import os

os.environ["ROBOT_FULLSCREEN"] = "1"

# Prevent pygame from grabbing the audio device
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from robot_app.face_loop import run_face_loop


def main():
    run_face_loop()


if __name__ == "__main__":
    main()
