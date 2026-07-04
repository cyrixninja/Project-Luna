import random
import threading
import time
from dataclasses import dataclass

from .config import EXPRESSION_FALLBACKS, VALID_EXPRESSIONS


@dataclass
class RobotSharedState:
    expression: str = "neutral"
    speaking: bool = False
    stopped: bool = False

    last_expression: str = "neutral"
    repeated_expression_count: int = 0
    last_happy_time: float = 0.0

    def __post_init__(self):
        self.lock = threading.Lock()

    def set_expression(self, expression: str):
        if expression not in VALID_EXPRESSIONS:
            expression = "neutral"

        with self.lock:
            now = time.monotonic()

            if expression == self.last_expression:
                self.repeated_expression_count += 1
            else:
                self.repeated_expression_count = 0

            if expression == "happy":
                happy_too_recent = now - self.last_happy_time < 8.0
                happy_repeated = self.last_expression == "happy"

                if happy_too_recent or happy_repeated:
                    expression = random.choice(["neutral", "surprised", "sleepy"])

                self.last_happy_time = now

            if self.repeated_expression_count >= 2:
                choices = [e for e in EXPRESSION_FALLBACKS if e != self.last_expression]
                expression = random.choice(choices)
                self.repeated_expression_count = 0

            self.expression = expression
            self.last_expression = expression

    def set_speaking(self, speaking: bool):
        with self.lock:
            self.speaking = speaking

    def stop(self):
        with self.lock:
            self.stopped = True
            self.speaking = False

    def snapshot(self):
        with self.lock:
            return self.expression, self.speaking, self.stopped

