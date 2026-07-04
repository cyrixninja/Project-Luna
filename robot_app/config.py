import os

from dotenv import load_dotenv


load_dotenv()

API_KEY = os.environ["GEMINI_API_KEY"]

MODEL = "gemini-3.1-flash-live-preview"

# Device list:
# 1 = AB13X USB Audio, has 1 input and 2 outputs
# 2 = Maono Elf mic
MIC_DEVICE = 2
SPEAKER_DEVICE = 1

MIC_NATIVE_RATE = 44100
GEMINI_INPUT_RATE = 16000

GEMINI_OUTPUT_RATE = 24000
SPEAKER_NATIVE_RATE = 48000

MIC_CHUNK = 4096

MUTE_MIC_WHILE_SPEAKING = True
EXTRA_LISTEN_DELAY_AFTER_SPEAKING = 0.45

VALID_EXPRESSIONS = [
    "neutral",
    "happy",
    "sad",
    "surprised",
    "confused",
    "angry",
    "sleepy",
]

EXPRESSION_FALLBACKS = [
    "neutral",
    "confused",
    "surprised",
    "sleepy",
]
