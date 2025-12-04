"""Export utilities for GeoTIFF and other formats."""

import os
from io import BytesIO
from typing import Tuple, Optional

import numpy as np
from PIL import Image

# Try to import rasterio, fall back to basic export if not available
try:
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("Warning: rasterio not available, GeoTIFF export will be limited")

from .tile import TileBounds


def export_geotiff(
    image: Image.Image,
    bounds: TileBounds,
    output_path: str,
    crs: str = "EPSG:4326"
) -> str:
    """
    Export image as GeoTIFF with geographic coordinates.
    
    Args:
        image: PIL Image to export
        bounds: Geographic bounds of the image
        output_path: Output file path
        crs: Coordinate reference system (default: WGS84)
    
    Returns:
        Path to the created file
    """
    if not RASTERIO_AVAILABLE:
        raise RuntimeError("rasterio is required for GeoTIFF export. Install with: pip install rasterio")
    
    # Convert PIL Image to numpy array
    img_array = np.array(image)
    
    # Get image dimensions
    height, width = img_array.shape[:2]
    
    # Handle RGB vs RGBA
    if len(img_array.shape) == 3:
        if img_array.shape[2] == 4:
            # RGBA - drop alpha channel for GeoTIFF
            img_array = img_array[:, :, :3]
        count = img_array.shape[2]
    else:
        count = 1
    
    # Create affine transform from bounds
    # from_bounds(west, south, east, north, width, height)
    transform = from_bounds(
        bounds.west, bounds.south, bounds.east, bounds.north,
        width, height
    )
    
    # Create GeoTIFF
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=count,
        dtype=img_array.dtype,
        crs=CRS.from_string(crs),
        transform=transform,
        compress='lzw'  # Use LZW compression
    ) as dst:
        # Write each band
        if count == 1:
            dst.write(img_array, 1)
        else:
            for i in range(count):
                dst.write(img_array[:, :, i], i + 1)
    
    return output_path


def export_geotiff_bytes(
    image: Image.Image,
    bounds: TileBounds,
    crs: str = "EPSG:4326"
) -> bytes:
    """
    Export image as GeoTIFF and return as bytes.
    
    Args:
        image: PIL Image to export
        bounds: Geographic bounds of the image
        crs: Coordinate reference system (default: WGS84)
    
    Returns:
        GeoTIFF file as bytes
    """
    if not RASTERIO_AVAILABLE:
        raise RuntimeError("rasterio is required for GeoTIFF export")
    
    # Convert PIL Image to numpy array
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 3:
        if img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]
        count = img_array.shape[2]
    else:
        count = 1
    
    transform = from_bounds(
        bounds.west, bounds.south, bounds.east, bounds.north,
        width, height
    )
    
    # Create in-memory GeoTIFF
    from rasterio.io import MemoryFile
    
    with MemoryFile() as memfile:
        with memfile.open(
            driver='GTiff',
            height=height,
            width=width,
            count=count,
            dtype=img_array.dtype,
            crs=CRS.from_string(crs),
            transform=transform,
            compress='lzw'
        ) as dst:
            if count == 1:
                dst.write(img_array, 1)
            else:
                for i in range(count):
                    dst.write(img_array[:, :, i], i + 1)
        
        return memfile.read()


def export_png(image: Image.Image, output_path: str) -> str:
    """Export image as PNG."""
    image.save(output_path, 'PNG', optimize=True)
    return output_path


def export_png_bytes(image: Image.Image) -> bytes:
    """Export image as PNG bytes."""
    buffer = BytesIO()
    image.save(buffer, 'PNG', optimize=True)
    return buffer.getvalue()


def export_jpeg(image: Image.Image, output_path: str, quality: int = 90) -> str:
    """Export image as JPEG."""
    # Convert RGBA to RGB if necessary
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    image.save(output_path, 'JPEG', quality=quality, optimize=True)
    return output_path


def export_jpeg_bytes(image: Image.Image, quality: int = 90) -> bytes:
    """Export image as JPEG bytes."""
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    buffer = BytesIO()
    image.save(buffer, 'JPEG', quality=quality, optimize=True)
    return buffer.getvalue()


def export_image(
    image: Image.Image,
    bounds: TileBounds,
    format: str,
    output_path: Optional[str] = None
) -> Tuple[bytes, str]:
    """
    Export image in the specified format.
    
    Args:
        image: PIL Image to export
        bounds: Geographic bounds of the image
        format: Output format ('geotiff', 'png', 'jpeg')
        output_path: Optional output file path
    
    Returns:
        Tuple of (file bytes, content type)
    """
    format = format.lower()
    
    if format == 'geotiff':
        try:
            if output_path:
                export_geotiff(image, bounds, output_path)
                with open(output_path, 'rb') as f:
                    return f.read(), 'image/tiff'
            else:
                return export_geotiff_bytes(image, bounds), 'image/tiff'
        except Exception as e:
            print(f"GeoTIFF export failed: {e}, falling back to PNG")
            # Fall back to PNG
            return export_png_bytes(image), 'image/png'
    
    elif format == 'png':
        if output_path:
            export_png(image, output_path)
            with open(output_path, 'rb') as f:
                return f.read(), 'image/png'
        else:
            return export_png_bytes(image), 'image/png'
    
    elif format in ('jpeg', 'jpg'):
        if output_path:
            export_jpeg(image, output_path)
            with open(output_path, 'rb') as f:
                return f.read(), 'image/jpeg'
        else:
            return export_jpeg_bytes(image), 'image/jpeg'
    
    else:
        raise ValueError(f"Unsupported format: {format}. Supported: geotiff, png, jpeg")


def get_file_extension(format: str) -> str:
    """Get file extension for a format."""
    format = format.lower()
    extensions = {
        'geotiff': '.tif',
        'tiff': '.tif',
        'tif': '.tif',
        'png': '.png',
        'jpeg': '.jpg',
        'jpg': '.jpg'
    }
    return extensions.get(format, '.tif')
