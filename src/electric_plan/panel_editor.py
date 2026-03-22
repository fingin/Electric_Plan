from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pygame

Vec2 = pygame.Vector2
Color = tuple[int, int, int]

BG = (26, 28, 34)
CABINET_BG = (92, 96, 108)
CABINET_INNER = (122, 126, 138)
CABINET_BORDER = (46, 48, 56)
BUS_COLOR_A = (170, 92, 48)
BUS_COLOR_B = (165, 80, 38)
NEUTRAL_BAR = (130, 170, 210)
GROUND_BAR = (90, 170, 110)
BREAKER_BODY = (35, 38, 46)
BREAKER_FACE = (70, 78, 92)
BREAKER_HANDLE_ON = (220, 220, 225)
BREAKER_HANDLE_OFF = (110, 110, 120)
TEXT = (232, 235, 240)
MUTED = (190, 195, 205)
ACCENT = (255, 205, 70)
HOT = (255, 210, 100)
WIRE_RED = (220, 70, 70)
WIRE_BLUE = (70, 110, 220)
WIRE_BLACK = (30, 30, 30)
WIRE_WHITE = (235, 235, 235)
WIRE_GREEN = (60, 185, 95)
WIRE_ORANGE = (225, 130, 45)
WIRE_PURPLE = (150, 80, 185)
PANEL_SLOT_LINE = (150, 155, 165)
BLUEPRINT = (92, 165, 255)
BLUEPRINT_FILL = (92, 165, 255, 36)
SIDEBAR_BG = (30, 32, 40)
SIDEBAR_BORDER = (65, 70, 82)
TOPBAR_BG = (19, 22, 29)
BUTTON_BG = (58, 66, 80)
BUTTON_BORDER = (100, 112, 130)


@dataclass
class Camera:
    offset: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    zoom: float = 1.0

    def world_to_screen(self, point: Vec2) -> Vec2:
        return (point + self.offset) * self.zoom

    def screen_to_world(self, point: tuple[int, int]) -> Vec2:
        return Vec2(point) / self.zoom - self.offset


@dataclass
class Terminal:
    id: str
    pos: tuple[float, float]
    role: str
    label: str
    part_id: int

    def world_pos(self) -> Vec2:
        return Vec2(self.pos)


@dataclass
class Wire:
    id: int
    start_terminal: str
    end_terminal: str
    path: List[tuple[float, float]]
    color: Color
    label: str = ""
    gauge: str = "12 AWG"


@dataclass
class Part:
    id: int
    kind: str
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    props: Dict = field(default_factory=dict)
    selected: bool = False

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def contains(self, point: Vec2) -> bool:
        return self.rect().collidepoint(point.x, point.y)


