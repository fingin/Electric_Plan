from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

Point = Tuple[float, float]


class Tool(str, Enum):
    SELECT = "select"
    WALL = "wall"
    PANEL = "panel"


@dataclass
class Wall:
    start: Point
    end: Point


@dataclass
class Panel:
    position: Point
    label: str = "Panel"


@dataclass
class FloorPlanState:
    walls: List[Wall] = field(default_factory=list)
    panels: List[Panel] = field(default_factory=list)
    tool: Tool = Tool.SELECT
    camera_offset: Point = (0.0, 0.0)
    zoom: float = 1.0
    selected_wall_index: Optional[int] = None
    selected_panel_index: Optional[int] = None
    wall_start: Optional[Point] = None

    def clear_selection(self) -> None:
        self.selected_wall_index = None
        self.selected_panel_index = None
