import pygame

import robot_face as rf

from .gemini_worker import start_gemini_thread
from .state import RobotSharedState


KEY_EXPRESSIONS = {
    pygame.K_1: "neutral",
    pygame.K_2: "happy",
    pygame.K_3: "sad",
    pygame.K_4: "surprised",
    pygame.K_5: "confused",
    pygame.K_6: "angry",
    pygame.K_7: "sleepy",
}


def handle_keydown(event, state: RobotSharedState):
    if event.key == pygame.K_ESCAPE:
        return False

    if event.key in KEY_EXPRESSIONS:
        state.set_expression(KEY_EXPRESSIONS[event.key])
        return True

    if event.key == pygame.K_SPACE:
        _, speaking, _ = state.snapshot()
        state.set_speaking(not speaking)

    return True


def run_face_loop():
    state = RobotSharedState()
    face = rf.RobotFace()

    start_gemini_thread(state)

    running = True

    try:
        while running:
            dt = rf.clock.tick(rf.FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    running = handle_keydown(event, state)

            expression, speaking, stopped = state.snapshot()
            if stopped:
                break

            face.set_expression(expression)
            face.speaking = speaking

            face.update(dt)
            face.draw(rf.screen)

            pygame.display.flip()

    except KeyboardInterrupt:
        print("\nStopping robot...")

    finally:
        state.stop()
        pygame.quit()

