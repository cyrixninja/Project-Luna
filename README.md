# Project Luna

Luna is a voice-enabled robot still in progress
It listens from your microphone, speaks through your speakers, and updates facial expressions in real time.

## Features

- Real-time voice conversation using Gemini Live API
- Animated robot face rendered with Pygame
- Expression control through tool calls from the model
- Echo-reduction behavior while the robot is speaking
- Manual keyboard expression overrides for quick testing

## Project Structure

```
robot/
├── robot.py                  # Main launcher for the face UI + Gemini worker
├── robot_face.py             # Face renderer and animation system
├── test.py                   # Standalone Gemini audio test script
├── requirements.txt
└── robot_app/
    ├── config.py             # API key, model, audio rates, device IDs, expression config
    ├── state.py              # Shared thread-safe robot state
    ├── face_loop.py          # Main UI loop + keyboard handling
    ├── audio.py              # Resampling and speaker stream helpers
    ├── gemini_tools.py       # Function tool declaration + tool call handler
    └── gemini_worker.py      # Gemini Live audio send/receive/playback loop
```

## Requirements

- Linux (project is currently configured and tested on Linux)
- Python 3.10+
- A valid Gemini API key
- Working microphone and speaker devices
- PortAudio runtime/development libraries (required by sounddevice)

On Debian/Ubuntu-like systems:

```bash
sudo apt update
sudo apt install -y portaudio19-dev
```

## Installation

1. Clone the repository and enter it.
2. Create and activate a virtual environment.
3. Install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Configuration

Create a .env file in the project root with your Gemini key:

```env
GEMINI_API_KEY=your_api_key_here
```

The app loads this automatically via python-dotenv.

## Audio Device Configuration

Audio device IDs are currently configured in robot_app/config.py:

- MIC_DEVICE = 2
- SPEAKER_DEVICE = 1

These IDs are machine-specific. If audio does not work:

1. Run the app once and check the printed device list.
2. Update MIC_DEVICE and SPEAKER_DEVICE in robot_app/config.py.
3. Restart the app.

## Running Luna

Start the full robot app:

```bash
source .venv/bin/activate
python robot.py
```

What starts:

- Pygame robot face window
- Background Gemini live audio worker thread
- Realtime mic input, model response streaming, and speaker playback

## Keyboard Controls

Inside the robot window:

- ESC: Quit
- SPACE: Toggle speaking flag manually (for quick visual testing)
- 1: neutral
- 2: happy
- 3: sad
- 4: surprised
- 5: confused
- 6: angry
- 7: sleepy

## Expression System

Gemini is provided a function tool named set_robot_expression.
Before each spoken reply, the model is instructed to set an expression.

State guardrails in robot_app/state.py reduce repetitive visuals:

- Invalid expressions fall back to neutral
- Repeated same-expression runs are diversified
- Happy is rate-limited to avoid overuse

## Echo Mitigation

To reduce speaker-to-mic feedback, the app:

- Mutes mic forwarding while robot audio is playing
- Adds a short delay before listening again after speech

Main controls are in robot_app/config.py:

- MUTE_MIC_WHILE_SPEAKING
- EXTRA_LISTEN_DELAY_AFTER_SPEAKING

## Useful Scripts

- robot.py: Main app entrypoint (recommended)
- test.py: Older standalone live audio script for direct diagnostics
- robot_face.py: Face renderer module used by the main loop

## Troubleshooting

### KeyError: GEMINI_API_KEY

Your key is missing from environment/.env.
Add GEMINI_API_KEY to .env and restart.

### No usable speaker output found

Speaker device ID is likely wrong. Check printed device list and update SPEAKER_DEVICE.

### Mic input not detected

Verify MIC_DEVICE, microphone permissions, and that your input device is not in use by another app.

### High echo or self-feedback

Keep MUTE_MIC_WHILE_SPEAKING enabled and increase EXTRA_LISTEN_DELAY_AFTER_SPEAKING slightly.

### Pygame window does not appear full screen

Fullscreen is controlled by ROBOT_FULLSCREEN in robot.py.
It is set to 1 by default there.

## Dependency List

From requirements.txt:

- google-genai
- pygame
- sounddevice
- python-dotenv
- websockets
- numpy
- scipy

## Notes

- Current branch defaults to master in this local repo.
- Default branch for GitHub repository is main.
- The model configured in code is gemini-3.1-flash-live-preview.
