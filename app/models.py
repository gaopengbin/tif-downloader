"""Pydantic models for request/response validation."""

from typing import List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class Bounds(BaseModel):
    """Geographic bounds (bounding box)."""
    north: float = Field(..., ge=-90, le=90, description="北纬度")
    south: float = Field(..., ge=-90, le=90, description="南纬度")
    east: float = Field(..., ge=-180, le=180, description="东经度")
    west: float = Field(..., ge=-180, le=180, description="西经度")


class PolygonCoord(BaseModel):
    """Polygon coordinate point."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class DownloadRequest(BaseModel):
    """Download request model."""
    bounds: Optional[Bounds] = Field(None, description="矩形边界")
    polygon: Optional[List[PolygonCoord]] = Field(None, description="多边形坐标列表")
    zoom: int = Field(..., ge=1, le=20, description="缩放级别")
    source: str = Field("google_satellite", description="图源类型")
    format: str = Field("geotiff", description="输出格式")
    crop_to_shape: bool = Field(False, description="是否按多边形裁剪")
    proxy: Optional[str] = Field(None, description="代理地址")
    
    class Config:
        json_schema_extra = {
            "example": {
                "bounds": {
                    "north": 39.92,
                    "south": 39.90,
                    "east": 116.40,
                    "west": 116.38
                },
                "zoom": 15,
                "source": "google_satellite",
                "format": "geotiff"
            }
        }


class TileInfo(BaseModel):
    """Tile information."""
    x: int
    y: int
    z: int


class DownloadProgress(BaseModel):
    """Download progress information."""
    total: int = Field(..., description="总瓦片数")
    completed: int = Field(..., description="已完成数")
    failed: int = Field(..., description="失败数")
    status: str = Field(..., description="状态")


class GeocodeResult(BaseModel):
    """Geocode search result."""
    name: str
    display_name: str
    lat: float
    lng: float
    bounds: Optional[Bounds] = None
    address: Optional[dict] = None


class AdminRegion(BaseModel):
    """Administrative region."""
    code: str = Field(..., description="行政区划代码")
    name: str = Field(..., description="名称")
    level: str = Field(..., description="级别: province/city/district")
    center: Optional[Tuple[float, float]] = Field(None, description="中心点 [lng, lat]")


class TileSourceInfo(BaseModel):
    """Tile source information."""
    id: str
    name: str
    max_zoom: int
    attribution: str
