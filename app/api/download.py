"""Download API endpoints."""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.responses import Response
import asyncio
import json
from io import BytesIO

from ..models import DownloadRequest, Bounds
from ..config import TILE_SOURCES, OUTPUT_FORMATS, TILE_SIZE, TIANDITU_DEFAULT_TOKEN
from ..core.tile import (
    get_tiles_in_bounds,
    get_tile_matrix_size,
    get_merged_bounds,
    estimate_tile_count,
    latlng_to_tile_float
)
from ..core.downloader import TileDownloader
from ..core.merger import merge_tiles, mask_image_by_polygon
from ..core.exporter import export_image, get_file_extension

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/sources")
async def get_tile_sources(tianditu_token: str = None):
    """Get available tile sources."""
    # Use custom token if provided, otherwise use default
    token = tianditu_token if tianditu_token else TIANDITU_DEFAULT_TOKEN
    
    # Convert config dictionary to simplified format for frontend
    result = {}
    for key, config in TILE_SOURCES.items():
        url = config["url"]
        # Replace token in Tianditu URLs
        if "tianditu" in key:
            url = url.replace(TIANDITU_DEFAULT_TOKEN, token)
        
        result[key] = {
            "id": key,
            "name": config["name"],
            "url": url,
            "subdomains": config.get("subdomains", []),
            "max_zoom": config["max_zoom"],
            "attribution": config["attribution"]
        }
    
    return result


@router.get("/formats")
async def get_output_formats():
    """Get available output formats."""
    return OUTPUT_FORMATS


@router.post("/estimate")
async def estimate_download(request: DownloadRequest):
    """Estimate download size and tile count."""
    if not request.bounds:
        raise HTTPException(status_code=400, detail="Bounds are required")
    
    bounds = request.bounds
    tile_count = estimate_tile_count(
        bounds.north, bounds.south, bounds.east, bounds.west, request.zoom
    )
    
    # Estimate file size (rough approximation)
    # Each tile is ~15-30KB for satellite imagery
    avg_tile_size_kb = 20
    estimated_size_mb = (tile_count * avg_tile_size_kb) / 1024
    
    # Check limits
    max_tiles = 1000000  # Increased limit
    if tile_count > max_tiles:
        return {
            "tile_count": tile_count,
            "estimated_size_mb": round(estimated_size_mb, 2),
            "warning": f"区域过大，超过 {max_tiles} 个瓦片限制。请缩小区域或降低缩放级别。",
            "allowed": False
        }
    
    return {
        "tile_count": tile_count,
        "estimated_size_mb": round(estimated_size_mb, 2),
        "allowed": True
    }


@router.post("/download")
async def download_tiles(request: DownloadRequest):
    """
    Download tiles and return merged image.
    
    This endpoint downloads all tiles in the specified bounds,
    merges them, and returns the result in the requested format.
    """
    # Validate request
    if not request.bounds and not request.polygon:
        raise HTTPException(status_code=400, detail="Either bounds or polygon is required")
    
    if request.source not in TILE_SOURCES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown source: {request.source}. Available: {list(TILE_SOURCES.keys())}"
        )
    
    if request.format.lower() not in ['geotiff', 'png', 'jpeg', 'jpg']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {request.format}. Supported: geotiff, png, jpeg"
        )
    
    # Get bounds from polygon if provided
    if request.polygon:
        lats = [p.lat for p in request.polygon]
        lngs = [p.lng for p in request.polygon]
        bounds = Bounds(
            north=max(lats),
            south=min(lats),
            east=max(lngs),
            west=min(lngs)
        )
    else:
        bounds = request.bounds
    
    # Check tile count limit
    tile_count = estimate_tile_count(
        bounds.north, bounds.south, bounds.east, bounds.west, request.zoom
    )
    
    max_tiles = 1000000
    if tile_count > max_tiles:
        raise HTTPException(
            status_code=400,
            detail=f"区域过大 ({tile_count} 瓦片)。最大允许 {max_tiles} 个瓦片。请缩小区域或降低缩放级别。"
        )
    
    # Get tiles to download
    tiles = get_tiles_in_bounds(
        bounds.north, bounds.south, bounds.east, bounds.west, request.zoom
    )
    
    # Get tile matrix info
    x_min, y_min, x_max, y_max, cols, rows = get_tile_matrix_size(
        bounds.north, bounds.south, bounds.east, bounds.west, request.zoom
    )
    
    # Download tiles
    downloader = TileDownloader(source=request.source, proxy=request.proxy, tianditu_token=request.tianditu_token)
    tile_images, progress = await downloader.download_tiles(tiles)
    
    if not tile_images:
        raise HTTPException(status_code=500, detail="Failed to download any tiles")
    
    # Merge tiles
    merged_image = merge_tiles(tile_images, x_min, y_min, x_max, y_max)
    
    # Crop to precise requested bounds
    nw_x, nw_y = latlng_to_tile_float(bounds.north, bounds.west, request.zoom)
    se_x, se_y = latlng_to_tile_float(bounds.south, bounds.east, request.zoom)
    
    left = int((nw_x - x_min) * TILE_SIZE)
    top = int((nw_y - y_min) * TILE_SIZE)
    right = int((se_x - x_min) * TILE_SIZE)
    bottom = int((se_y - y_min) * TILE_SIZE)
    
    # Ensure bounds are within image
    width, height = merged_image.size
    left = max(0, min(left, width))
    top = max(0, min(top, height))
    right = max(0, min(right, width))
    bottom = max(0, min(bottom, height))
    
    if right > left and bottom > top:
        merged_image = merged_image.crop((left, top, right, bottom))
    
    # Mask by polygon if requested
    if request.crop_to_shape and request.polygon:
        merged_image = mask_image_by_polygon(
            merged_image, 
            request.polygon, 
            (bounds.north, bounds.south, bounds.east, bounds.west)
        )
    
    # Export with requested bounds
    file_bytes, content_type = export_image(merged_image, bounds, request.format)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = get_file_extension(request.format)
    filename = f"map_{timestamp}_z{request.zoom}{ext}"
    
    # Return as streaming response
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(file_bytes))
        }
    )


