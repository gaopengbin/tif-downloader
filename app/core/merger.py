"""Tile merging utilities using Pillow."""

from typing import Dict, Tuple, List
from PIL import Image, ImageDraw
from ..config import TILE_SIZE
from .downloader import create_blank_tile
from ..models import PolygonCoord

def mask_image_by_polygon(
    image: Image.Image,
    polygon: List[PolygonCoord],
    image_bounds: Tuple[float, float, float, float]
) -> Image.Image:
    """
    Mask image using a polygon, making outside area transparent.
    
    Args:
        image: PIL Image to mask
        polygon: List of coordinates [lat, lng]
        image_bounds: (north, south, east, west) of the image
        
    Returns:
        Masked PIL Image (RGBA)
    """
    # Ensure image has alpha channel
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
        
    width, height = image.size
    img_north, img_south, img_east, img_west = image_bounds
    
    # Calculate pixel coordinates for polygon
    pixels = []
    lat_span = img_north - img_south
    lng_span = img_east - img_west
    
    for point in polygon:
        # X = (lng - west) / span * width
        x = int((point.lng - img_west) / lng_span * width)
        # Y = (north - lat) / span * height
        y = int((img_north - point.lat) / lat_span * height)
        pixels.append((x, y))
        
    if len(pixels) < 3:
        return image
        
    # Create mask
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(pixels, fill=255)
    
    # Apply mask
    # We want to keep alpha of original image where mask is white
    # So we combine original alpha with our mask
    # Actually, simple putalpha works if we want strictly the polygon shape
    # But let's respect existing transparency if any
    
    # Create a composite mask: minimum of existing alpha and new mask
    alpha = image.split()[3]
    composite_mask = Image.composite(alpha, mask, mask) # Wait, this logic is tricky
    
    # Simpler: Just paste the image onto a transparent background using the mask
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    
    return result


def merge_tiles(
    tile_images: Dict[Tuple[int, int], Image.Image],
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int
) -> Image.Image:
    """
    Merge downloaded tiles into a single image.
    
    Args:
        tile_images: Dictionary mapping (x, y) coordinates to PIL Images
        x_min: Minimum tile X coordinate
        y_min: Minimum tile Y coordinate
        x_max: Maximum tile X coordinate
        y_max: Maximum tile Y coordinate
    
    Returns:
        Merged PIL Image
    """
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    
    # Calculate output image size
    width = cols * TILE_SIZE
    height = rows * TILE_SIZE
    
    # Create output image
    merged = Image.new("RGB", (width, height), (255, 255, 255))
    
    # Paste each tile
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            # Get tile or create blank
            tile_image = tile_images.get((x, y))
            if tile_image is None:
                tile_image = create_blank_tile()
            
            # Calculate position in output image
            px = (x - x_min) * TILE_SIZE
            py = (y - y_min) * TILE_SIZE
            
            # Ensure tile is correct size
            if tile_image.size != (TILE_SIZE, TILE_SIZE):
                tile_image = tile_image.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
            
            # Paste tile
            merged.paste(tile_image, (px, py))
    
    return merged


def merge_tiles_chunked(
    tile_images: Dict[Tuple[int, int], Image.Image],
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    chunk_size: int = 10
) -> Image.Image:
    """
    Merge tiles in chunks for large areas (memory optimization).
    
    This processes tiles row by row to reduce peak memory usage.
    
    Args:
        tile_images: Dictionary mapping (x, y) coordinates to PIL Images
        x_min: Minimum tile X coordinate
        y_min: Minimum tile Y coordinate
        x_max: Maximum tile X coordinate
        y_max: Maximum tile Y coordinate
        chunk_size: Number of rows to process at once
    
    Returns:
        Merged PIL Image
    """
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    
    # For smaller images, use simple merge
    if rows <= chunk_size * 2:
        return merge_tiles(tile_images, x_min, y_min, x_max, y_max)
    
    # Calculate output image size
    width = cols * TILE_SIZE
    height = rows * TILE_SIZE
    
    # Create output image
    merged = Image.new("RGB", (width, height), (255, 255, 255))
    
    # Process in row chunks
    for chunk_start in range(0, rows, chunk_size):
        chunk_end = min(chunk_start + chunk_size, rows)
        
        for row_offset in range(chunk_start, chunk_end):
            y = y_min + row_offset
            py = row_offset * TILE_SIZE
            
            for col_offset in range(cols):
                x = x_min + col_offset
                px = col_offset * TILE_SIZE
                
                tile_image = tile_images.get((x, y))
                if tile_image is None:
                    tile_image = create_blank_tile()
                
                if tile_image.size != (TILE_SIZE, TILE_SIZE):
                    tile_image = tile_image.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
                
                merged.paste(tile_image, (px, py))
    
    return merged


def crop_to_bounds(
    image: Image.Image,
    image_bounds: Tuple[float, float, float, float],
    target_bounds: Tuple[float, float, float, float]
) -> Image.Image:
    """
    Crop image to target geographic bounds.
    
    Args:
        image: PIL Image to crop
        image_bounds: (north, south, east, west) of the image
        target_bounds: (north, south, east, west) to crop to
    
    Returns:
        Cropped PIL Image
    """
    img_north, img_south, img_east, img_west = image_bounds
    tgt_north, tgt_south, tgt_east, tgt_west = target_bounds
    
    width, height = image.size
    
    # Calculate pixel positions
    lng_per_pixel = (img_east - img_west) / width
    lat_per_pixel = (img_north - img_south) / height
    
    left = int((tgt_west - img_west) / lng_per_pixel)
    right = int((tgt_east - img_west) / lng_per_pixel)
    top = int((img_north - tgt_north) / lat_per_pixel)
    bottom = int((img_north - tgt_south) / lat_per_pixel)
    
    # Clamp to image bounds
    left = max(0, min(width, left))
    right = max(0, min(width, right))
    top = max(0, min(height, top))
    bottom = max(0, min(height, bottom))
    
    return image.crop((left, top, right, bottom))
