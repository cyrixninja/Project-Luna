import asyncio
import threading
import time

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

from .audio import clear_async_queue, open_output_stream, resample_audio
from .config import (
    API_KEY,
    EXTRA_LISTEN_DELAY_AFTER_SPEAKING,
    GEMINI_INPUT_RATE,
    GEMINI_OUTPUT_RATE,
    MIC_CHUNK,
    MIC_DEVICE,
    MIC_NATIVE_RATE,
    MODEL,
    MUTE_MIC_WHILE_SPEAKING,
    SPEAKER_NATIVE_RATE,
)
from .gemini_tools import handle_tool_call, live_config
from .state import RobotSharedState


client = genai.Client(api_key=API_KEY)


async def gemini_audio_worker(state: RobotSharedState):
    print("Available audio devices:")
    print(sd.query_devices())

    mic_queue = asyncio.Queue(maxsize=10)
    speaker_queue = asyncio.Queue(maxsize=40)

    robot_is_speaking = asyncio.Event()
    allow_listening_after = {"time": 0.0}

    async with client.aio.live.connect(model=MODEL, config=live_config()) as session:
        print("\nGemini Live started.")
        print("Robot face linked.")
        print("Speak into the mic. Press ESC in the robot window to stop.\n")

        loop = asyncio.get_running_loop()

        def mic_callback(indata, frames, time_info, status):
            if status and "overflow" not in str(status).lower():
                print("Mic status:", status)

            audio_float = indata[:, 0].copy()

            def put_audio():
                _, _, stopped = state.snapshot()
                if stopped:
                    return

                if mic_queue.full():
                    try:
                        mic_queue.get_nowait()
                        mic_queue.task_done()
                    except asyncio.QueueEmpty:
                        pass

                try:
                    mic_queue.put_nowait(audio_float)
                except asyncio.QueueFull:
                    pass

            loop.call_soon_threadsafe(put_audio)

        async def send_mic():
            with sd.InputStream(
                device=MIC_DEVICE,
                samplerate=MIC_NATIVE_RATE,
                channels=1,
                dtype="float32",
                blocksize=MIC_CHUNK,
                latency="high",
                callback=mic_callback,
            ):
                print(f"[Audio] Using mic input: device {MIC_DEVICE}")

                while True:
                    _, _, stopped = state.snapshot()
                    if stopped:
                        break

                    audio_float = await mic_queue.get()

                    now = time.monotonic()

                    if MUTE_MIC_WHILE_SPEAKING:
                        if robot_is_speaking.is_set() or now < allow_listening_after["time"]:
                            mic_queue.task_done()
                            continue

                    audio_float = np.clip(audio_float, -1.0, 1.0)
                    audio_int16 = (audio_float * 32767).astype(np.int16)

                    audio_16k = resample_audio(
                        audio_int16,
                        MIC_NATIVE_RATE,
                        GEMINI_INPUT_RATE,
                    )

                    if len(audio_16k) > 0:
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_16k.tobytes(),
                                mime_type=f"audio/pcm;rate={GEMINI_INPUT_RATE}",
                            )
                        )

                    mic_queue.task_done()

        async def receive_audio():
            while True:
                _, _, stopped = state.snapshot()
                if stopped:
                    break

                async for response in session.receive():
                    _, _, stopped = state.snapshot()
                    if stopped:
                        break

                    if response.tool_call:
                        await handle_tool_call(response, session, state)
                        continue

                    if response.server_content and response.server_content.interrupted:
                        print("[Interrupted]")
                        clear_async_queue(speaker_queue)
                        await speaker_queue.put(None)
                        continue

                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                audio_24k = np.frombuffer(
                                    part.inline_data.data,
                                    dtype=np.int16,
                                )

                                audio_48k = resample_audio(
                                    audio_24k,
                                    GEMINI_OUTPUT_RATE,
                                    SPEAKER_NATIVE_RATE,
                                )

                                if speaker_queue.full():
                                    try:
                                        speaker_queue.get_nowait()
                                        speaker_queue.task_done()
                                    except asyncio.QueueEmpty:
                                        pass

                                await speaker_queue.put(audio_48k)

                    elif response.data:
                        audio_24k = np.frombuffer(response.data, dtype=np.int16)

                        audio_48k = resample_audio(
                            audio_24k,
                            GEMINI_OUTPUT_RATE,
                            SPEAKER_NATIVE_RATE,
                        )

                        if speaker_queue.full():
                            try:
                                speaker_queue.get_nowait()
                                speaker_queue.task_done()
                            except asyncio.QueueEmpty:
                                pass

                        await speaker_queue.put(audio_48k)

                await asyncio.sleep(0.01)

        async def play_audio():
            stream = None

            try:
                stream = open_output_stream()

                while True:
                    _, _, stopped = state.snapshot()
                    if stopped:
                        break

                    audio = await speaker_queue.get()

                    if audio is None:
                        try:
                            stream.abort()
                            stream.start()
                        except Exception:
                            pass

                        robot_is_speaking.clear()
                        state.set_speaking(False)
                        allow_listening_after["time"] = (
                            time.monotonic() + EXTRA_LISTEN_DELAY_AFTER_SPEAKING
                        )

                        speaker_queue.task_done()
                        continue

                    robot_is_speaking.set()
                    state.set_speaking(True)

                    if audio.ndim == 1:
                        audio_out = np.column_stack((audio, audio))
                    else:
                        audio_out = audio

                    await asyncio.to_thread(stream.write, audio_out)

                    if speaker_queue.empty():
                        robot_is_speaking.clear()
                        state.set_speaking(False)
                        allow_listening_after["time"] = (
                            time.monotonic() + EXTRA_LISTEN_DELAY_AFTER_SPEAKING
                        )

                    speaker_queue.task_done()

            finally:
                state.set_speaking(False)

                if stream is not None:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass

        tasks = [
            asyncio.create_task(send_mic()),
            asyncio.create_task(receive_audio()),
            asyncio.create_task(play_audio()),
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()


def start_gemini_thread(state: RobotSharedState):
    def runner():
        try:
            asyncio.run(gemini_audio_worker(state))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"[Gemini thread error] {e}")
            state.set_expression("confused")
            state.set_speaking(False)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread

