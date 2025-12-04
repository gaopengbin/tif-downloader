"""Tile coordinate calculation utilities.

Web Mercator (EPSG:3857) tile coordinate system.
Reference: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
"""

import math
from typing import List, Tuple, NamedTuple

from ..config import TILE_SIZE


class TileBounds(NamedTuple):
    """Tile geographic bounds."""
    north: float
    south: float
    east: float
    west: float


class TileCoord(NamedTuple):
    """Tile coordinate."""
    x: int
    y: int
    z: int


def latlng_to_tile_float(lat: float, lng: float, zoom: int) -> Tuple[float, float]:
    """
    Convert latitude/longitude to fractional tile coordinates.
    
    Args:
        lat: Latitude in degrees
        lng: Longitude in degrees
        zoom: Zoom level
    
    Returns:
        Tuple of (tile_x, tile_y) as floats
    """
    # Clamp latitude to valid range for Web Mercator
    lat = max(-85.05112878, min(85.05112878, lat))
    
    n = 2.0 ** zoom
    x = (lng + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    
    return x, y

def latlng_to_tile(lat: float, lng: float, zoom: int) -> Tuple[int, int]:
    """
    Convert latitude/longitude to tile coordinates.
    
    Args:
        lat: Latitude in degrees (-85.05 to 85.05)
        lng: Longitude in degrees (-180 to 180)
        zoom: Zoom level (0 to 20+)
    
    Returns:
        Tuple of (tile_x, tile_y)
    """
    x, y = latlng_to_tile_float(lat, lng, zoom)
    
    # Clamp to valid tile range
    n = 2.0 ** zoom
    x_int = max(0, min(int(n) - 1, int(x)))
    y_int = max(0, min(int(n) - 1, int(y)))
    
    return x_int, y_int


def tile_to_latlng(x: int, y: int, zoom: int) -> TileBounds:
    """
    Convert tile coordinates to geographic bounds (northwest and southeast corners).
    
    Args:
        x: Tile X coordinate
        y: Tile Y coordinate
        zoom: Zoom level
    
    Returns:
        TileBounds with north, south, east, west coordinates
    """
    n = 2.0 ** zoom
    
    # Northwest corner (top-left)
    west = x / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    
    # Southeast corner (bottom-right)
    east = (x + 1) / n * 360.0 - 180.0
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    
    return TileBounds(north=north, south=south, east=east, west=west)


def get_tiles_in_bounds(
    north: float, 
    south: float, 
    east: float, 
    west: float, 
    zoom: int
) -> List[TileCoord]:
    """
    Get all tile coordinates within a bounding box.
    
    Args:
        north: Northern latitude
        south: Southern latitude
        east: Eastern longitude
        west: Western longitude
        zoom: Zoom level
    
    Returns:
        List of TileCoord objects
    """
    # Get tile coordinates for corners
    x_min, y_min = latlng_to_tile(north, west, zoom)  # Northwest
    x_max, y_max = latlng_to_tile(south, east, zoom)  # Southeast
    
    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append(TileCoord(x=x, y=y, z=zoom))
    
    return tiles


def get_tile_matrix_size(
    north: float, 
    south: float, 
    east: float, 
    west: float, 
    zoom: int
) -> Tuple[int, int, int, int, int, int]:
    """
    Get tile matrix dimensions for a bounding box.
    
    Returns:
        Tuple of (x_min, y_min, x_max, y_max, cols, rows)
    """
    x_min, y_min = latlng_to_tile(north, west, zoom)
    x_max, y_max = latlng_to_tile(south, east, zoom)
    
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    
    return x_min, y_min, x_max, y_max, cols, rows


def get_merged_bounds(
    x_min: int, 
    y_min: int, 
    x_max: int, 
    y_max: int, 
    zoom: int
) -> TileBounds:
    """
    Get the geographic bounds of a merged tile area.
    
    Args:
        x_min: Minimum tile X
        y_min: Minimum tile Y
        x_max: Maximum tile X
        y_max: Maximum tile Y
        zoom: Zoom level
    
    Returns:
        TileBounds for the merged area
    """
    nw_bounds = tile_to_latlng(x_min, y_min, zoom)
    se_bounds = tile_to_latlng(x_max, y_max, zoom)
    
    return TileBounds(
        north=nw_bounds.north,
        south=se_bounds.south,
        east=se_bounds.east,
        west=nw_bounds.west
    )


def estimate_tile_count(
    north: float, 
    south: float, 
    east: float, 
    west: float, 
    zoom: int
) -> int:
    """Estimate the number of tiles in a bounding box."""
    x_min, y_min = latlng_to_tile(north, west, zoom)
    x_max, y_max = latlng_to_tile(south, east, zoom)
    
    return (x_max - x_min + 1) * (y_max - y_min + 1)


def meters_per_pixel(lat: float, zoom: int) -> float:
    """
    Calculate meters per pixel at a given latitude and zoom level.
    
    Args:
        lat: Latitude in degrees
        zoom: Zoom level
    
    Returns:
        Meters per pixel
    """
    # Earth's circumference at equator in meters
    earth_circumference = 40075016.686
    
    return earth_circumference * math.cos(math.radians(lat)) / (TILE_SIZE * (2 ** zoom))


def get_optimal_zoom(
    north: float, 
    south: float, 
    east: float, 
    west: float, 
    max_tiles: int = 1000
) -> int:
    """
    Get optimal zoom level that doesn't exceed max_tiles.
    
    Args:
        north, south, east, west: Bounding box
        max_tiles: Maximum number of tiles
    
    Returns:
        Optimal zoom level
    """
    for zoom in range(20, 0, -1):
        count = estimate_tile_count(north, south, east, west, zoom)
        if count <= max_tiles:
            return zoom
    return 1
