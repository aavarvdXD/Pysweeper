import sys
import random
from collections import deque
import json
import os

import pygame

# ----------------------------
# Difficulty Presets
# ----------------------------
DIFFICULTIES = {
    "Easy":   {"grid_w": 9,  "grid_h": 9,  "mines": 10},
    "Medium": {"grid_w": 16, "grid_h": 16, "mines": 40},
    "Hard":   {"grid_w": 30, "grid_h": 16, "mines": 99},
    "Custom": {"grid_w": 24, "grid_h": 16, "density": 0.21},
}
DIFFICULTY_ORDER = ["Easy", "Medium", "Hard", "Custom"]

# ----------------------------
# Config (defaults to Custom)
# ----------------------------
BASE_CELL = 40
BASE_TOPBAR = 48

current_difficulty = "Medium"

def get_grid_settings():
    d = DIFFICULTIES[current_difficulty]
    gw = d["grid_w"]
    gh = d["grid_h"]
    if "mines" in d:
        mines = d["mines"]
    else:
        mines = max(1, int(gw * gh * d.get("density", 0.15)))
    return gw, gh, mines

GRID_W, GRID_H, MINES = get_grid_settings()

WINDOW_W = GRID_W * BASE_CELL
WINDOW_H = BASE_TOPBAR + GRID_H * BASE_CELL

FPS = 60

SAVE_FILE = os.path.join(os.path.dirname(__file__), "minesweeper_scores.json")
AUTO_RESTART = False
AUTO_RESTART_DELAY_S = 1.25

OVERLAY_ALPHA = 170

# ----------------------------
# Colors
# ----------------------------
BG = (30, 30, 34)
PANEL = (45, 45, 52)
GRID_BG = (22, 22, 26)
LINE = (60, 60, 70)

COVER = (70, 70, 82)
COVER_HI = (85, 85, 100)

REVEALED = (200, 200, 210)
REVEALED_2 = (180, 180, 190)

FLAG = (220, 60, 60)
MINE = (20, 20, 20)

NUM_COLORS = {
    1: (25, 95, 235),
    2: (30, 130, 55),
    3: (220, 50, 50),
    4: (40, 40, 170),
    5: (140, 50, 30),
    6: (30, 140, 140),
    7: (10, 10, 10),
    8: (90, 90, 90),
}


def in_bounds(x, y):
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def neighbors(x, y):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if in_bounds(nx, ny):
                yield nx, ny


def load_best_times():
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Support both old single-value and new per-difficulty format
        if "best_times" in data:
            return data["best_times"]
        elif "best_time_s" in data:
            return {"Custom": data["best_time_s"]}
        return {}
    except Exception:
        return {}


def save_best_times(best_times: dict):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"best_times": best_times}, f)
    except Exception:
        pass


class Minesweeper:
    def __init__(self):
        self.first_click_zero_spread = True
        self.best_times = load_best_times()
        self.reset()

    def reset(self):
        global GRID_W, GRID_H, MINES
        GRID_W, GRID_H, MINES = get_grid_settings()

        self.mines = [[False] * GRID_H for _ in range(GRID_W)]
        self.numbers = [[0] * GRID_H for _ in range(GRID_W)]
        self.revealed = [[False] * GRID_H for _ in range(GRID_W)]
        self.flagged = [[False] * GRID_H for _ in range(GRID_W)]

        self.generated = False
        self.game_over = False
        self.win = False
        self.exploded = None

        self.flags_left = MINES
        self.reveal_count = 0

        self.started = False
        self.start_ticks = 0
        self.end_ticks = None

    def get_best_time(self):
        return self.best_times.get(current_difficulty, None)

    def elapsed_s(self):
        if not self.started:
            return 0.0
        end = self.end_ticks if self.end_ticks is not None else pygame.time.get_ticks()
        return max(0.0, (end - self.start_ticks) / 1000.0)

    def _start_timer_if_needed(self):
        if not self.started:
            self.started = True
            self.start_ticks = pygame.time.get_ticks()
            self.end_ticks = None

    def _finalize_timer(self):
        if self.started and self.end_ticks is None:
            self.end_ticks = pygame.time.get_ticks()

    def toggle_first_click_zero_spread(self):
        self.first_click_zero_spread = not self.first_click_zero_spread

    def _place_mines(self, safe_x, safe_y):
        forbidden = {(safe_x, safe_y)}
        if self.first_click_zero_spread:
            for nx, ny in neighbors(safe_x, safe_y):
                forbidden.add((nx, ny))

        candidates = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in forbidden]
        if len(candidates) < MINES:
            candidates = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) != (safe_x, safe_y)]

        for x, y in random.sample(candidates, MINES):
            self.mines[x][y] = True

        for x in range(GRID_W):
            for y in range(GRID_H):
                if self.mines[x][y]:
                    self.numbers[x][y] = -1
                else:
                    self.numbers[x][y] = sum(1 for nx, ny in neighbors(x, y) if self.mines[nx][ny])

        self.generated = True

        if self.first_click_zero_spread and self.numbers[safe_x][safe_y] != 0:
            self.mines = [[False] * GRID_H for _ in range(GRID_W)]
            self.numbers = [[0] * GRID_H for _ in range(GRID_W)]
            self._place_mines(safe_x, safe_y)

    def _flood_reveal_zeros(self, start_x, start_y):
        q = deque()
        q.append((start_x, start_y))
        visited = set()

        while q:
            x, y = q.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))

            if self.flagged[x][y] or self.revealed[x][y]:
                continue

            self.revealed[x][y] = True
            self.reveal_count += 1

            if self.numbers[x][y] == 0:
                for nx, ny in neighbors(x, y):
                    if not self.revealed[nx][ny] and not self.flagged[nx][ny]:
                        q.append((nx, ny))

    def _reveal_single(self, x, y):
        if self.flagged[x][y] or self.revealed[x][y]:
            return
        self.revealed[x][y] = True
        self.reveal_count += 1

    def reveal(self, x, y):
        if self.game_over or self.win:
            return
        if not in_bounds(x, y):
            return
        if self.flagged[x][y] or self.revealed[x][y]:
            return

        self._start_timer_if_needed()

        if not self.generated:
            self._place_mines(x, y)

        if self.mines[x][y]:
            self.game_over = True
            self.exploded = (x, y)
            self._finalize_timer()
            for ix in range(GRID_W):
                for iy in range(GRID_H):
                    if self.mines[ix][iy]:
                        self.revealed[ix][iy] = True
            return

        if self.numbers[x][y] == 0:
            self._flood_reveal_zeros(x, y)
        else:
            self._reveal_single(x, y)

        self._check_win()

    def toggle_flag(self, x, y):
        if self.game_over or self.win:
            return
        if not in_bounds(x, y):
            return
        if self.revealed[x][y]:
            return

        if self.flagged[x][y]:
            self.flagged[x][y] = False
            self.flags_left += 1
        else:
            if self.flags_left <= 0:
                return
            self.flagged[x][y] = True
            self.flags_left -= 1

    def chord(self, x, y):
        if self.game_over or self.win:
            return
        if not in_bounds(x, y):
            return
        if not self.revealed[x][y]:
            return
        n = self.numbers[x][y]
        if n <= 0:
            return

        adj_flags = sum(1 for nx, ny in neighbors(x, y) if self.flagged[nx][ny])
        if adj_flags != n:
            return

        for nx, ny in neighbors(x, y):
            if not self.flagged[nx][ny] and not self.revealed[nx][ny]:
                self.reveal(nx, ny)

    def _check_win(self):
        total_safe = GRID_W * GRID_H - MINES
        if self.reveal_count >= total_safe and not self.game_over:
            self.win = True
            self._finalize_timer()

            t = self.elapsed_s()
            best = self.best_times.get(current_difficulty, None)
            if t > 0 and (best is None or t < best):
                self.best_times[current_difficulty] = t
                save_best_times(self.best_times)

            for x in range(GRID_W):
                for y in range(GRID_H):
                    if self.mines[x][y] and not self.flagged[x][y]:
                        self.flagged[x][y] = True
            self.flags_left = 0


def compute_layout(screen_w, screen_h):
    scale = min(
        screen_w / (GRID_W * BASE_CELL),
        screen_h / (BASE_TOPBAR + GRID_H * BASE_CELL),
    )
    scale = max(0.5, min(scale, 2.5))

    cell = max(12, int(BASE_CELL * scale))
    topbar = max(28, int(BASE_TOPBAR * scale))

    grid_w = GRID_W * cell
    grid_h = GRID_H * cell

    origin_x = (screen_w - grid_w) // 2
    origin_y = topbar + (screen_h - topbar - grid_h) // 2

    return {
        "scale": scale,
        "cell": cell,
        "topbar": topbar,
        "grid_w": grid_w,
        "grid_h": grid_h,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "screen_w": screen_w,
        "screen_h": screen_h,
    }


def build_fonts(scale):
    title_size = max(16, int(22 * scale))
    small_size = max(10, int(16 * scale))
    btn_size = max(10, int(14 * scale))
    return (
        pygame.font.SysFont("segoe ui", title_size, bold=True),
        pygame.font.SysFont("segoe ui", small_size, bold=False),
        pygame.font.SysFont("segoe ui", btn_size, bold=False),
    )


def cell_from_mouse(mx, my, layout):
    cell = layout["cell"]
    ox, oy = layout["origin_x"], layout["origin_y"]
    gx = (mx - ox) // cell
    gy = (my - oy) // cell
    if in_bounds(gx, gy) and (mx >= ox) and (my >= oy):
        return gx, gy
    return None


def endgame_restart_button_rect(layout):
    w, h = int(220 * layout["scale"]), int(52 * layout["scale"])
    grid_cx = layout["origin_x"] + layout["grid_w"] // 2
    grid_cy = layout["origin_y"] + layout["grid_h"] // 2
    return pygame.Rect(grid_cx - w // 2, grid_cy - h // 2, w, h)


def difficulty_button_rects(layout, btn_font):
    """Return list of (difficulty_name, rect) for top bar buttons."""
    rects = []
    pad = int(6 * layout["scale"])
    h = int(24 * layout["scale"])
    x = int(10 * layout["scale"])
    y = (layout["topbar"] - h) // 2

    for name in DIFFICULTY_ORDER:
        w = btn_font.size(name)[0] + int(16 * layout["scale"])
        rects.append((name, pygame.Rect(x, y, w, h)))
        x += w + pad
    return rects


def draw_flag_icon(screen, rect):
    pole_x = rect.left + 6
    pole_y = rect.top + 3
    pygame.draw.rect(screen, (90, 90, 90), (pole_x, pole_y, 3, rect.height - 6))
    pygame.draw.polygon(
        screen,
        FLAG,
        [(pole_x + 3, rect.top + 6), (rect.right - 4, rect.top + 10), (pole_x + 3, rect.top + 16)],
    )


def fit_text_render(font_name, initial_size, min_size, text, color, max_width, bold=False):
    size = initial_size
    while size >= min_size:
        f = pygame.font.SysFont(font_name, size, bold=bold)
        s = f.render(text, True, color)
        if s.get_width() <= max_width:
            return s, f
        size -= 1
    f = pygame.font.SysFont(font_name, min_size, bold=bold)
    ell = "…"
    t = text
    while t and f.render(t + ell, True, color).get_width() > max_width:
        t = t[:-1]
    s = f.render((t + ell) if t else ell, True, color)
    return s, f


def draw_button(screen, font, rect, label, emphasized=False):
    bg = (90, 90, 105) if not emphasized else (120, 120, 145)
    border = (160, 160, 180) if not emphasized else (235, 235, 245)
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, 2, border_radius=10)
    t = font.render(label, True, (245, 245, 250))
    screen.blit(t, t.get_rect(center=rect.center))


