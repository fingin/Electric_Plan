from __future__ import annotations

from math import atan2, degrees, hypot
from typing import Optional, Tuple

import pygame

from electric_plan.models import Conduit, FloorPlanState, Panel, Tool, Wall
from electric_plan.panel_editor import PanelEditor
from electric_plan.settings import (
    BACKGROUND_COLOR,
    FPS,
    GRID_MAJOR_COLOR,
    GRID_MINOR_COLOR,
    GRID_SIZE,
    MAX_ZOOM,
    MIN_ZOOM,
    MUTED_TEXT_COLOR,
    PANEL_COLOR,
    PANEL_SELECTED_COLOR,
    PANEL_SIZE,
    SELECTION_COLOR,
    SIDEBAR_COLOR,
    SIDEBAR_WIDTH,
    TEXT_COLOR,
    WALL_COLOR,
    WALL_PREVIEW_COLOR,
    WALL_THICKNESS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZOOM_STEP,
)


class ElectricPlanApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Electric Plan")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 18)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.state = FloorPlanState()
        self.running = True
        self.panning = False
        self.last_mouse_position: Optional[Tuple[int, int]] = None
        self.current_view = "floor_plan"
        self.panel_editor = PanelEditor()
        self.active_panel_index: Optional[int] = None
        self.floor_tool_buttons: list[tuple[Tool, pygame.Rect, str]] = []

    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                continue

            if event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            if self.current_view == "panel_editor":
                should_close = self.panel_editor.handle_event(event, self.screen.get_size())
                if should_close:
                    self.close_panel_editor()
                continue

            if event.type == pygame.KEYDOWN:
                self.handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_button_down(event)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                self.panning = False
                self.last_mouse_position = None
            elif event.type == pygame.MOUSEMOTION:
                self.handle_mouse_motion(event)

    def handle_keydown(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_1:
            self.state.tool = Tool.SELECT
            self.state.wall_start = None
            self.state.conduit_start = None
        elif event.key == pygame.K_2:
            self.state.tool = Tool.WALL
            self.state.wall_start = None
            self.state.conduit_start = None
        elif event.key == pygame.K_3:
            self.state.tool = Tool.PANEL
            self.state.wall_start = None
            self.state.conduit_start = None
        elif event.key == pygame.K_4:
            self.state.tool = Tool.CONDUIT
            self.state.wall_start = None
            self.state.conduit_start = None
        elif event.key == pygame.K_ESCAPE:
            self.state.wall_start = None
            self.state.conduit_start = None
            self.state.clear_selection()
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self.delete_selected()

    def handle_mouse_button_down(self, event: pygame.event.Event) -> None:
        if event.button == 3:
            self.panning = True
            self.last_mouse_position = event.pos
            return

        if self.handle_sidebar_click(event.pos):
            return

        if self.is_sidebar_click(event.pos):
            return

        if event.button == 1:
            world_pos = self.screen_to_world(event.pos)

            if self.state.tool == Tool.SELECT:
                self.select_at(world_pos)
            elif self.state.tool == Tool.WALL:
                self.handle_wall_click(world_pos)
            elif self.state.tool == Tool.PANEL:
                self.state.panels.append(self.create_panel(world_pos))
                self.state.selected_panel_index = len(self.state.panels) - 1
                self.state.selected_wall_index = None
                self.state.selected_conduit_index = None
            elif self.state.tool == Tool.CONDUIT:
                self.handle_conduit_click(world_pos)

        elif event.button in (4, 5):
            self.zoom_at(event.pos, 1 if event.button == 4 else -1)

    def handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.panning and self.last_mouse_position is not None:
            dx = event.pos[0] - self.last_mouse_position[0]
            dy = event.pos[1] - self.last_mouse_position[1]
            ox, oy = self.state.camera_offset
            self.state.camera_offset = (ox + dx, oy + dy)
            self.last_mouse_position = event.pos

    def handle_wall_click(self, world_pos: Tuple[float, float]) -> None:
        snapped = self.snap(world_pos)
        if self.state.wall_start is None:
            self.state.wall_start = snapped
        else:
            if snapped != self.state.wall_start:
                self.state.walls.append(Wall(start=self.state.wall_start, end=snapped))
                self.state.selected_wall_index = len(self.state.walls) - 1
                self.state.selected_panel_index = None
            self.state.wall_start = None

    def handle_conduit_click(self, world_pos: Tuple[float, float]) -> None:
        snapped = self.snap(world_pos)
        if self.state.conduit_start is None:
            self.state.conduit_start = snapped
            return

        if snapped != self.state.conduit_start:
            self.state.conduits.append(Conduit(start=self.state.conduit_start, end=snapped))
            self.state.selected_conduit_index = len(self.state.conduits) - 1
            self.state.selected_panel_index = None
            self.state.selected_wall_index = None
        self.state.conduit_start = None

    def delete_selected(self) -> None:
        if self.state.selected_panel_index is not None:
            del self.state.panels[self.state.selected_panel_index]
            self.state.selected_panel_index = None
        elif self.state.selected_conduit_index is not None:
            del self.state.conduits[self.state.selected_conduit_index]
            self.state.selected_conduit_index = None
        elif self.state.selected_wall_index is not None:
            del self.state.walls[self.state.selected_wall_index]
            self.state.selected_wall_index = None

    def select_at(self, world_pos: Tuple[float, float]) -> None:
        self.state.clear_selection()

        for index, panel in enumerate(self.state.panels):
            if hypot(world_pos[0] - panel.position[0], world_pos[1] - panel.position[1]) <= PANEL_SIZE:
                self.state.selected_panel_index = index
                self.open_panel_editor(index)
                return

        threshold = 12 / self.state.zoom
        for index, conduit in enumerate(self.state.conduits):
            if self.distance_to_segment(world_pos, conduit.start, conduit.end) <= threshold:
                self.state.selected_conduit_index = index
                return

        for index, wall in enumerate(self.state.walls):
            if self.distance_to_segment(world_pos, wall.start, wall.end) <= threshold:
                self.state.selected_wall_index = index
                return

    def draw(self) -> None:
        if self.current_view == "panel_editor":
            self.panel_editor.draw(self.screen)
            pygame.display.flip()
            return

        self.screen.fill(BACKGROUND_COLOR)
        canvas_rect = self.get_canvas_rect()
        pygame.draw.rect(self.screen, BACKGROUND_COLOR, canvas_rect)
        self.draw_grid(canvas_rect)
        self.draw_walls()
        self.draw_wall_preview()
        self.draw_conduits()
        self.draw_conduit_preview()
        self.draw_panels()
        self.draw_sidebar()
        pygame.display.flip()

    def draw_grid(self, rect: pygame.Rect) -> None:
        world_top_left = self.screen_to_world((rect.left, rect.top))
        world_bottom_right = self.screen_to_world((rect.right, rect.bottom))
        start_x = int(world_top_left[0] // GRID_SIZE) - 1
        end_x = int(world_bottom_right[0] // GRID_SIZE) + 1
        start_y = int(world_top_left[1] // GRID_SIZE) - 1
        end_y = int(world_bottom_right[1] // GRID_SIZE) + 1

        for gx in range(start_x, end_x + 1):
            color = GRID_MAJOR_COLOR if gx % 4 == 0 else GRID_MINOR_COLOR
            x = self.world_to_screen((gx * GRID_SIZE, 0))[0]
            pygame.draw.line(self.screen, color, (x, rect.top), (x, rect.bottom))

        for gy in range(start_y, end_y + 1):
            color = GRID_MAJOR_COLOR if gy % 4 == 0 else GRID_MINOR_COLOR
            y = self.world_to_screen((0, gy * GRID_SIZE))[1]
            pygame.draw.line(self.screen, color, (rect.left, y), (rect.right, y))

    def draw_walls(self) -> None:
        for index, wall in enumerate(self.state.walls):
            color = SELECTION_COLOR if index == self.state.selected_wall_index else WALL_COLOR
            pygame.draw.line(
                self.screen,
                color,
                self.world_to_screen(wall.start),
                self.world_to_screen(wall.end),
                max(2, int(WALL_THICKNESS * self.state.zoom)),
            )

    def draw_wall_preview(self) -> None:
        if self.state.wall_start is None or self.state.tool != Tool.WALL:
            return

        mouse_pos = pygame.mouse.get_pos()
        if self.is_sidebar_click(mouse_pos):
            return

        start = self.world_to_screen(self.state.wall_start)
        end = self.world_to_screen(self.snap(self.screen_to_world(mouse_pos)))
        pygame.draw.line(self.screen, WALL_PREVIEW_COLOR, start, end, max(1, int(2 * self.state.zoom)))

    def draw_panels(self) -> None:
        for index, panel in enumerate(self.state.panels):
            center = self.world_to_screen(panel.position)
            color = PANEL_SELECTED_COLOR if index == self.state.selected_panel_index else PANEL_COLOR
            panel_surface = pygame.Surface((PANEL_SIZE * 2, int(PANEL_SIZE * 1.4)), pygame.SRCALPHA)
            panel_rect = panel_surface.get_rect()
            pygame.draw.rect(panel_surface, color, panel_rect, border_radius=4)
            pygame.draw.rect(panel_surface, BACKGROUND_COLOR, panel_rect, width=2, border_radius=4)
            rotated_surface = pygame.transform.rotate(panel_surface, -panel.rotation)
            rotated_rect = rotated_surface.get_rect(center=center)
            self.screen.blit(rotated_surface, rotated_rect)

    def draw_conduits(self) -> None:
        for index, conduit in enumerate(self.state.conduits):
            color = PANEL_SELECTED_COLOR if index == self.state.selected_conduit_index else (130, 126, 108)
            pygame.draw.line(
                self.screen,
                color,
                self.world_to_screen(conduit.start),
                self.world_to_screen(conduit.end),
                max(2, int(6 * self.state.zoom)),
            )
            for endpoint in (conduit.start, conduit.end):
                pygame.draw.circle(self.screen, BACKGROUND_COLOR, self.world_to_screen(endpoint), max(3, int(4 * self.state.zoom)))

    def draw_conduit_preview(self) -> None:
        if self.state.conduit_start is None or self.state.tool != Tool.CONDUIT:
            return
        mouse_pos = pygame.mouse.get_pos()
        if self.is_sidebar_click(mouse_pos):
            return
        pygame.draw.line(
            self.screen,
            PANEL_COLOR,
            self.world_to_screen(self.state.conduit_start),
            self.world_to_screen(self.snap(self.screen_to_world(mouse_pos))),
            max(1, int(4 * self.state.zoom)),
        )

    def draw_sidebar(self) -> None:
        width, height = self.screen.get_size()
        panel_rect = pygame.Rect(width - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, height)
        pygame.draw.rect(self.screen, SIDEBAR_COLOR, panel_rect)
        self.floor_tool_buttons = []

        tool_specs = [
            (Tool.SELECT, "Select"),
            (Tool.WALL, "Wall"),
            (Tool.PANEL, "Panel"),
            (Tool.CONDUIT, "Conduit"),
        ]
        button_y = 18
        for tool, label in tool_specs:
            button_rect = pygame.Rect(panel_rect.left + 18, button_y, 120, 28)
            button_color = PANEL_COLOR if self.state.tool == tool else GRID_MAJOR_COLOR
            pygame.draw.rect(self.screen, button_color, button_rect, border_radius=6)
            pygame.draw.rect(self.screen, BACKGROUND_COLOR, button_rect, width=2, border_radius=6)
            text_surface = self.small_font.render(label, True, BACKGROUND_COLOR if self.state.tool == tool else TEXT_COLOR)
            self.screen.blit(text_surface, (button_rect.x + 12, button_rect.y + 6))
            self.floor_tool_buttons.append((tool, button_rect, label))
            button_y += 34

        lines = [
            ("Electric Plan", self.font, TEXT_COLOR),
            ("Floor plan prototype", self.small_font, MUTED_TEXT_COLOR),
            ("", self.small_font, TEXT_COLOR),
            (f"Active tool: {self.state.tool.value.title()}", self.font, TEXT_COLOR),
            ("1 Select", self.small_font, MUTED_TEXT_COLOR),
            ("2 Draw walls", self.small_font, MUTED_TEXT_COLOR),
            ("3 Place panel", self.small_font, MUTED_TEXT_COLOR),
            ("4 Draw conduit", self.small_font, MUTED_TEXT_COLOR),
            ("Click panel to open editor", self.small_font, MUTED_TEXT_COLOR),
            ("", self.small_font, TEXT_COLOR),
            ("Navigation", self.font, TEXT_COLOR),
            ("Right drag to pan", self.small_font, MUTED_TEXT_COLOR),
            ("Mouse wheel to zoom", self.small_font, MUTED_TEXT_COLOR),
            ("", self.small_font, TEXT_COLOR),
            ("Scene", self.font, TEXT_COLOR),
            (f"Walls: {len(self.state.walls)}", self.small_font, MUTED_TEXT_COLOR),
            (f"Panels: {len(self.state.panels)}", self.small_font, MUTED_TEXT_COLOR),
            (f"Conduits: {len(self.state.conduits)}", self.small_font, MUTED_TEXT_COLOR),
        ]

        selected_label = self.get_selected_label()
        if selected_label:
            lines.extend(
                [
                    ("", self.small_font, TEXT_COLOR),
                    ("Selection", self.font, TEXT_COLOR),
                    (selected_label, self.small_font, MUTED_TEXT_COLOR),
                    ("Delete / Backspace removes selection", self.small_font, MUTED_TEXT_COLOR),
                ]
            )

        y = button_y + 8
        y = 24
        for text, font, color in lines:
            surface = font.render(text, True, color)
            self.screen.blit(surface, (panel_rect.left + 20, y))
            y += 28 if font == self.font else 22

    def get_selected_label(self) -> str:
        if self.state.selected_panel_index is not None:
            panel = self.state.panels[self.state.selected_panel_index]
            return f"{panel.label} at {self.format_point(panel.position)} ({int(panel.rotation)}°)"

        if self.state.selected_conduit_index is not None:
            conduit = self.state.conduits[self.state.selected_conduit_index]
            return f"{conduit.label} {self.format_point(conduit.start)} → {self.format_point(conduit.end)}"

        if self.state.selected_wall_index is not None:
            wall = self.state.walls[self.state.selected_wall_index]
            return f"Wall {self.format_point(wall.start)} → {self.format_point(wall.end)}"

        return ""

    def format_point(self, point: Tuple[float, float]) -> str:
        return f"({int(point[0])}, {int(point[1])})"

    def zoom_at(self, mouse_pos: Tuple[int, int], direction: int) -> None:
        previous_zoom = self.state.zoom
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, previous_zoom + direction * ZOOM_STEP))
        if new_zoom == previous_zoom:
            return

        world_before = self.screen_to_world(mouse_pos)
        self.state.zoom = new_zoom
        world_after = self.screen_to_world(mouse_pos)
        ox, oy = self.state.camera_offset
        self.state.camera_offset = (
            ox + (world_after[0] - world_before[0]) * new_zoom,
            oy + (world_after[1] - world_before[1]) * new_zoom,
        )

    def snap(self, point: Tuple[float, float]) -> Tuple[float, float]:
        return (
            round(point[0] / GRID_SIZE) * GRID_SIZE,
            round(point[1] / GRID_SIZE) * GRID_SIZE,
        )

    def create_panel(self, world_pos: Tuple[float, float]) -> Panel:
        snapped_position = self.snap(world_pos)
        nearest_wall = self.find_nearest_wall(snapped_position)
        if nearest_wall is None:
            return Panel(position=snapped_position)

        wall, snapped_to_wall, _distance = nearest_wall
        return Panel(
            position=snapped_to_wall,
            rotation=self.wall_rotation(wall),
        )

    def find_nearest_wall(
        self,
        point: Tuple[float, float],
        max_distance: float = GRID_SIZE * 1.5,
    ) -> Optional[Tuple[Wall, Tuple[float, float], float]]:
        nearest: Optional[Tuple[Wall, Tuple[float, float], float]] = None
        for wall in self.state.walls:
            projection, distance = self.project_point_to_segment(point, wall.start, wall.end)
            if distance > max_distance:
                continue

            snapped_projection = self.snap(projection)
            candidate = (wall, snapped_projection, distance)
            if nearest is None or distance < nearest[2]:
                nearest = candidate

        return nearest

    @staticmethod
    def wall_rotation(wall: Wall) -> float:
        dx = wall.end[0] - wall.start[0]
        dy = wall.end[1] - wall.start[1]
        return degrees(atan2(dy, dx))

    def world_to_screen(self, point: Tuple[float, float]) -> Tuple[int, int]:
        ox, oy = self.state.camera_offset
        return int(point[0] * self.state.zoom + ox), int(point[1] * self.state.zoom + oy)

    def screen_to_world(self, point: Tuple[int, int]) -> Tuple[float, float]:
        ox, oy = self.state.camera_offset
        return (point[0] - ox) / self.state.zoom, (point[1] - oy) / self.state.zoom

    def get_canvas_rect(self) -> pygame.Rect:
        width, height = self.screen.get_size()
        return pygame.Rect(0, 0, width - SIDEBAR_WIDTH, height)

    def is_sidebar_click(self, position: Tuple[int, int]) -> bool:
        return position[0] >= self.get_canvas_rect().right

    @staticmethod
    def distance_to_segment(point: Tuple[float, float], start: Tuple[float, float], end: Tuple[float, float]) -> float:
        _, distance = ElectricPlanApp.project_point_to_segment(point, start, end)
        return distance

    @staticmethod
    def project_point_to_segment(
        point: Tuple[float, float],
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Tuple[Tuple[float, float], float]:
        px, py = point
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            return (x1, y1), hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        return (nearest_x, nearest_y), hypot(px - nearest_x, py - nearest_y)

    def open_panel_editor(self, panel_index: int) -> None:
        if panel_index < 0 or panel_index >= len(self.state.panels):
            return
        self.active_panel_index = panel_index
        panel = self.state.panels[panel_index]
        self.panel_editor.reset_for_panel(panel.label)
        self.current_view = "panel_editor"

    def close_panel_editor(self) -> None:
        self.current_view = "floor_plan"
        self.active_panel_index = None
        if self.panel_editor.request_floor_plan_conduit:
            self.state.tool = Tool.CONDUIT
            self.state.conduit_start = None
            self.panel_editor.request_floor_plan_conduit = False

    def handle_sidebar_click(self, position: Tuple[int, int]) -> bool:
        if not self.is_sidebar_click(position):
            return False

        if not self.floor_tool_buttons:
            return False

        for tool, rect, _label in self.floor_tool_buttons:
            if rect.collidepoint(position):
                self.state.tool = tool
                self.state.wall_start = None
                self.state.conduit_start = None
                return True
        return False


def main() -> None:
    ElectricPlanApp().run()
