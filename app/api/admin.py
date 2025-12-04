"""Administrative regions API using DataV."""

from typing import List, Optional, Dict, Any
import aiohttp

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..config import DATAV_API, DATAV_FULL_API, HTTP_PROXY

router = APIRouter(prefix="/api/admin", tags=["admin"])

# China administrative division codes
CHINA_CODE = "100000"

# Province codes cache
PROVINCE_CODES: Dict[str, str] = {}


async def fetch_geojson(url: str) -> Dict[str, Any]:
    """Fetch GeoJSON from DataV API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        # Disable SSL verification for environments with certificate issues
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # DataV is a domestic (China) service, NO proxy needed
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"DataV API error: {response.status}"
                    )
                return await response.json()
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")


@router.get("/provinces")
async def get_provinces():
    """
    Get list of provinces in China.
    
    Returns list of province objects with code, name, and center coordinates.
    """
    url = DATAV_FULL_API.format(code=CHINA_CODE)
    
    try:
        data = await fetch_geojson(url)
        
        provinces = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            
            # Get center point
            center = props.get("center", [])
            if not center and feature.get("geometry"):
                # Calculate center from geometry if not provided
                coords = feature["geometry"].get("coordinates", [])
                if coords:
                    # Simple centroid for polygon
                    pass  # Use provided center
            
            provinces.append({
                "code": str(props.get("adcode", "")),
                "name": props.get("name", ""),
                "center": center,
                "level": "province"
            })
        
        # Sort by code
        provinces.sort(key=lambda x: x["code"])
        
        return provinces
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading provinces: {str(e)}")


@router.get("/cities")
async def get_cities(province_code: str = Query(..., description="省份代码")):
    """
    Get list of cities in a province.
    
    Args:
        province_code: Province administrative code (e.g., "110000" for Beijing)
    """
    url = DATAV_FULL_API.format(code=province_code)
    
    try:
        data = await fetch_geojson(url)
        
        cities = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            
            cities.append({
                "code": str(props.get("adcode", "")),
                "name": props.get("name", ""),
                "center": props.get("center", []),
                "level": "city"
            })
        
        cities.sort(key=lambda x: x["code"])
        
        return cities
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading cities: {str(e)}")


@router.get("/districts")
async def get_districts(city_code: str = Query(..., description="城市代码")):
    """
    Get list of districts in a city.
    
    Args:
        city_code: City administrative code (e.g., "110100" for Beijing urban)
    """
    url = DATAV_FULL_API.format(code=city_code)
    
    try:
        data = await fetch_geojson(url)
        
        districts = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            
            districts.append({
                "code": str(props.get("adcode", "")),
                "name": props.get("name", ""),
                "center": props.get("center", []),
                "level": "district"
            })
        
        districts.sort(key=lambda x: x["code"])
        
        return districts
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading districts: {str(e)}")


@router.get("/boundary")
async def get_boundary(code: str = Query(..., description="行政区划代码")):
    """
    Get GeoJSON boundary for an administrative region.
    
    Args:
        code: Administrative code (province/city/district)
    
    Returns:
        GeoJSON FeatureCollection with boundary polygon
    """
    url = DATAV_API.format(code=code)
    
    try:
        data = await fetch_geojson(url)
        return data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boundary_full")
async def get_boundary_full(code: str = Query(..., description="行政区划代码")):
    """
    Get GeoJSON boundary with sub-regions for an administrative region.
    
    Args:
        code: Administrative code (province/city)
    
    Returns:
        GeoJSON FeatureCollection with boundary and sub-region polygons
    """
    url = DATAV_FULL_API.format(code=code)
    
    try:
        data = await fetch_geojson(url)
        return data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