def draw_difficulty_buttons(screen, btn_font, layout, hover_pos):
    rects = difficulty_button_rects(layout, btn_font)
    for name, rect in rects:
        is_current = (name == current_difficulty)
        is_hover = rect.collidepoint(hover_pos) if hover_pos else False
        if is_current:
            bg = (100, 130, 180)
            border = (180, 200, 255)
        elif is_hover:
            bg = (80, 80, 95)
            border = (140, 140, 160)
        else:
            bg = (60, 60, 72)
            border = (100, 100, 115)
        pygame.draw.rect(screen, bg, rect, border_radius=6)
        pygame.draw.rect(screen, border, rect, 1, border_radius=6)
        t = btn_font.render(name, True, (230, 230, 240))
        screen.blit(t, t.get_rect(center=rect.center))
    return rects


def draw_endgame_overlay(screen, font, small_font, game, layout):
    overlay = pygame.Surface((layout["grid_w"], layout["grid_h"]), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, OVERLAY_ALPHA))
    screen.blit(overlay, (layout["origin_x"], layout["origin_y"]))

    title = "You win" if game.win else "Boom"
    title_surf = font.render(title, True, (245, 245, 250))
    title_pos = title_surf.get_rect(center=(
        layout["origin_x"] + layout["grid_w"] // 2,
        layout["origin_y"] + layout["grid_h"] // 2 - int(70 * layout["scale"])
    ))
    screen.blit(title_surf, title_pos)

    btn = endgame_restart_button_rect(layout)
    draw_button(screen, font, btn, "Restart", emphasized=True)

    hint = small_font.render("Click Restart or press R", True, (220, 220, 230))
    hint_pos = hint.get_rect(center=(layout["origin_x"] + layout["grid_w"] // 2, btn.bottom + int(22 * layout["scale"])))
    screen.blit(hint, hint_pos)


def draw(screen, font, small_font, btn_font, game: Minesweeper, hover_cell, mouse_buttons, layout, mouse_pos):
    screen.fill(BG)

    # Top bar
    pygame.draw.rect(screen, PANEL, pygame.Rect(0, 0, layout["screen_w"], layout["topbar"]))

    # Difficulty buttons (left side)
    diff_rects = draw_difficulty_buttons(screen, btn_font, layout, mouse_pos)

    # Calculate right side info area start
    if diff_rects:
        info_start_x = diff_rects[-1][1].right + int(20 * layout["scale"])
    else:
        info_start_x = int(10 * layout["scale"])

    cur_time = game.elapsed_s()
    best = game.get_best_time()
    best_txt = f"{best:.2f}s" if best is not None else "--"
    mode = "ON" if game.first_click_zero_spread else "OFF"

    info = f"Time: {cur_time:.2f}s  Best: {best_txt}  Easy(Z):{mode}"
    flag_block_w = int(64 * layout["scale"])
    max_w = layout["screen_w"] - info_start_x - flag_block_w - int(10 * layout["scale"])

    txt_surf, _ = fit_text_render("segoe ui", int(14 * layout["scale"]), int(10 * layout["scale"]),
                                  info, (220, 220, 230), max_w, bold=False)
    screen.blit(txt_surf, (info_start_x, (layout["topbar"] - txt_surf.get_height()) // 2))

    flag_rect = pygame.Rect(layout["screen_w"] - flag_block_w + 4, (layout["topbar"] - int(22 * layout["scale"])) // 2,
                            int(22 * layout["scale"]), int(22 * layout["scale"]))
    draw_flag_icon(screen, flag_rect)
    flags_surf = small_font.render(str(game.flags_left), True, (220, 220, 230))
    screen.blit(flags_surf, (flag_rect.right + 6, (layout["topbar"] - flags_surf.get_height()) // 2))

    # Grid background
    pygame.draw.rect(
        screen,
        GRID_BG,
        pygame.Rect(layout["origin_x"], layout["origin_y"], layout["grid_w"], layout["grid_h"]),
    )

    cell = layout["cell"]
    ox, oy = layout["origin_x"], layout["origin_y"]

    # Cells
    for x in range(GRID_W):
        for y in range(GRID_H):
            r = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)

            if game.revealed[x][y]:
                base = REVEALED if (x + y) % 2 == 0 else REVEALED_2
                pygame.draw.rect(screen, base, r)
                if game.mines[x][y]:
                    color = (255, 90, 90) if game.exploded == (x, y) else (120, 120, 120)
                    pygame.draw.circle(screen, color, r.center, cell // 4)
                    pygame.draw.circle(screen, MINE, r.center, cell // 7)
                else:
                    n = game.numbers[x][y]
                    if n > 0:
                        t = font.render(str(n), True, NUM_COLORS.get(n, (0, 0, 0)))
                        screen.blit(t, t.get_rect(center=r.center))
            else:
                is_hover = (hover_cell == (x, y))
                base = COVER_HI if is_hover else COVER
                pygame.draw.rect(screen, base, r)

                if game.flagged[x][y]:
                    pole_x = r.left + cell // 2 - 3
                    pygame.draw.rect(screen, (90, 90, 90), (pole_x, r.top + 6, 3, cell - 12))
                    pygame.draw.polygon(
                        screen,
                        FLAG,
                        [(pole_x + 3, r.top + 8), (r.left + cell - 6, r.top + 14), (pole_x + 3, r.top + 20)],
                    )

            pygame.draw.rect(screen, LINE, r, 1)

    # Chord hint highlight
    if hover_cell and mouse_buttons[0] and mouse_buttons[2]:
        x, y = hover_cell
        if game.revealed[x][y] and game.numbers[x][y] > 0:
            r = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)
            pygame.draw.rect(screen, (255, 255, 255), r, 2)

    # End-game overlay
    if game.win or game.game_over:
        draw_endgame_overlay(screen, font, small_font, game, layout)

    return diff_rects


def main():
    global current_difficulty

    pygame.init()
    pygame.display.set_caption("Pysweeper")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    game = Minesweeper()

    hover_cell = None
    end_state_ticks = None
    diff_rects = []

    while True:
        clock.tick(FPS)
        screen_w, screen_h = screen.get_size()
        layout = compute_layout(screen_w, screen_h)
        font, small_font, btn_font = build_fonts(layout["scale"])

        mx, my = pygame.mouse.get_pos()
        hover_cell = cell_from_mouse(mx, my, layout)

        if AUTO_RESTART and (game.win or game.game_over):
            if end_state_ticks is None:
                end_state_ticks = pygame.time.get_ticks()
            elif (pygame.time.get_ticks() - end_state_ticks) / 1000.0 >= AUTO_RESTART_DELAY_S:
                game.reset()
                end_state_ticks = None
        else:
            end_state_ticks = None

        # Draw call moved here to ensure diff_rects is populated before event loop for the frame
        diff_rects = draw(screen, font, small_font, btn_font, game, hover_cell, pygame.mouse.get_pressed(), layout, (mx, my))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_z:
                    game.toggle_first_click_zero_spread()
                    game.reset()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check difficulty buttons
                    clicked_diff = False
                    for name, rect in diff_rects:
                        if rect.collidepoint(event.pos):
                            if name != current_difficulty:
                                current_difficulty = name
                                game.reset()
                                # Window resize removed; grid will refit current window next frame
                            clicked_diff = True
                            break
                    if clicked_diff:
                        continue

                    # If end overlay is showing, allow centered restart button click
                    if (game.win or game.game_over) and endgame_restart_button_rect(layout).collidepoint(event.pos):
                        game.reset()
                        continue

                # Game interaction
                if hover_cell:
                    x, y = hover_cell
                    if event.button == 1:
                        buttons = pygame.mouse.get_pressed(3)
                        if buttons[2]: # Right + Left chord
                            game.chord(x, y)
                        else:
                            game.reveal(x, y)
                    elif event.button == 3:
                        buttons = pygame.mouse.get_pressed(3)
                        if buttons[0]: # Left + Right chord
                            game.chord(x, y)
                        else:
                            game.toggle_flag(x, y)

if __name__ == "__main__":
    main()

