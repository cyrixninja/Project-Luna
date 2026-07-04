import asyncio
import os
import time
import numpy as np
import sounddevice as sd

from google import genai
from google.genai import types


API_KEY = os.environ["GEMINI_API_KEY"]

MODEL = "gemini-3.1-flash-live-preview"

MIC_DEVICE = 2
SPEAKER_DEVICE = 1

MIC_NATIVE_RATE = 44100
GEMINI_INPUT_RATE = 16000

GEMINI_OUTPUT_RATE = 24000
SPEAKER_NATIVE_RATE = 48000

MIC_CHUNK = 4096

# Important anti-echo settings
MUTE_MIC_WHILE_SPEAKING = True
EXTRA_LISTEN_DELAY_AFTER_SPEAKING = 0.45  # seconds

client = genai.Client(api_key=API_KEY)


def resample_audio(audio_np, from_rate, to_rate):
    if len(audio_np) == 0:
        return audio_np.astype(np.int16)

    if from_rate == to_rate:
        return audio_np.astype(np.int16)

    new_length = int(len(audio_np) * to_rate / from_rate)
    if new_length <= 0:
        return np.array([], dtype=np.int16)

    old_indices = np.arange(len(audio_np))
    new_indices = np.linspace(0, len(audio_np) - 1, new_length)

    return np.interp(new_indices, old_indices, audio_np).astype(np.int16)


def clear_queue(q: asyncio.Queue):
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except asyncio.QueueEmpty:
            break


async def main():
    print("Available audio devices:")
    print(sd.query_devices())

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (
            "You are a simple friendly robot assistant. "
            "Reply briefly and naturally."
        ),
    }

    mic_queue = asyncio.Queue(maxsize=10)
    speaker_queue = asyncio.Queue(maxsize=40)

    # Shared state
    robot_is_speaking = asyncio.Event()
    allow_listening_after = {"time": 0.0}

    async with client.aio.live.connect(model=MODEL, config=config) as session:
        print("\nGemini Live started.")
        print("Speak into the mic. Ctrl+C to stop.\n")

        loop = asyncio.get_running_loop()

        def mic_callback(indata, frames, time_info, status):
            if status and "overflow" not in str(status).lower():
                print("Mic status:", status)

            audio_float = indata[:, 0].copy()

            def put_audio():
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
                while True:
                    audio_float = await mic_queue.get()

                    now = time.monotonic()

                    # Anti-echo:
                    # Do not send mic audio while robot speaker is playing.
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
                async for response in session.receive():
                    if response.server_content and response.server_content.interrupted:
                        print("[Interrupted]")
                        clear_queue(speaker_queue)
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
            with sd.OutputStream(
                device=SPEAKER_DEVICE,
                samplerate=SPEAKER_NATIVE_RATE,
                channels=1,
                dtype="int16",
                latency="high",
            ) as stream:
                while True:
                    audio = await speaker_queue.get()

                    if audio is None:
                        try:
                            stream.abort()
                            stream.start()
                        except Exception:
                            pass

                        robot_is_speaking.clear()
                        allow_listening_after["time"] = (
                            time.monotonic() + EXTRA_LISTEN_DELAY_AFTER_SPEAKING
                        )

                        speaker_queue.task_done()
                        continue

                    robot_is_speaking.set()

                    await asyncio.to_thread(stream.write, audio)

                    # If no more audio is waiting, assume robot finished speaking
                    if speaker_queue.empty():
                        robot_is_speaking.clear()
                        allow_listening_after["time"] = (
                            time.monotonic() + EXTRA_LISTEN_DELAY_AFTER_SPEAKING
                        )

                    speaker_queue.task_done()

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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")