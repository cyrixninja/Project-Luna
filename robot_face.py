import os
import pygame
import math
import random
import sys

pygame.init()

WIDTH, HEIGHT = 800, 480
FPS = 60

display_flags = 0

if os.environ.get("ROBOT_FULLSCREEN", "0") == "1":
    display_flags = pygame.FULLSCREEN | pygame.SCALED

screen = pygame.display.set_mode((WIDTH, HEIGHT), display_flags)
pygame.display.set_caption("RobotFace")
pygame.mouse.set_visible(display_flags == 0)
clock = pygame.time.Clock()

# ============================================================
# COLORS
# ============================================================

BG_TOP = (3, 8, 20)
BG_BOTTOM = (1, 3, 10)

SOFT_SHADOW = (8, 14, 24)
MOUTH_INNER = (5, 10, 18)
MOUTH_INNER_2 = (12, 18, 28)

EXPR_COLORS = {
    "neutral":   (92, 155, 245),
    "happy":     (88, 235, 245),
    "sad":       (110, 170, 245),
    "surprised": (70, 220, 255),
    "confused":  (170, 130, 255),
    "angry":     (245, 92, 100),
    "sleepy":    (120, 145, 235),
}

# ============================================================
# HELPERS
# ============================================================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def color_scale(color, factor):
    return (
        clamp(int(color[0] * factor), 0, 255),
        clamp(int(color[1] * factor), 0, 255),
        clamp(int(color[2] * factor), 0, 255),
    )


def color_mix(a, b, t):
    return (
        int(lerp(a[0], b[0], t)),
        int(lerp(a[1], b[1], t)),
        int(lerp(a[2], b[2], t)),
    )


def draw_vertical_gradient(surface, top_color, bottom_color):
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = color_mix(top_color, bottom_color, t)
        pygame.draw.line(surface, color, (0, y), (WIDTH, y))


def draw_capsule(surface, rect, color):
    x, y, w, h = [int(v) for v in rect]

    if w <= 0 or h <= 0:
        return

    if w <= h:
        pygame.draw.ellipse(surface, color, (x, y, w, h))
        return

    r = h // 2
    pygame.draw.rect(surface, color, (x + r, y, w - 2 * r, h))
    pygame.draw.circle(surface, color, (x + r, y + r), r)
    pygame.draw.circle(surface, color, (x + w - r, y + r), r)


def draw_shadowed_capsule(surface, cx, cy, w, h, color, shadow_offset=5):
    draw_capsule(surface, (cx - w / 2, cy - h / 2 + shadow_offset, w, h), SOFT_SHADOW)
    draw_capsule(surface, (cx - w / 2, cy - h / 2, w, h), color)


def draw_shadowed_ellipse(surface, cx, cy, w, h, color, shadow_offset=5):
    pygame.draw.ellipse(surface, SOFT_SHADOW, (cx - w / 2, cy - h / 2 + shadow_offset, w, h))
    pygame.draw.ellipse(surface, color, (cx - w / 2, cy - h / 2, w, h))


def draw_arc(surface, rect, color, start_deg, end_deg, width):
    pygame.draw.arc(
        surface,
        color,
        pygame.Rect(rect),
        math.radians(start_deg),
        math.radians(end_deg),
        width
    )


def shadow_points(points, offset=5):
    return [(x, y + offset) for x, y in points]


def draw_rotated_capsule(surface, cx, cy, w, h, color, angle):
    temp_w = int(w + 60)
    temp_h = int(h + 60)
    temp = pygame.Surface((temp_w, temp_h), pygame.SRCALPHA)

    tcx = temp_w // 2
    tcy = temp_h // 2

    draw_capsule(temp, (tcx - w / 2, tcy - h / 2 + 5, w, h), SOFT_SHADOW)
    draw_capsule(temp, (tcx - w / 2, tcy - h / 2, w, h), color)

    rotated = pygame.transform.rotate(temp, angle)
    surface.blit(rotated, rotated.get_rect(center=(cx, cy)))


