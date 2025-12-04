"""Geocode API for place name search."""

from typing import List, Optional
import aiohttp

from fastapi import APIRouter, HTTPException, Query

from ..models import GeocodeResult, Bounds
from ..config import NOMINATIM_API, HTTP_PROXY

router = APIRouter(prefix="/api", tags=["geocode"])


@router.get("/geocode", response_model=List[GeocodeResult])
async def search_place(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(5, ge=1, le=20, description="返回结果数量")
):
    """
    Search for places by name using Nominatim API.
    
    Args:
        q: Search query (place name)
        limit: Maximum number of results
    
    Returns:
        List of matching places with coordinates
    """
    params = {
        "q": q,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
        "extratags": 1
    }
    
    headers = {
        "User-Agent": "TIF-Downloader/1.0 (Educational Project)"
    }
    
    try:
        # Disable SSL verification for environments with certificate issues
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                NOMINATIM_API,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
                proxy=HTTP_PROXY
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail="Geocoding service error"
                    )
                
                data = await response.json()
                
                results = []
                for item in data:
                    # Parse bounds if available
                    bounds = None
                    if "boundingbox" in item:
                        bb = item["boundingbox"]
                        bounds = Bounds(
                            south=float(bb[0]),
                            north=float(bb[1]),
                            west=float(bb[2]),
                            east=float(bb[3])
                        )
                    
                    results.append(GeocodeResult(
                        name=item.get("name", item.get("display_name", "").split(",")[0]),
                        display_name=item.get("display_name", ""),
                        lat=float(item["lat"]),
                        lng=float(item["lon"]),
                        bounds=bounds,
                        address=item.get("address", {})
                    ))
                
                return results
    
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding error: {str(e)}")