@router.post("/download_with_progress")
async def download_tiles_with_progress(request: DownloadRequest):
    """
    Download tiles with real-time progress updates via Server-Sent Events.
    Returns task_id for progress tracking.
    """
    import uuid
    
    # Validate request (same as download)
    if not request.bounds and not request.polygon:
        raise HTTPException(status_code=400, detail="Either bounds or polygon is required")
    
    if request.source not in TILE_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unknown source: {request.source}")
    
    # Get bounds
    if request.polygon:
        lats = [p.lat for p in request.polygon]
        lngs = [p.lng for p in request.polygon]
        bounds = Bounds(north=max(lats), south=min(lats), east=max(lngs), west=min(lngs))
    else:
        bounds = request.bounds
    
    # Check tile count
    tile_count = estimate_tile_count(bounds.north, bounds.south, bounds.east, bounds.west, request.zoom)
    if tile_count > 1000000:
        raise HTTPException(status_code=400, detail="区域过大")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Store task info in memory (in production, use Redis or similar)
    if not hasattr(download_tiles_with_progress, 'tasks'):
        download_tiles_with_progress.tasks = {}
    
    download_tiles_with_progress.tasks[task_id] = {
        'status': 'pending',
        'progress': 0,
        'total': tile_count,
        'completed': 0
    }
    
    # Start download in background
    asyncio.create_task(_download_task(task_id, request, bounds))
    
    return {"task_id": task_id, "total": tile_count}


