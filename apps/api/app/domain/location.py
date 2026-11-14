# 文件说明：领域对象：location。
from dataclasses import dataclass
from typing import Literal

CoordinateSystem = Literal["GCJ-02", "WGS84"]


@dataclass(frozen=True, slots=True)
class GeoPoint:
    longitude: float
    latitude: float
    coordinate_system: CoordinateSystem = "GCJ-02"