class PanelWorld:
    def __init__(self) -> None:
        self.parts: List[Part] = []
        self.terminals: Dict[str, Terminal] = {}
        self.wires: List[Wire] = []
        self.next_part_id = 1
        self.next_wire_id = 1
        self.selected_part: Optional[Part] = None
        self.grid_snap = True
        self.grid_size = 10
        self.current_tool = "pointer"
        self.pending_wire_terminal: Optional[str] = None
        self.pending_wire_points: List[tuple[float, float]] = []
        self.pending_wire_color: Color = WIRE_RED
        self.dragging_part = False
        self.drag_offset = Vec2(0, 0)
        self.panning = False
        self.show_blueprint = True
        self.creating_zone = False
        self.zone_start: Optional[Vec2] = None
        self.temp_zone_rect: Optional[pygame.Rect] = None
        self.status = "Ready"
        self.panel_slot_height = 46
        self.panel_slot_gap = 8
        self.slot_count_per_side = 8
        self.build_default_scene()

    def snap(self, point: Vec2) -> Vec2:
        if not self.grid_snap:
            return point
        grid = self.grid_size
        return Vec2(round(point.x / grid) * grid, round(point.y / grid) * grid)

    def add_part(self, kind: str, x: float, y: float, w: float, h: float, label: str = "", props: Optional[Dict] = None) -> Part:
        part = Part(self.next_part_id, kind, x, y, w, h, label, props or {})
        self.next_part_id += 1
        self.parts.append(part)
        return part

    def add_terminal(self, part: Part, x: float, y: float, role: str, label: str) -> str:
        terminal_id = f"{part.id}:{label.lower().replace(' ', '_')}:{len(self.terminals)}"
        self.terminals[terminal_id] = Terminal(terminal_id, (x, y), role, label, part.id)
        return terminal_id

    def select_part(self, part: Optional[Part]) -> None:
        for existing_part in self.parts:
            existing_part.selected = False
        self.selected_part = part
        if part is not None:
            part.selected = True

    def delete_selected(self) -> None:
        if self.selected_part is None:
            return

        part_id = self.selected_part.id
        self.parts = [part for part in self.parts if part.id != part_id]
        removed_terminals = [terminal_id for terminal_id, terminal in self.terminals.items() if terminal.part_id == part_id]
        for terminal_id in removed_terminals:
            self.terminals.pop(terminal_id, None)
        self.wires = [wire for wire in self.wires if wire.start_terminal not in removed_terminals and wire.end_terminal not in removed_terminals]
        self.selected_part = None
        self.status = "Deleted selected part"

    def build_default_scene(self) -> None:
        self.parts.clear()
        self.terminals.clear()
        self.wires.clear()
        self.next_part_id = 1
        self.next_wire_id = 1
        self.selected_part = None

        panel = self.add_part(
            "panel",
            100,
            70,
            980,
            780,
            "Main Panel",
            {
                "slots_per_side": 8,
                "main_amps": 200,
                "system": "split phase",
                "left_bus_role": "L1",
                "right_bus_role": "L2",
            },
        )
        self.make_panel_structure(panel)
        self.add_part("zone", 60, 40, 1060, 840, "Panel Working Envelope", {"blueprint": True})
        self.select_part(panel)
        self.status = "Default panel created"

    def make_panel_structure(self, panel: Part) -> None:
        rect = panel.rect()
        feeder = self.add_part("feeder_lugs", rect.centerx - 120, rect.y + 20, 240, 70, "Service Feed")
        l1_top = self.add_terminal(feeder, feeder.x + 60, feeder.y + 18, "hot", "L1 FEED")
        neutral_top = self.add_terminal(feeder, feeder.x + 120, feeder.y + 18, "neutral", "N FEED")
        l2_top = self.add_terminal(feeder, feeder.x + 180, feeder.y + 18, "hot", "L2 FEED")
        ground_top = self.add_terminal(feeder, feeder.x + 120, feeder.y + 52, "ground", "G FEED")
        feeder.props.update({"energized": True, "l1": l1_top, "l2": l2_top, "neutral": neutral_top, "ground": ground_top})

        left_bus = self.add_part("busbar", rect.centerx - 66, rect.y + 115, 16, 560, "L1 BUS", {"role": "L1"})
        right_bus = self.add_part("busbar", rect.centerx + 50, rect.y + 115, 16, 560, "L2 BUS", {"role": "L2"})
        left_bus_input = self.add_terminal(left_bus, left_bus.x + 8, left_bus.y + 8, "hot", "L1 IN")
        right_bus_input = self.add_terminal(right_bus, right_bus.x + 8, right_bus.y + 8, "hot", "L2 IN")
        left_bus.props["main_terminal"] = left_bus_input
        right_bus.props["main_terminal"] = right_bus_input

        neutral_bar = self.add_part("neutral_bar", rect.x + 38, rect.y + 120, 24, 520, "NEUTRAL BAR")
        ground_bar = self.add_part("ground_bar", rect.right - 62, rect.y + 120, 24, 520, "GROUND BAR")
        neutral_bar.props["main_terminal"] = self.add_terminal(neutral_bar, neutral_bar.x + 12, neutral_bar.y + 10, "neutral", "N BAR TOP")
        ground_bar.props["main_terminal"] = self.add_terminal(ground_bar, ground_bar.x + 12, ground_bar.y + 10, "ground", "G BAR TOP")

        self.add_wire(l1_top, left_bus_input, [(left_bus.x + 8, feeder.y + 18)], WIRE_BLACK, "L1 feeder", "2/0")
        self.add_wire(l2_top, right_bus_input, [(right_bus.x + 8, feeder.y + 18)], WIRE_RED, "L2 feeder", "2/0")
        self.add_wire(neutral_top, neutral_bar.props["main_terminal"], [(neutral_bar.x + 12, feeder.y + 18)], WIRE_WHITE, "Neutral feeder", "2/0")
        self.add_wire(ground_top, ground_bar.props["main_terminal"], [(ground_bar.x + 12, feeder.y + 52)], WIRE_GREEN, "Ground feeder", "2/0")

        self.create_breaker_stack(panel, left_bus, right_bus, neutral_bar, ground_bar)

    def create_breaker_stack(self, panel: Part, left_bus: Part, right_bus: Part, neutral_bar: Part, ground_bar: Part) -> None:
        rect = panel.rect()
        top_y = rect.y + 145
        left_x = rect.centerx - 165
        right_x = rect.centerx + 20
        for index in range(self.slot_count_per_side):
            y = top_y + index * (self.panel_slot_height + self.panel_slot_gap)
            left_breaker = self.add_breaker(left_x, y, side="left", slot=index + 1, bus=left_bus, neutral=neutral_bar, ground=ground_bar)
            right_breaker = self.add_breaker(right_x, y, side="right", slot=index + 1, bus=right_bus, neutral=neutral_bar, ground=ground_bar)
            if index < 4:
                self.auto_wire_branch(left_breaker, neutral_bar, ground_bar, color_hot=WIRE_BLUE if index % 2 else WIRE_RED)
                self.auto_wire_branch(right_breaker, neutral_bar, ground_bar, color_hot=WIRE_RED if index % 2 else WIRE_BLUE)

    def add_breaker(self, x: float, y: float, side: str, slot: int, bus: Part, neutral: Part, ground: Part) -> Part:
        breaker = self.add_part(
            "breaker",
            x,
            y,
            130,
            42,
            f"{side.upper()} {slot}",
            {
                "state": "closed",
                "tripped": False,
                "amps": 20,
                "pole_count": 1,
                "side": side,
                "slot": slot,
                "bus_part_id": bus.id,
                "circuit_no": slot * 2 - 1 if side == "left" else slot * 2,
            },
        )
        line_terminal = self.add_terminal(breaker, x + 16, y + 21, "hot", f"LINE {breaker.props['circuit_no']}")
        load_terminal = self.add_terminal(breaker, x + 114, y + 21, "hot", f"LOAD {breaker.props['circuit_no']}")
        breaker.props["line_terminal"] = line_terminal
        breaker.props["load_terminal"] = load_terminal

        bus_terminal = self.add_terminal(bus, bus.x + 8, y + 21, "hot", f"BUS TAP {breaker.props['circuit_no']}")
        self.add_wire(bus_terminal, line_terminal, [], WIRE_ORANGE, f"Bus tap {breaker.props['circuit_no']}", "bus")

        breaker.props["neutral_terminal"] = self.add_terminal(neutral, neutral.x + 12, y + 10, "neutral", f"N {breaker.props['circuit_no']}")
        breaker.props["ground_terminal"] = self.add_terminal(ground, ground.x + 12, y + 10, "ground", f"G {breaker.props['circuit_no']}")
        return breaker

    def auto_wire_branch(self, breaker: Part, neutral: Part, ground: Part, color_hot: Color = WIRE_RED) -> None:
        branch = self.add_part(
            "load_stub",
            breaker.x + breaker.w + 170,
            breaker.y - 4,
            110,
            50,
            f"LOAD {breaker.props['circuit_no']}",
            {"circuit_no": breaker.props["circuit_no"]},
        )
        hot_in = self.add_terminal(branch, branch.x + 10, branch.y + 16, "hot", f"HOT IN {breaker.props['circuit_no']}")
        neutral_in = self.add_terminal(branch, branch.x + 10, branch.y + 28, "neutral", f"N IN {breaker.props['circuit_no']}")
        ground_in = self.add_terminal(branch, branch.x + 10, branch.y + 40, "ground", f"G IN {breaker.props['circuit_no']}")

        bend_x = breaker.x + breaker.w + 55
        self.add_wire(breaker.props["load_terminal"], hot_in, [(bend_x, breaker.y + breaker.h / 2), (bend_x, branch.y + 16)], color_hot, f"Branch hot {breaker.props['circuit_no']}")
        self.add_wire(breaker.props["neutral_terminal"], neutral_in, [(branch.x - 55, neutral.y + 20), (branch.x - 55, branch.y + 28)], WIRE_WHITE, f"Branch neutral {breaker.props['circuit_no']}")
        self.add_wire(breaker.props["ground_terminal"], ground_in, [(branch.x + 70, ground.y + 20), (branch.x + 70, branch.y + 40)], WIRE_GREEN, f"Branch ground {breaker.props['circuit_no']}")

    def add_wire(self, start: str, end: str, path: List[tuple[float, float]], color: Color, label: str = "", gauge: str = "12 AWG") -> None:
        self.wires.append(Wire(self.next_wire_id, start, end, path[:], color, label, gauge))
        self.next_wire_id += 1

    def get_part_at(self, position: Vec2) -> Optional[Part]:
        for part in reversed(self.parts):
            if part.kind == "zone":
                continue
            if part.contains(position):
                return part
        return None

    def get_terminal_at(self, position: Vec2, radius: float = 12) -> Optional[str]:
        for terminal_id, terminal in reversed(list(self.terminals.items())):
            if terminal.world_pos().distance_to(position) <= radius:
                return terminal_id
        return None

    def terminal_pos(self, terminal_id: str) -> Optional[Vec2]:
        terminal = self.terminals.get(terminal_id)
        return terminal.world_pos() if terminal is not None else None

    def toggle_breaker(self, breaker: Part) -> None:
        if breaker.kind != "breaker":
            return
        if breaker.props.get("tripped"):
            breaker.props["tripped"] = False
        breaker.props["state"] = "open" if breaker.props.get("state") == "closed" else "closed"
        self.status = f"Breaker {breaker.props.get('circuit_no')} toggled"

    def graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for wire in self.wires:
            graph.setdefault(wire.start_terminal, []).append(wire.end_terminal)
            graph.setdefault(wire.end_terminal, []).append(wire.start_terminal)

        for part in self.parts:
            if part.kind == "breaker":
                line_terminal = part.props.get("line_terminal")
                load_terminal = part.props.get("load_terminal")
                if line_terminal and load_terminal and part.props.get("state") == "closed" and not part.props.get("tripped"):
                    graph.setdefault(line_terminal, []).append(load_terminal)
                    graph.setdefault(load_terminal, []).append(line_terminal)
            elif part.kind in {"busbar", "neutral_bar", "ground_bar", "feeder_lugs", "load_stub"}:
                terminal_ids = [terminal_id for terminal_id, terminal in self.terminals.items() if terminal.part_id == part.id]
                for index, terminal_id in enumerate(terminal_ids):
                    for other_terminal_id in terminal_ids[index + 1 :]:
                        if self.terminals[terminal_id].role == self.terminals[other_terminal_id].role:
                            graph.setdefault(terminal_id, []).append(other_terminal_id)
                            graph.setdefault(other_terminal_id, []).append(terminal_id)
        return graph

    def source_terminals(self) -> List[str]:
        source_ids: List[str] = []
        for part in self.parts:
            if part.kind == "feeder_lugs" and part.props.get("energized"):
                for key in ("l1", "l2", "neutral", "ground"):
                    terminal_id = part.props.get(key)
                    if terminal_id:
                        source_ids.append(terminal_id)
        return source_ids

    def is_terminal_hot(self, terminal_id: str) -> bool:
        terminal = self.terminals.get(terminal_id)
        if terminal is None:
            return False

        sources = [source_id for source_id in self.source_terminals() if self.terminals[source_id].role == terminal.role]
        if not sources:
            return False

        graph = self.graph()
        stack = sources[:]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for next_terminal in graph.get(current, []):
                if next_terminal not in seen:
                    stack.append(next_terminal)
        return terminal_id in seen

    def save(self, path: str = "panel_blueprint.json") -> None:
        payload = {
            "parts": [
                {
                    "id": part.id,
                    "kind": part.kind,
                    "x": part.x,
                    "y": part.y,
                    "w": part.w,
                    "h": part.h,
                    "label": part.label,
                    "props": part.props,
                }
                for part in self.parts
            ],
            "terminals": [
                {
                    "id": terminal.id,
                    "pos": list(terminal.pos),
                    "role": terminal.role,
                    "label": terminal.label,
                    "part_id": terminal.part_id,
                }
                for terminal in self.terminals.values()
            ],
            "wires": [
                {
                    "id": wire.id,
                    "start_terminal": wire.start_terminal,
                    "end_terminal": wire.end_terminal,
                    "path": [list(point) for point in wire.path],
                    "color": list(wire.color),
                    "label": wire.label,
                    "gauge": wire.gauge,
                }
                for wire in self.wires
            ],
            "next_part_id": self.next_part_id,
            "next_wire_id": self.next_wire_id,
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        self.status = f"Saved {path}"

    def load(self, path: str = "panel_blueprint.json") -> None:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        self.parts = [Part(**raw_part) for raw_part in payload["parts"]]
        self.terminals = {
            raw_terminal["id"]: Terminal(
                raw_terminal["id"],
                tuple(raw_terminal["pos"]),
                raw_terminal["role"],
                raw_terminal["label"],
                raw_terminal["part_id"],
            )
            for raw_terminal in payload["terminals"]
        }
        self.wires = [
            Wire(
                raw_wire["id"],
                raw_wire["start_terminal"],
                raw_wire["end_terminal"],
                [tuple(point) for point in raw_wire["path"]],
                tuple(raw_wire["color"]),
                raw_wire.get("label", ""),
                raw_wire.get("gauge", "12 AWG"),
            )
            for raw_wire in payload["wires"]
        ]
        self.next_part_id = payload.get("next_part_id", 1)
        self.next_wire_id = payload.get("next_wire_id", 1)
        self.select_part(None)
        self.status = f"Loaded {path}"


class PanelEditor:
    def __init__(self) -> None:
        self.world = PanelWorld()
        self.camera = Camera()
        self.font = pygame.font.SysFont("consolas", 15)
        self.small_font = pygame.font.SysFont("consolas", 12)
        self.big_font = pygame.font.SysFont("consolas", 22)
        self.topbar_height = 52
        self.sidebar_width = 360
        self.back_button_rect = pygame.Rect(0, 0, 120, 32)
        self.tool_buttons: list[tuple[str, pygame.Rect]] = []
        self.part_buttons: list[tuple[str, pygame.Rect]] = []
        self.wire_role_cycle = ["hot", "neutral", "ground"]
        self.manual_wire_role = "hot"
        self.request_floor_plan_conduit = False

    def reset_for_panel(self, panel_label: str) -> None:
        self.world.build_default_scene()
        panel = next((part for part in self.world.parts if part.kind == "panel"), None)
        if panel is not None:
            panel.label = panel_label or panel.label
        self.world.status = f"Opened panel view for {panel_label or 'panel'}"
        self.camera = Camera()
        self.request_floor_plan_conduit = False

    def handle_event(self, event: pygame.event.Event, screen_size: tuple[int, int]) -> bool:
        mouse_screen = Vec2(pygame.mouse.get_pos())
        mouse_world = self.camera.screen_to_world((int(mouse_screen.x), int(mouse_screen.y)))

        if event.type == pygame.KEYDOWN:
            return self.handle_keydown(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.handle_mouse_button_down(event, mouse_screen, mouse_world, screen_size)
        if event.type == pygame.MOUSEBUTTONUP:
            self.handle_mouse_button_up(event)
        elif event.type == pygame.MOUSEMOTION:
            self.handle_mouse_motion(event, mouse_world)
        return False

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_ESCAPE:
            if self.world.pending_wire_terminal or self.world.creating_zone:
                self.cancel_current_action()
                return False
            return True
        if event.key == pygame.K_1:
            self.set_tool("pointer")
        elif event.key == pygame.K_2:
            self.set_tool("wire")
        elif event.key == pygame.K_3:
            self.set_tool("zone")
        elif event.key == pygame.K_4:
            self.world.build_default_scene()
        elif event.key == pygame.K_5:
            self.set_tool("add_load")
        elif event.key == pygame.K_g:
            self.world.grid_snap = not self.world.grid_snap
            self.world.status = f"Grid snap {'ON' if self.world.grid_snap else 'OFF'}"
        elif event.key == pygame.K_b:
            self.world.show_blueprint = not self.world.show_blueprint
            self.world.status = f"Blueprint {'ON' if self.world.show_blueprint else 'OFF'}"
        elif event.key == pygame.K_TAB and self.world.current_tool == "wire":
            self.cycle_wire_role()
        elif event.key == pygame.K_z and self.world.current_tool == "wire" and self.world.pending_wire_points:
            self.world.pending_wire_points.pop()
            self.world.status = "Removed last wire waypoint"
        elif event.key == pygame.K_s:
            self.world.save()
        elif event.key == pygame.K_l:
            self.world.load()
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self.world.delete_selected()
        return False

    def handle_mouse_button_down(
        self,
        event: pygame.event.Event,
        mouse_screen: Vec2,
        mouse_world: Vec2,
        screen_size: tuple[int, int],
    ) -> bool:
        if event.button == 1:
            if self.back_button_rect.collidepoint(mouse_screen.x, mouse_screen.y):
                return True
            sidebar_action = self.handle_sidebar_click(mouse_screen)
            if sidebar_action == "close":
                return True
            if sidebar_action:
                return False
            if self.is_sidebar_click(mouse_screen, screen_size):
                return False
            self.handle_left_click(mouse_world)
        elif event.button == 2:
            self.world.panning = True
        elif event.button == 3:
            if self.world.current_tool == "wire" and self.world.pending_wire_points:
                self.world.pending_wire_points.pop()
                self.world.status = "Removed last wire waypoint"
            else:
                self.world.pending_wire_terminal = None
                self.world.pending_wire_points = []
                self.world.dragging_part = False
                self.world.status = "Canceled wire"
        elif event.button == 4:
            self.zoom_at(mouse_screen, 1.1)
        elif event.button == 5:
            self.zoom_at(mouse_screen, 1 / 1.1)
        return False

    def handle_mouse_button_up(self, event: pygame.event.Event) -> None:
        if event.button == 1:
            self.world.dragging_part = False
        elif event.button == 2:
            self.world.panning = False

    def handle_mouse_motion(self, event: pygame.event.Event, mouse_world: Vec2) -> None:
        if self.world.panning:
            self.camera.offset += Vec2(event.rel) / self.camera.zoom
        if self.world.dragging_part and self.world.selected_part and self.world.selected_part.kind not in {"panel", "busbar", "neutral_bar", "ground_bar", "feeder_lugs", "breaker"}:
            new_position = self.world.snap(Vec2(mouse_world.x - self.world.drag_offset.x, mouse_world.y - self.world.drag_offset.y))
            dx = new_position.x - self.world.selected_part.x
            dy = new_position.y - self.world.selected_part.y
            self.world.selected_part.x = new_position.x
            self.world.selected_part.y = new_position.y
            for terminal_id, terminal in list(self.world.terminals.items()):
                if terminal.part_id == self.world.selected_part.id:
                    self.world.terminals[terminal_id] = Terminal(terminal.id, (terminal.pos[0] + dx, terminal.pos[1] + dy), terminal.role, terminal.label, terminal.part_id)

    def draw(self, surface: pygame.Surface) -> None:
        mouse_screen = Vec2(pygame.mouse.get_pos())
        mouse_world = self.camera.screen_to_world((int(mouse_screen.x), int(mouse_screen.y)))
        self.update_temp_zone(mouse_world)

        surface.fill(BG)
        self.draw_grid(surface, surface.get_size())
        self.draw_topbar(surface)

        for part in self.world.parts:
            if part.kind == "zone":
                self.draw_part(surface, part)
        for part in self.world.parts:
            if part.kind != "zone":
                self.draw_part(surface, part)
        for wire in self.world.wires:
            self.draw_wire(surface, wire)
        for terminal in self.world.terminals.values():
            self.draw_terminal(surface, terminal)

        if self.world.temp_zone_rect and self.world.show_blueprint:
            screen_rect = self.to_screen_rect(self.world.temp_zone_rect)
            overlay = pygame.Surface((max(1, screen_rect.width), max(1, screen_rect.height)), pygame.SRCALPHA)
            overlay.fill((92, 165, 255, 42))
            surface.blit(overlay, screen_rect.topleft)
            pygame.draw.rect(surface, BLUEPRINT, screen_rect, 2)

        self.draw_pending_wire(surface, mouse_world)
        self.draw_sidebar(surface)

    def set_tool(self, tool: str) -> None:
        self.world.current_tool = tool
        if tool != "wire":
            self.world.pending_wire_terminal = None
            self.world.pending_wire_points = []
        self.world.status = f"Tool set to {tool}"

    def cancel_current_action(self) -> None:
        self.world.pending_wire_terminal = None
        self.world.pending_wire_points = []
        self.world.creating_zone = False
        self.world.zone_start = None
        self.world.temp_zone_rect = None
        self.world.dragging_part = False
        self.world.status = "Canceled current action"

    def cycle_wire_role(self) -> None:
        current_index = self.wire_role_cycle.index(self.manual_wire_role)
        self.manual_wire_role = self.wire_role_cycle[(current_index + 1) % len(self.wire_role_cycle)]
        self.world.pending_wire_color = {"hot": WIRE_RED, "neutral": WIRE_WHITE, "ground": WIRE_GREEN}[self.manual_wire_role]
        self.world.status = f"Wire role set to {self.manual_wire_role}"

    def zoom_at(self, mouse_screen: Vec2, factor: float) -> None:
        old_world = self.camera.screen_to_world((int(mouse_screen.x), int(mouse_screen.y)))
        self.camera.zoom = max(0.35, min(2.8, self.camera.zoom * factor))
        new_world = self.camera.screen_to_world((int(mouse_screen.x), int(mouse_screen.y)))
        self.camera.offset += new_world - old_world

    def update_temp_zone(self, mouse_world: Vec2) -> None:
        if not self.world.creating_zone or self.world.zone_start is None:
            self.world.temp_zone_rect = None
            return
        start = self.world.zone_start
        end = self.world.snap(mouse_world)
        x1, x2 = sorted((start.x, end.x))
        y1, y2 = sorted((start.y, end.y))
        self.world.temp_zone_rect = pygame.Rect(x1, y1, max(20, x2 - x1), max(20, y2 - y1))

    def handle_left_click(self, mouse_world: Vec2) -> None:
        snapped = self.world.snap(mouse_world)

        if self.world.current_tool == "zone":
            if not self.world.creating_zone:
                self.world.creating_zone = True
                self.world.zone_start = snapped
                self.world.status = "Zone start placed"
            else:
                start = self.world.zone_start
                x1, x2 = sorted((start.x, snapped.x))
                y1, y2 = sorted((start.y, snapped.y))
                self.world.add_part("zone", x1, y1, max(20, x2 - x1), max(20, y2 - y1), f"Zone {self.world.next_part_id}", {"blueprint": True})
                self.world.creating_zone = False
                self.world.zone_start = None
                self.world.temp_zone_rect = None
                self.world.status = "Zone created"
            return

        if self.world.current_tool == "wire":
            self.handle_wire_click(mouse_world, snapped)
            return

        if self.world.current_tool == "add_load":
            load_stub = self.world.add_part("load_stub", snapped.x, snapped.y, 120, 54, f"Load {self.world.next_part_id}")
            self.world.add_terminal(load_stub, load_stub.x + 10, load_stub.y + 16, "hot", "HOT IN")
            self.world.add_terminal(load_stub, load_stub.x + 10, load_stub.y + 28, "neutral", "N IN")
            self.world.add_terminal(load_stub, load_stub.x + 10, load_stub.y + 40, "ground", "G IN")
            self.world.select_part(load_stub)
            self.world.status = "Load stub added"
            return

        part = self.world.get_part_at(mouse_world)
        if part is None:
            self.world.select_part(None)
            self.world.status = "Deselected"
            return

        self.world.select_part(part)
        if part.kind == "breaker":
            self.world.toggle_breaker(part)
        else:
            self.world.dragging_part = True
            self.world.drag_offset = Vec2(mouse_world.x - part.x, mouse_world.y - part.y)
            self.world.status = f"Selected {part.label or part.kind}"

    def handle_wire_click(self, mouse_world: Vec2, snapped: Vec2) -> None:
        terminal_id = self.world.get_terminal_at(mouse_world)
        if terminal_id is not None:
            if self.world.pending_wire_terminal is None:
                self.world.pending_wire_terminal = terminal_id
                self.world.pending_wire_points = []
                role = self.world.terminals[terminal_id].role
                self.manual_wire_role = role if role in self.wire_role_cycle else "hot"
                self.world.pending_wire_color = {"hot": WIRE_RED, "neutral": WIRE_WHITE, "ground": WIRE_GREEN}.get(self.manual_wire_role, WIRE_PURPLE)
                self.world.status = f"Wire start: {self.world.terminals[terminal_id].label}"
                return

            if terminal_id == self.world.pending_wire_terminal:
                self.world.status = "Pick a different terminal"
                return

            start_role = self.world.terminals[self.world.pending_wire_terminal].role
            end_role = self.world.terminals[terminal_id].role
            if start_role != end_role:
                self.world.status = "Roles do not match"
                return

            self.world.add_wire(self.world.pending_wire_terminal, terminal_id, self.world.pending_wire_points, self.world.pending_wire_color, f"{start_role} wire")
            self.world.pending_wire_terminal = None
            self.world.pending_wire_points = []
            self.world.status = "Wire completed"
            return

        if self.world.pending_wire_terminal is not None:
            previous = self.world.terminal_pos(self.world.pending_wire_terminal) if not self.world.pending_wire_points else Vec2(self.world.pending_wire_points[-1])
            point = self.orthogonal_point(previous, snapped)
            self.world.pending_wire_points.append((point.x, point.y))
            self.world.status = f"Waypoint {len(self.world.pending_wire_points)} added"

    def handle_sidebar_click(self, mouse_screen: Vec2) -> str | bool:
        for tool, rect in self.tool_buttons:
            if rect.collidepoint(mouse_screen.x, mouse_screen.y):
                self.set_tool(tool)
                return True

        for part_kind, rect in self.part_buttons:
            if rect.collidepoint(mouse_screen.x, mouse_screen.y):
                if part_kind == "add_load":
                    self.set_tool("add_load")
                elif part_kind == "place_conduit":
                    self.request_floor_plan_conduit = True
                    self.world.status = "Conduit tool armed for floor plan placement"
                    return "close"
                return True
        return False

    @staticmethod
    def orthogonal_point(previous: Vec2, target: Vec2) -> Vec2:
        if abs(target.x - previous.x) >= abs(target.y - previous.y):
            return Vec2(target.x, previous.y)
        return Vec2(previous.x, target.y)

    def is_sidebar_click(self, mouse_screen: Vec2, screen_size: tuple[int, int]) -> bool:
        return mouse_screen.x >= screen_size[0] - self.sidebar_width

    def to_screen_rect(self, world_rect: pygame.Rect) -> pygame.Rect:
        top_left = self.camera.world_to_screen(Vec2(world_rect.topleft))
        return pygame.Rect(int(top_left.x), int(top_left.y), int(world_rect.width * self.camera.zoom), int(world_rect.height * self.camera.zoom))

    def draw_text(self, surface: pygame.Surface, text: str, x: int | float, y: int | float, color: Color = TEXT, font: Optional[pygame.font.Font] = None) -> None:
        render_font = font or self.font
        surface.blit(render_font.render(text, True, color), (x, y))

    def draw_grid(self, surface: pygame.Surface, screen_size: tuple[int, int]) -> None:
        world_top_left = self.camera.screen_to_world((0, 0))
        world_bottom_right = self.camera.screen_to_world(screen_size)
        grid = self.world.grid_size
        major = grid * 10
        start_x = int(world_top_left.x // grid) * grid
        end_x = int(world_bottom_right.x // grid + 1) * grid
        start_y = int(world_top_left.y // grid) * grid
        end_y = int(world_bottom_right.y // grid + 1) * grid
        for x in range(start_x, end_x, grid):
            screen_x = self.camera.world_to_screen(Vec2(x, 0)).x
            color = (42, 46, 55) if x % major else (60, 66, 80)
            pygame.draw.line(surface, color, (screen_x, 0), (screen_x, screen_size[1]))
        for y in range(start_y, end_y, grid):
            screen_y = self.camera.world_to_screen(Vec2(0, y)).y
            color = (42, 46, 55) if y % major else (60, 66, 80)
            pygame.draw.line(surface, color, (0, screen_y), (screen_size[0], screen_y))

    def draw_topbar(self, surface: pygame.Surface) -> None:
        topbar = pygame.Rect(0, 0, surface.get_width(), self.topbar_height)
        pygame.draw.rect(surface, TOPBAR_BG, topbar)
        self.back_button_rect = pygame.Rect(16, 10, 120, 32)
        pygame.draw.rect(surface, BUTTON_BG, self.back_button_rect, border_radius=6)
        pygame.draw.rect(surface, BUTTON_BORDER, self.back_button_rect, 2, border_radius=6)
        self.draw_text(surface, "Back to plan", self.back_button_rect.x + 12, self.back_button_rect.y + 7, TEXT, self.small_font)
        self.draw_text(surface, "Panelboard / Breaker Box Emulator", 160, 14, TEXT, self.big_font)

    def draw_part(self, surface: pygame.Surface, part: Part) -> None:
        screen_rect = self.to_screen_rect(part.rect())
        if part.kind == "zone":
            if self.world.show_blueprint:
                overlay = pygame.Surface((max(1, screen_rect.width), max(1, screen_rect.height)), pygame.SRCALPHA)
                overlay.fill(BLUEPRINT_FILL)
                surface.blit(overlay, screen_rect.topleft)
                pygame.draw.rect(surface, BLUEPRINT, screen_rect, 2)
                self.draw_text(surface, part.label, screen_rect.x + 6, screen_rect.y + 6, BLUEPRINT, self.small_font)
            return
        if part.kind == "panel":
            pygame.draw.rect(surface, CABINET_BG, screen_rect, border_radius=14)
            inner = screen_rect.inflate(-36 * self.camera.zoom, -40 * self.camera.zoom)
            pygame.draw.rect(surface, CABINET_INNER, inner, border_radius=8)
            pygame.draw.rect(surface, CABINET_BORDER, screen_rect, 3, border_radius=14)
            self.draw_text(surface, part.label, screen_rect.x + 20, screen_rect.y + 12, TEXT, self.big_font)
            self.draw_text(surface, f"{part.props.get('main_amps', 0)}A {part.props.get('system', '')}", screen_rect.x + 20, screen_rect.y + 38, MUTED, self.small_font)
            center_x = screen_rect.centerx
            for index in range(self.world.slot_count_per_side):
                y = screen_rect.y + 145 * self.camera.zoom + index * ((self.world.panel_slot_height + self.world.panel_slot_gap) * self.camera.zoom)
                pygame.draw.line(surface, PANEL_SLOT_LINE, (center_x - 230 * self.camera.zoom, y), (center_x - 40 * self.camera.zoom, y), 1)
                pygame.draw.line(surface, PANEL_SLOT_LINE, (center_x + 40 * self.camera.zoom, y), (center_x + 230 * self.camera.zoom, y), 1)
            return
        if part.kind == "feeder_lugs":
            pygame.draw.rect(surface, (150, 154, 165), screen_rect, border_radius=6)
            pygame.draw.rect(surface, (50, 52, 58), screen_rect, 2, border_radius=6)
            lug_y1 = screen_rect.y + screen_rect.h * 0.28
            lug_y2 = screen_rect.y + screen_rect.h * 0.72
            for frac, color in ((0.25, WIRE_BLACK), (0.5, WIRE_WHITE), (0.75, WIRE_RED)):
                x = screen_rect.x + screen_rect.w * frac
                pygame.draw.circle(surface, color, (int(x), int(lug_y1)), max(4, int(7 * self.camera.zoom)))
            pygame.draw.circle(surface, WIRE_GREEN, (int(screen_rect.centerx), int(lug_y2)), max(4, int(7 * self.camera.zoom)))
            self.draw_text(surface, part.label, screen_rect.x + 8, screen_rect.y + 8, TEXT, self.small_font)
            return
        if part.kind == "busbar":
            color = BUS_COLOR_A if part.props.get("role") == "L1" else BUS_COLOR_B
            pygame.draw.rect(surface, color, screen_rect, border_radius=4)
            pygame.draw.rect(surface, (60, 32, 18), screen_rect, 2, border_radius=4)
            self.draw_text(surface, part.label, screen_rect.x - 5, screen_rect.y - 18, TEXT, self.small_font)
            return
        if part.kind == "neutral_bar":
            pygame.draw.rect(surface, NEUTRAL_BAR, screen_rect, border_radius=4)
            pygame.draw.rect(surface, (45, 65, 88), screen_rect, 2, border_radius=4)
            self.draw_text(surface, part.label, screen_rect.x - 16, screen_rect.y - 18, TEXT, self.small_font)
            return
        if part.kind == "ground_bar":
            pygame.draw.rect(surface, GROUND_BAR, screen_rect, border_radius=4)
            pygame.draw.rect(surface, (30, 70, 45), screen_rect, 2, border_radius=4)
            self.draw_text(surface, part.label, screen_rect.x - 6, screen_rect.y - 18, TEXT, self.small_font)
            return
        if part.kind == "breaker":
            pygame.draw.rect(surface, BREAKER_BODY, screen_rect, border_radius=5)
            face = screen_rect.inflate(-10 * self.camera.zoom, -8 * self.camera.zoom)
            pygame.draw.rect(surface, BREAKER_FACE, face, border_radius=4)
            pygame.draw.rect(surface, (20, 22, 26), screen_rect, 2, border_radius=5)
            handle_on = part.props.get("state") == "closed" and not part.props.get("tripped")
            handle_x = face.x + face.w * (0.67 if handle_on else 0.34)
            handle_y = face.centery
            pygame.draw.rect(surface, BREAKER_HANDLE_ON if handle_on else BREAKER_HANDLE_OFF, pygame.Rect(handle_x - 9 * self.camera.zoom, handle_y - 10 * self.camera.zoom, 18 * self.camera.zoom, 20 * self.camera.zoom), border_radius=3)
            self.draw_text(surface, str(part.props.get("circuit_no", "?")), screen_rect.x + 8, screen_rect.y + 8, TEXT, self.small_font)
            self.draw_text(surface, f"{part.props.get('amps', 0)}A", screen_rect.right - 42, screen_rect.y + 8, MUTED, self.small_font)
        elif part.kind == "load_stub":
            pygame.draw.rect(surface, (68, 74, 86), screen_rect, border_radius=5)
            pygame.draw.rect(surface, (28, 30, 36), screen_rect, 2, border_radius=5)
            self.draw_text(surface, part.label, screen_rect.x + 8, screen_rect.y + 14, TEXT, self.small_font)
        else:
            pygame.draw.rect(surface, (90, 95, 105), screen_rect)
        if part.selected:
            pygame.draw.rect(surface, ACCENT, screen_rect, 2, border_radius=5)

    def draw_terminal(self, surface: pygame.Surface, terminal: Terminal) -> None:
        screen_position = self.camera.world_to_screen(terminal.world_pos())
        color = {
            "hot": HOT if self.world.is_terminal_hot(terminal.id) else WIRE_ORANGE,
            "neutral": WIRE_WHITE,
            "ground": WIRE_GREEN,
        }.get(terminal.role, ACCENT)
        pygame.draw.circle(surface, color, (int(screen_position.x), int(screen_position.y)), max(2, int(4 * self.camera.zoom)))

    def draw_wire(self, surface: pygame.Surface, wire: Wire) -> None:
        start = self.world.terminal_pos(wire.start_terminal)
        end = self.world.terminal_pos(wire.end_terminal)
        if start is None or end is None:
            return
        points = [start] + [Vec2(point) for point in wire.path] + [end]
        screen_points = [self.camera.world_to_screen(point) for point in points]
        color = HOT if self.world.is_terminal_hot(wire.start_terminal) and self.world.terminals[wire.start_terminal].role == "hot" else wire.color
        pygame.draw.lines(surface, color, False, screen_points, max(1, int(3 * self.camera.zoom)))
        for point in screen_points[1:-1]:
            pygame.draw.circle(surface, color, (int(point.x), int(point.y)), max(2, int(3 * self.camera.zoom)))

    def draw_pending_wire(self, surface: pygame.Surface, mouse_world: Vec2) -> None:
        if self.world.pending_wire_terminal is None:
            return
        start = self.world.terminal_pos(self.world.pending_wire_terminal)
        if start is None:
            return
        points = [start] + [Vec2(point) for point in self.world.pending_wire_points] + [mouse_world]
        screen_points = [self.camera.world_to_screen(point) for point in points]
        pygame.draw.lines(surface, self.world.pending_wire_color, False, screen_points, 2)

    def draw_sidebar(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        sidebar = pygame.Rect(width - self.sidebar_width, 0, self.sidebar_width, height)
        pygame.draw.rect(surface, SIDEBAR_BG, sidebar)
        pygame.draw.line(surface, SIDEBAR_BORDER, sidebar.topleft, sidebar.bottomleft, 2)
        y = 72
        self.tool_buttons = []
        self.part_buttons = []

        def line(text: str, color: Color = TEXT, font: Optional[pygame.font.Font] = None) -> None:
            nonlocal y
            render_font = font or self.font
            surface.blit(render_font.render(text, True, color), (width - self.sidebar_width + 20, y))
            y += render_font.get_height() + 7

        line("Panelboard Emulator", TEXT, self.big_font)
        line("Tools", TEXT)
        button_y = y
        for tool_name, label in [("pointer", "Pointer"), ("wire", "Wire"), ("zone", "Zone"), ("add_load", "Load")]:
            rect = pygame.Rect(width - self.sidebar_width + 20, button_y, 88, 28)
            active = self.world.current_tool == tool_name
            pygame.draw.rect(surface, ACCENT if active else BUTTON_BG, rect, border_radius=6)
            pygame.draw.rect(surface, BUTTON_BORDER, rect, 2, border_radius=6)
            self.draw_text(surface, label, rect.x + 10, rect.y + 6, BG if active else TEXT, self.small_font)
            self.tool_buttons.append((tool_name, rect))
            button_y += 34
        y = button_y + 4

        line("Parts", TEXT)
        for part_kind, label in [("add_load", "Add Load Stub"), ("place_conduit", "Send Conduit To Plan")]:
            rect = pygame.Rect(width - self.sidebar_width + 20, y, 180, 28)
            pygame.draw.rect(surface, BUTTON_BG, rect, border_radius=6)
            pygame.draw.rect(surface, BUTTON_BORDER, rect, 2, border_radius=6)
            self.draw_text(surface, label, rect.x + 10, rect.y + 6, TEXT, self.small_font)
            self.part_buttons.append((part_kind, rect))
            y += 34

        line(f"Tool: {self.world.current_tool}")
        line(f"Grid snap: {'ON' if self.world.grid_snap else 'OFF'}")
        line(f"Blueprint: {'ON' if self.world.show_blueprint else 'OFF'}")
        line(f"Wire role: {self.manual_wire_role}")
        line("")
        line("Hotkeys", TEXT)
        line("1 pointer")
        line("2 wire")
        line("3 zone")
        line("4 reset default panel")
        line("5 add load stub")
        line("G grid toggle")
        line("B blueprint toggle")
        line("Tab cycle wire role")
        line("Right click / Z undo path")
        line("S save   L load")
        line("Delete remove selected")
        line("Esc / Back returns")
        line("Middle drag pans")
        line("Mouse wheel zoom")
        line("")
        if self.world.selected_part is not None:
            part = self.world.selected_part
            line("Selected", TEXT)
            line(f"Kind: {part.kind}")
            line(f"Label: {part.label}")
            if part.kind == "breaker":
                line(f"Circuit: {part.props.get('circuit_no')}", HOT)
                line(f"State: {part.props.get('state')}", HOT if part.props.get("state") == "closed" else MUTED)
                line(f"Amps: {part.props.get('amps')}A")
                line("Click breaker in pointer mode")
            elif part.kind == "panel":
                line(f"Main: {part.props.get('main_amps')}A")
                line(f"System: {part.props.get('system')}")
            elif part.kind == "load_stub":
                line(f"Load circuit: {part.props.get('circuit_no')}")
        else:
            line("No selection")
        line("")
        line(f"Parts: {len(self.world.parts)}")
        line(f"Terminals: {len(self.world.terminals)}")
        line(f"Wires: {len(self.world.wires)}")
        line("")
        line(self.world.status, ACCENT, self.small_font)