def draw_bezier_curve(surface, points, color, width):
    if len(points) < 3:
        return

    p0, p1, p2 = points
    curve_points = []

    for i in range(40):
        t = i / 39
        x = (1 - t) * (1 - t) * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) * (1 - t) * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        curve_points.append((int(x), int(y)))

    pygame.draw.lines(surface, color, False, curve_points, width)
    pygame.draw.circle(surface, color, curve_points[0], max(1, width // 2))
    pygame.draw.circle(surface, color, curve_points[-1], max(1, width // 2))

# ============================================================
# ROBOT FACE
# ============================================================

class RobotFace:
    def __init__(self):
        self.expression = "neutral"
        self.time = 0.0

        self.look_x = 0.0
        self.look_y = 0.0
        self.target_look_x = 0.0
        self.target_look_y = 0.0
        self.look_timer = 0.0

        self.blink = 0.0
        self.blink_state = "idle"
        self.blink_timer = random.uniform(1.5, 3.5)

        self.speaking = False
        self.speech_target = 0.0
        self.speech_energy = 0.0

    def set_expression(self, name):
        self.expression = name

    def current_color(self):
        return EXPR_COLORS.get(self.expression, EXPR_COLORS["neutral"])

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    def update(self, dt):
        self.time += dt
        self.update_look(dt)
        self.update_blink(dt)
        self.update_speech(dt)

    def update_look(self, dt):
        self.look_timer -= dt

        if self.look_timer <= 0:
            self.target_look_x = random.uniform(-8, 8)
            self.target_look_y = random.uniform(-4, 4)
            self.look_timer = random.uniform(1.0, 2.4)

        self.look_x = lerp(self.look_x, self.target_look_x, dt * 3.2)
        self.look_y = lerp(self.look_y, self.target_look_y, dt * 3.2)

    def update_blink(self, dt):
        self.blink_timer -= dt

        if self.blink_state == "idle" and self.blink_timer <= 0:
            self.blink_state = "closing"

        if self.blink_state == "closing":
            self.blink += dt * 11.5
            if self.blink >= 1.0:
                self.blink = 1.0
                self.blink_state = "opening"

        elif self.blink_state == "opening":
            self.blink -= dt * 13.0
            if self.blink <= 0.0:
                self.blink = 0.0
                self.blink_state = "idle"
                self.blink_timer = random.uniform(1.7, 4.2)

        self.blink = clamp(self.blink, 0.0, 1.0)

        if self.expression == "sleepy":
            self.blink = max(self.blink, 0.55)

    def update_speech(self, dt):
        if self.speaking:
            raw = (
                0.45
                + 0.24 * math.sin(self.time * 10.0)
                + 0.15 * math.sin(self.time * 18.0 + 0.8)
                + 0.08 * math.sin(self.time * 26.0 + 1.4)
            )
            self.speech_target = clamp(raw, 0.10, 1.0)
        else:
            self.speech_target = 0.0

        self.speech_energy = lerp(self.speech_energy, self.speech_target, dt * 9.0)

    # --------------------------------------------------------
    # DRAW
    # --------------------------------------------------------

    def draw(self, surface):
        draw_vertical_gradient(surface, BG_TOP, BG_BOTTOM)
        self.draw_background_depth(surface)
        self.draw_eyes(surface)
        self.draw_mouth(surface)

    def draw_background_depth(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(overlay, (8, 18, 34, 34), (205, 95, 390, 88))
        pygame.draw.ellipse(overlay, (4, 9, 18, 42), (265, 288, 270, 42))
        surface.blit(overlay, (0, 0))

    # ========================================================
    # EYES
    # ========================================================

    def draw_eyes(self, surface):
        blink = smoothstep(self.blink)

        bob = math.sin(self.time * 1.5) * 2.2
        talk_focus = self.speech_energy * 3.0

        lx = 280 + self.look_x
        rx = 520 + self.look_x
        y = 180 + self.look_y + bob - talk_focus

        if self.expression == "neutral":
            self.draw_neutral_eyes(surface, lx, rx, y, blink)
        elif self.expression == "happy":
            self.draw_happy_eyes(surface, lx, rx, y, blink)
        elif self.expression == "sad":
            self.draw_sad_eyes(surface, lx, rx, y, blink)
        elif self.expression == "surprised":
            self.draw_surprised_eyes(surface, lx, rx, y, blink)
        elif self.expression == "confused":
            self.draw_confused_eyes(surface, lx, rx, y, blink)
        elif self.expression == "angry":
            self.draw_angry_eyes(surface, lx, rx, y, blink)
        elif self.expression == "sleepy":
            self.draw_sleepy_eyes(surface, lx, rx, y, blink)
        else:
            self.draw_neutral_eyes(surface, lx, rx, y, blink)

    def draw_neutral_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()
        w = 122
        h = max(8, 68 * (1.0 - blink * 0.94) * (1.0 - self.speech_energy * 0.08))

        for cx in (lx, rx):
            draw_shadowed_capsule(surface, cx, y, w, h, color)

    def draw_happy_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()

        # cheerful bounce
        y += math.sin(self.time * 4.0) * 1.2

        # thicker happy eyes
        eye_width = 108
        eye_height = max(20, 26 * (1.0 - blink * 0.08))

        for cx in (lx, rx):
            start = (cx - eye_width // 2, y + eye_height // 2)
            control = (cx, y - 28)
            end = (cx + eye_width // 2, y + eye_height // 2)

            shadow_start = (start[0], start[1] + 5)
            shadow_control = (control[0], control[1] + 5)
            shadow_end = (end[0], end[1] + 5)

            draw_bezier_curve(
                surface,
                [shadow_start, shadow_control, shadow_end],
                SOFT_SHADOW,
                18
            )

            draw_bezier_curve(
                surface,
                [start, control, end],
                color,
                14
            )

    def draw_sad_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()
        brow_color = color_scale(color, 0.82)

        y += 10 + math.sin(self.time * 1.2) * 0.6

        eye_w = 96
        eye_h = max(10, 18 * (1.0 - blink * 0.55))

        left_start = (lx - eye_w // 2, y - 2)
        left_control = (lx, y + 18)
        left_end = (lx + eye_w // 2, y + 4)

        right_start = (rx - eye_w // 2, y + 4)
        right_control = (rx, y + 18)
        right_end = (rx + eye_w // 2, y - 2)

        draw_bezier_curve(
            surface,
            [
                (left_start[0], left_start[1] + 5),
                (left_control[0], left_control[1] + 5),
                (left_end[0], left_end[1] + 5),
            ],
            SOFT_SHADOW,
            12
        )

        draw_bezier_curve(
            surface,
            [
                (right_start[0], right_start[1] + 5),
                (right_control[0], right_control[1] + 5),
                (right_end[0], right_end[1] + 5),
            ],
            SOFT_SHADOW,
            12
        )

        draw_bezier_curve(surface, [left_start, left_control, left_end], color, 9)
        draw_bezier_curve(surface, [right_start, right_control, right_end], color, 9)

        pygame.draw.line(
            surface,
            brow_color,
            (int(lx - 42), int(y - 26)),
            (int(lx + 10), int(y - 34)),
            4
        )
        pygame.draw.line(
            surface,
            brow_color,
            (int(rx - 10), int(y - 34)),
            (int(rx + 42), int(y - 26)),
            4
        )

    def draw_surprised_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()
        w = 96
        h = max(
            14,
            110 * (1.0 - blink * 0.90) * (1.0 + 0.03 * math.sin(self.time * 6.0))
        )

        for cx in (lx, rx):
            draw_shadowed_ellipse(surface, cx, y, w, h, color)

    def draw_confused_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()

        y += 2 + math.sin(self.time * 1.8) * 1.0
        wobble = math.sin(self.time * 4.0) * 2.5

        w1 = 104
        h1 = max(14, (78 + wobble) * (1.0 - blink * 0.90))
        draw_shadowed_ellipse(surface, lx, y, w1, h1, color)

        w2 = 110
        h2 = max(8, (22 - wobble * 0.35) * (1.0 - blink * 0.90))
        draw_shadowed_capsule(surface, rx, y - 6, w2, h2, color)

        pygame.draw.line(
            surface,
            color,
            (int(rx - 36), int(y - 42)),
            (int(rx - 10), int(y - 48)),
            4
        )

    def draw_angry_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()
        brow_color = color_scale(color, 0.72)

        y += math.sin(self.time * 6.0) * 0.8

        left_eye = [
            (lx - 56, y - 10),
            (lx + 56, y + 6),
            (lx + 42, y + 24),
            (lx - 44, y + 12),
        ]

        right_eye = [
            (rx - 56, y + 6),
            (rx + 56, y - 10),
            (rx + 44, y + 12),
            (rx - 42, y + 24),
        ]

        pygame.draw.polygon(surface, SOFT_SHADOW, shadow_points(left_eye, 6))
        pygame.draw.polygon(surface, SOFT_SHADOW, shadow_points(right_eye, 6))

        pygame.draw.polygon(surface, color, left_eye)
        pygame.draw.polygon(surface, color, right_eye)

        left_brow = [
            (lx - 70, y - 34),
            (lx + 18, y - 18),
            (lx + 12, y - 8),
            (lx - 76, y - 24),
        ]

        right_brow = [
            (rx - 18, y - 18),
            (rx + 70, y - 34),
            (rx + 76, y - 24),
            (rx - 12, y - 8),
        ]

        pygame.draw.polygon(surface, brow_color, left_brow)
        pygame.draw.polygon(surface, brow_color, right_brow)

    def draw_sleepy_eyes(self, surface, lx, rx, y, blink):
        color = self.current_color()

        y += 12 + math.sin(self.time * 1.0) * 1.0

        left_h = max(6, 14 * (1.0 - blink * 0.20))
        right_h = max(6, 12 * (1.0 - blink * 0.20))
        w = 118

        draw_rotated_capsule(surface, lx, y, w, left_h, color, angle=-2)
        draw_rotated_capsule(surface, rx, y, w, right_h, color, angle=2)

    # ========================================================
    # MOUTH
    # ========================================================

    def draw_mouth(self, surface):
        color = self.current_color()

        bob = math.sin(self.time * 1.35) * 1.5
        cx = WIDTH // 2
        cy = 318 + bob

        if self.speech_energy > 0.04:
            self.draw_speaking_mouth(surface, cx, cy, color)
            return

        expr = self.expression

        if expr == "happy":
            start = (cx - 68, cy - 6)
            control = (cx, cy + 34)
            end = (cx + 68, cy - 6)

            draw_bezier_curve(
                surface,
                [
                    (start[0], start[1] + 5),
                    (control[0], control[1] + 5),
                    (end[0], end[1] + 5),
                ],
                SOFT_SHADOW,
                10
            )

            draw_bezier_curve(surface, [start, control, end], color, 8)

        elif expr == "sad":
            start = (cx - 64, cy + 16)
            control = (cx, cy - 14)
            end = (cx + 64, cy + 16)

            draw_bezier_curve(
                surface,
                [
                    (start[0], start[1] + 5),
                    (control[0], control[1] + 5),
                    (end[0], end[1] + 5),
                ],
                SOFT_SHADOW,
                10
            )

            draw_bezier_curve(surface, [start, control, end], color, 8)

        elif expr == "surprised":
            pygame.draw.ellipse(surface, color, (cx - 28, cy - 26, 56, 56))
            pygame.draw.ellipse(surface, MOUTH_INNER, (cx - 18, cy - 16, 36, 36))

        elif expr == "confused":
            points = [
                (cx - 48, cy + 3),
                (cx - 18, cy - 7),
                (cx + 12, cy + 4),
                (cx + 44, cy - 3)
            ]
            shadow = [(x, y + 4) for x, y in points]
            pygame.draw.lines(surface, SOFT_SHADOW, False, shadow, 8)
            pygame.draw.lines(surface, color, False, points, 6)

        elif expr == "angry":
            angry_pts = [
                (cx - 42, cy + 8),
                (cx - 16, cy + 8),
                (cx,      cy + 3),
                (cx + 16, cy + 8),
                (cx + 42, cy + 8),
            ]
            angry_shadow = [(x, y + 4) for x, y in angry_pts]
            pygame.draw.lines(surface, SOFT_SHADOW, False, angry_shadow, 8)
            pygame.draw.lines(surface, color, False, angry_pts, 6)

        elif expr == "sleepy":
            draw_capsule(surface, (cx - 28, cy + 5, 56, 7), color)

        else:
            draw_capsule(surface, (cx - 46, cy, 92, 10), color)

    def draw_speaking_mouth(self, surface, cx, cy, color):
        energy = self.speech_energy

        w = int(92 + 76 * energy)
        h = int(12 + 42 * energy)

        darker = color_scale(color, 0.78)
        lighter = color_mix(color, (255, 255, 255), 0.25)

        draw_capsule(surface, (cx - w / 2, cy - h / 2 + 5, w, h), SOFT_SHADOW)
        draw_capsule(surface, (cx - w / 2, cy - h / 2, w, h), color)

        inner_w = max(12, w - 16)
        inner_h = max(6, h - 12)

        draw_capsule(
            surface,
            (cx - inner_w / 2, cy - inner_h / 2, inner_w, inner_h),
            MOUTH_INNER
        )

        if inner_h > 14:
            draw_capsule(
                surface,
                (
                    cx - inner_w * 0.34,
                    cy + inner_h * 0.04,
                    inner_w * 0.68,
                    inner_h * 0.30
                ),
                MOUTH_INNER_2
            )

        if inner_h > 8:
            draw_capsule(
                surface,
                (
                    cx - inner_w * 0.20,
                    cy - inner_h * 0.36,
                    inner_w * 0.40,
                    4
                ),
                lighter
            )

        if inner_h > 18:
            draw_capsule(
                surface,
                (
                    cx - inner_w * 0.22,
                    cy + inner_h * 0.05,
                    inner_w * 0.44,
                    max(4, inner_h * 0.12)
                ),
                darker
            )

# ============================================================
# MAIN
# ============================================================

def main():
    face = RobotFace()
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    face.speaking = not face.speaking
                elif event.key == pygame.K_1:
                    face.set_expression("neutral")
                elif event.key == pygame.K_2:
                    face.set_expression("happy")
                elif event.key == pygame.K_3:
                    face.set_expression("sad")
                elif event.key == pygame.K_4:
                    face.set_expression("surprised")
                elif event.key == pygame.K_5:
                    face.set_expression("confused")
                elif event.key == pygame.K_6:
                    face.set_expression("angry")
                elif event.key == pygame.K_7:
                    face.set_expression("sleepy")

        face.update(dt)
        face.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
