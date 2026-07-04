import asyncio

import numpy as np
import sounddevice as sd

from .config import SPEAKER_DEVICE, SPEAKER_NATIVE_RATE


def resample_audio(audio_np: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
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


def clear_async_queue(q: asyncio.Queue):
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except asyncio.QueueEmpty:
            break


def unique_devices(devices):
    result = []
    seen = set()

    for device in devices:
        key = "default" if device is None else str(device)
        if key not in seen:
            seen.add(key)
            result.append(device)

    return result


def open_output_stream():
    """Open the preferred speaker stream, falling back through known devices."""

    candidates = unique_devices([
        SPEAKER_DEVICE,
        1,
        5,
        None,
        3,
        4,
        0,
    ])

    last_error = None

    for device in candidates:
        try:
            stream = sd.OutputStream(
                device=device,
                samplerate=SPEAKER_NATIVE_RATE,
                channels=2,
                dtype="int16",
                latency="high",
            )
            stream.start()

            label = "system default" if device is None else f"device {device}"
            print(f"[Audio] Using speaker output: {label}")

            return stream

        except Exception as e:
            label = "system default" if device is None else f"device {device}"
            print(f"[Audio] Could not open speaker {label}: {e}")
            last_error = e

    raise RuntimeError(f"No usable speaker output found. Last error: {last_error}")

