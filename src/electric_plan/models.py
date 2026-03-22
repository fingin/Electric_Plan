from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

Point = Tuple[float, float]


class Tool(str, Enum):
    SELECT = "select"
    WALL = "wall"
    PANEL = "panel"
    CONDUIT = "conduit"


@dataclass
class Wall:
    start: Point
    end: Point


@dataclass
class Panel:
    position: Point
    label: str = "Panel"
    rotation: float = 0.0


@dataclass
class Conduit:
    start: Point
    end: Point
    label: str = "Conduit"


@dataclass
class FloorPlanState:
    walls: List[Wall] = field(default_factory=list)
    panels: List[Panel] = field(default_factory=list)
    conduits: List[Conduit] = field(default_factory=list)
class FloorPlanState:
    walls: List[Wall] = field(default_factory=list)
    panels: List[Panel] = field(default_factory=list)
    tool: Tool = Tool.SELECT
    camera_offset: Point = (0.0, 0.0)
    zoom: float = 1.0
    selected_wall_index: Optional[int] = None
    selected_panel_index: Optional[int] = None
    selected_conduit_index: Optional[int] = None
    wall_start: Optional[Point] = None
    conduit_start: Optional[Point] = None
    wall_start: Optional[Point] = None

    def clear_selection(self) -> None:
        self.selected_wall_index = None
        self.selected_panel_index = None
        self.selected_conduit_index = None