async def _download_task(task_id: str, request: DownloadRequest, bounds: Bounds):
    """Background task for downloading tiles."""
    try:
        tasks = download_tiles_with_progress.tasks
        tasks[task_id]['status'] = 'downloading'
        print(f"[Task {task_id}] Starting download...")
        
        # Get tiles
        tiles = get_tiles_in_bounds(bounds.north, bounds.south, bounds.east, bounds.west, request.zoom)
        print(f"[Task {task_id}] Found {len(tiles)} tiles to download")
        
        x_min, y_min, x_max, y_max, cols, rows = get_tile_matrix_size(
            bounds.north, bounds.south, bounds.east, bounds.west, request.zoom
        )
        
        # Download with progress callback
        def progress_callback(progress):
            tasks[task_id]['completed'] = progress.completed
            tasks[task_id]['failed'] = progress.failed
            percent = int(progress.completed / progress.total * 100) if progress.total > 0 else 0
            tasks[task_id]['progress'] = percent
            # Log every tile for debugging
            print(f"[Task {task_id}] Progress: {progress.completed}/{progress.total} ({percent}%)")
        
        downloader = TileDownloader(source=request.source, proxy=request.proxy, tianditu_token=request.tianditu_token)
        tile_images, progress = await downloader.download_tiles(tiles, progress_callback)
        print(f"[Task {task_id}] Download completed. Got {len(tile_images)} tiles")
        
        if not tile_images:
            print(f"[Task {task_id}] ERROR: No tiles downloaded")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = 'Failed to download tiles'
            return
        
        print(f"[Task {task_id}] Merging tiles...")
        tasks[task_id]['status'] = 'merging'
        merged_image = merge_tiles(tile_images, x_min, y_min, x_max, y_max)
        
        # Crop to precise requested bounds
        nw_x, nw_y = latlng_to_tile_float(bounds.north, bounds.west, request.zoom)
        se_x, se_y = latlng_to_tile_float(bounds.south, bounds.east, request.zoom)
        
        left = int((nw_x - x_min) * TILE_SIZE)
        top = int((nw_y - y_min) * TILE_SIZE)
        right = int((se_x - x_min) * TILE_SIZE)
        bottom = int((se_y - y_min) * TILE_SIZE)
        
        # Ensure bounds are within image
        width, height = merged_image.size
        left = max(0, min(left, width))
        top = max(0, min(top, height))
        right = max(0, min(right, width))
        bottom = max(0, min(bottom, height))
        
        if right > left and bottom > top:
            merged_image = merged_image.crop((left, top, right, bottom))
        
        # Mask by polygon if requested
        if request.crop_to_shape and request.polygon:
            print(f"[Task {task_id}] Masking by polygon...")
            merged_image = mask_image_by_polygon(
                merged_image, 
                request.polygon, 
                (bounds.north, bounds.south, bounds.east, bounds.west)
            )
        
        print(f"[Task {task_id}] Exporting to {request.format}...")
        tasks[task_id]['status'] = 'exporting'
        file_bytes, _ = export_image(merged_image, bounds, request.format)
        
        # Store result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = get_file_extension(request.format)
        filename = f"map_{timestamp}_z{request.zoom}{ext}"
        
        print(f"[Task {task_id}] Task completed! File size: {len(file_bytes)} bytes")
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['filename'] = filename
        tasks[task_id]['data'] = file_bytes
        
    except Exception as e:
        import traceback
        print(f"[Task {task_id}] ERROR: {e}")
        traceback.print_exc()
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)


@router.get("/download_progress/{task_id}")
async def get_download_progress(task_id: str):
    """Get download progress for a task (SSE endpoint)."""
    tasks = getattr(download_tiles_with_progress, 'tasks', {})
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        # Send initial status immediately
        yield f": keepalive\n\n"
        
        while True:
            if task_id not in tasks:
                break
            
            task = tasks[task_id]
            data = {
                'status': task['status'],
                'progress': task.get('progress', 0),
                'completed': task.get('completed', 0),
                'total': task.get('total', 0)
            }
            
            if task['status'] == 'failed':
                data['error'] = task.get('error', 'Unknown error')
            
            yield f"data: {json.dumps(data)}\n\n"
            
            if task['status'] in ['completed', 'failed']:
                break
            
            await asyncio.sleep(0.3)  # More frequent updates
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/download_result/{task_id}")
async def get_download_result(task_id: str):
    """Get the downloaded file."""
    tasks = getattr(download_tiles_with_progress, 'tasks', {})
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Download not completed")
    
    file_bytes = task.get('data')
    filename = task.get('filename', 'map.tif')
    
    if not file_bytes:
        raise HTTPException(status_code=500, detail="File data not found")
    
    # Get content type from filename
    if filename.endswith('.tif'):
        content_type = 'image/tiff'
    elif filename.endswith('.png'):
        content_type = 'image/png'
    else:
        content_type = 'image/jpeg'
    
    # Clean up task after a delay
    asyncio.create_task(_cleanup_task(task_id, 60))
    
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(file_bytes))
        }
    )


async def _cleanup_task(task_id: str, delay: int):
    """Clean up task data after delay."""
    await asyncio.sleep(delay)
    tasks = getattr(download_tiles_with_progress, 'tasks', {})
    if task_id in tasks:
        del tasks[task_id]


@router.post("/save_to_file/{task_id}")
async def save_to_file(task_id: str, save_path: str):
    """
    Save completed download directly to file (for desktop app).
    This avoids transferring data over network.
    """
    import os
    
    tasks = getattr(download_tiles_with_progress, 'tasks', {})
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Download not completed")
    
    file_bytes = task.get('data')
    
    if not file_bytes:
        raise HTTPException(status_code=500, detail="File data not found")
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Write file directly
        with open(save_path, 'wb') as f:
            f.write(file_bytes)
        
        # Clean up task data
        del tasks[task_id]
        
        return {"success": True, "path": save_path, "size": len(file_bytes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
