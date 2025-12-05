"""Vector data download API endpoints."""

import json
import asyncio
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import aiohttp

router = APIRouter(prefix="/api/vector", tags=["vector"])

# OSM Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# OSM 要素类型配置
OSM_FEATURES = {
    "roads": {
        "name": "道路",
        "query": '[out:json];(way["highway"]({bbox}););out body;>;out skel qt;'
    },
    "buildings": {
        "name": "建筑",
        "query": '[out:json];(way["building"]({bbox});relation["building"]({bbox}););out body;>;out skel qt;'
    },
    "waterways": {
        "name": "水系",
        "query": '[out:json];(way["waterway"]({bbox});way["natural"="water"]({bbox});relation["natural"="water"]({bbox}););out body;>;out skel qt;'
    },
    "landuse": {
        "name": "土地利用",
        "query": '[out:json];(way["landuse"]({bbox});relation["landuse"]({bbox}););out body;>;out skel qt;'
    },
    "pois": {
        "name": "兴趣点",
        "query": '[out:json];(node["amenity"]({bbox});node["shop"]({bbox});node["tourism"]({bbox}););out body;'
    },
    "railways": {
        "name": "铁路",
        "query": '[out:json];(way["railway"]({bbox}););out body;>;out skel qt;'
    },
    "natural": {
        "name": "自然要素",
        "query": '[out:json];(way["natural"]({bbox});relation["natural"]({bbox}););out body;>;out skel qt;'
    },
    "boundaries": {
        "name": "边界",
        "query": '[out:json];(relation["boundary"="administrative"]({bbox}););out body;>;out skel qt;'
    }
}


@router.get("/osm_features")
async def get_osm_features():
    """获取可下载的 OSM 要素类型列表"""
    return {key: {"id": key, "name": config["name"]} for key, config in OSM_FEATURES.items()}


@router.post("/osm")
async def download_osm_data(
    feature_type: str,
    south: float,
    west: float,
    north: float,
    east: float,
    output_format: str = "geojson",
    proxy: Optional[str] = None
):
    """
    下载指定区域的 OSM 矢量数据
    
    - feature_type: 要素类型 (roads, buildings, waterways, etc.)
    - south, west, north, east: 边界框
    - output_format: 输出格式 (geojson, json)
    - proxy: 代理地址
    """
    if feature_type not in OSM_FEATURES:
        raise HTTPException(
            status_code=400,
            detail=f"未知的要素类型: {feature_type}。可用类型: {list(OSM_FEATURES.keys())}"
        )
    
    # 检查区域大小 (防止请求过大)
    area = (north - south) * (east - west)
    if area > 1:  # 约 100km x 100km
        raise HTTPException(
            status_code=400,
            detail="区域过大，请缩小选择范围 (最大约 100km x 100km)"
        )
    
    # 构建 Overpass 查询
    bbox = f"{south},{west},{north},{east}"
    query = OSM_FEATURES[feature_type]["query"].replace("{bbox}", bbox)
    
    print(f"[Vector] Downloading OSM {feature_type} for bbox: {bbox}")
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=120)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.post(
                OVERPASS_URL,
                data={"data": query},
                proxy=proxy if proxy else None
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Overpass API 错误: {error_text[:200]}"
                    )
                
                osm_data = await response.json()
    
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Overpass API 请求超时，请缩小区域重试")
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
    
    # 转换为 GeoJSON
    if output_format == "geojson":
        geojson = osm_to_geojson(osm_data, feature_type)
        content = json.dumps(geojson, ensure_ascii=False, indent=2)
        media_type = "application/geo+json"
        ext = ".geojson"
    else:
        content = json.dumps(osm_data, ensure_ascii=False, indent=2)
        media_type = "application/json"
        ext = ".json"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"osm_{feature_type}_{timestamp}{ext}"
    
    return Response(
        content=content.encode('utf-8'),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Filename": filename
        }
    )


def osm_to_geojson(osm_data: dict, feature_type: str) -> dict:
    """将 OSM JSON 转换为 GeoJSON"""
    features = []
    
    # 建立节点索引
    nodes = {}
    for element in osm_data.get("elements", []):
        if element["type"] == "node":
            nodes[element["id"]] = (element["lon"], element["lat"])
    
    # 处理要素
    for element in osm_data.get("elements", []):
        feature = None
        
        if element["type"] == "node" and "tags" in element:
            # 点要素
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [element["lon"], element["lat"]]
                },
                "properties": element.get("tags", {})
            }
        
        elif element["type"] == "way" and "nodes" in element:
            # 线/面要素
            coords = []
            for node_id in element["nodes"]:
                if node_id in nodes:
                    coords.append(list(nodes[node_id]))
            
            if len(coords) >= 2:
                # 判断是否闭合 (面)
                if coords[0] == coords[-1] and len(coords) >= 4:
                    geometry = {
                        "type": "Polygon",
                        "coordinates": [coords]
                    }
                else:
                    geometry = {
                        "type": "LineString",
                        "coordinates": coords
                    }
                
                feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": element.get("tags", {})
                }
        
        if feature:
            feature["properties"]["osm_id"] = element.get("id")
            feature["properties"]["osm_type"] = element.get("type")
            features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "source": "OpenStreetMap",
            "feature_type": feature_type,
            "timestamp": datetime.now().isoformat()
        }
    }


@router.post("/admin_boundary")
async def download_admin_boundary(
    code: str,
    output_format: str = "geojson",
    full: bool = True
):
    """
    下载行政区划边界
    
    - code: 行政区划代码
    - output_format: 输出格式 (geojson, json)
    - full: 是否包含完整边界 (full=True 下载完整版)
    """
    # 使用 DataV 的 GeoJSON API
    if full:
        url = f"https://geo.datav.aliyun.com/areas_v3/bound/{code}_full.json"
    else:
        url = f"https://geo.datav.aliyun.com/areas_v3/bound/{code}.json"
    
    print(f"[Vector] Downloading admin boundary: {code}")
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    # 尝试不带 _full 的版本
                    url = f"https://geo.datav.aliyun.com/areas_v3/bound/{code}.json"
                    async with session.get(url) as response2:
                        if response2.status != 200:
                            raise HTTPException(status_code=404, detail=f"找不到行政区划: {code}")
                        geojson = await response2.json()
                elif response.status != 200:
                    raise HTTPException(status_code=response.status, detail="获取边界数据失败")
                else:
                    geojson = await response.json()
    
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
    
    # 添加元数据
    if "properties" not in geojson:
        geojson["properties"] = {}
    geojson["properties"]["adcode"] = code
    geojson["properties"]["source"] = "DataV.GeoAtlas"
    geojson["properties"]["timestamp"] = datetime.now().isoformat()
    
    content = json.dumps(geojson, ensure_ascii=False, indent=2)
    
    # 获取名称
    name = code
    if geojson.get("features") and len(geojson["features"]) > 0:
        props = geojson["features"][0].get("properties", {})
        name = props.get("name", code)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"admin_{name}_{timestamp}.geojson"
    
    return Response(
        content=content.encode('utf-8'),
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Filename": filename
        }
    )


from pydantic import BaseModel
from fastapi import UploadFile, File
import tempfile
import zipfile
import shutil

class SaveFileRequest(BaseModel):
    data: str
    save_path: str
    filename: str


@router.post("/save_to_file")
async def save_vector_to_file(request: SaveFileRequest):
    """
    将矢量数据直接保存到文件 (桌面端使用)
    """
    import os
    
    try:
        # 确保目录存在
        dir_path = os.path.dirname(request.save_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # 写入文件
        with open(request.save_path, 'w', encoding='utf-8') as f:
            f.write(request.data)
        
        return {"success": True, "path": request.save_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.post("/convert_shapefile")
async def convert_shapefile(file: UploadFile = File(...)):
    """
    将 Shapefile (ZIP) 转换为 GeoJSON
    """
    import os
    
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="请上传 ZIP 压缩的 Shapefile")
    
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'upload.zip')
        
        # 保存上传的文件
        with open(zip_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # 解压
        extract_dir = os.path.join(temp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        
        # 查找 .shp 文件
        shp_file = None
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith('.shp'):
                    shp_file = os.path.join(root, f)
                    break
            if shp_file:
                break
        
        if not shp_file:
            raise HTTPException(status_code=400, detail="ZIP 中找不到 .shp 文件")
        
        # 使用 fiona 或 pyshp 读取
        try:
            import shapefile
            geojson = shapefile_to_geojson(shp_file)
        except ImportError:
            # 如果没有 pyshp，尝试用 fiona
            try:
                import fiona
                geojson = fiona_to_geojson(shp_file)
            except ImportError:
                raise HTTPException(
                    status_code=500, 
                    detail="服务器缺少 Shapefile 读取库，请安装 pyshp 或 fiona"
                )
        
        return geojson
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shapefile 转换失败: {str(e)}")
    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def shapefile_to_geojson(shp_path: str) -> dict:
    """Use pyshp to convert shapefile to GeoJSON, with coordinate transformation"""
    import shapefile
    import os
    
    # 检查是否需要坐标转换
    prj_path = os.path.splitext(shp_path)[0] + '.prj'
    transformer = None
    
    if os.path.exists(prj_path):
        try:
            from pyproj import CRS, Transformer
            with open(prj_path, 'r') as f:
                prj_text = f.read()
            
            src_crs = CRS.from_wkt(prj_text)
            dst_crs = CRS.from_epsg(4326)  # WGS84
            
            # 检查是否已经是 WGS84
            if not src_crs.equals(dst_crs):
                transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
                print(f"[Shapefile] Will transform from {src_crs.name} to WGS84")
            else:
                print(f"[Shapefile] Already in WGS84, no transformation needed")
        except ImportError:
            print(f"[Shapefile] pyproj not available, coordinates may be incorrect")
        except Exception as e:
            print(f"[Shapefile] Could not parse PRJ: {e}")
    
    # 尝试不同编码打开
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    sf = None
    
    for encoding in encodings:
        try:
            sf = shapefile.Reader(shp_path, encoding=encoding)
            if len(sf) > 0:
                _ = sf.shapeRecord(0)
            break
        except Exception as e:
            continue
    
    if sf is None:
        sf = shapefile.Reader(shp_path)
    
    features = []
    
    for shape_rec in sf.shapeRecords():
        geom = shape_rec.shape.__geo_interface__
        
        # 如果需要坐标转换
        if transformer:
            geom = transform_geometry(geom, transformer)
        
        props = dict(zip([f[0] for f in sf.fields[1:]], shape_rec.record))
        
        # 处理编码问题
        clean_props = {}
        for k, v in props.items():
            if isinstance(v, bytes):
                for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        v = v.decode(enc)
                        break
                    except:
                        continue
                else:
                    v = str(v)
            clean_props[k] = v
        
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": clean_props
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def transform_geometry(geom: dict, transformer) -> dict:
    """转换几何坐标"""
    geom_type = geom.get('type')
    coords = geom.get('coordinates')
    
    if geom_type == 'Point':
        new_coords = transformer.transform(coords[0], coords[1])
        return {'type': 'Point', 'coordinates': list(new_coords)}
    
    elif geom_type == 'LineString':
        new_coords = [list(transformer.transform(x, y)) for x, y in coords]
        return {'type': 'LineString', 'coordinates': new_coords}
    
    elif geom_type == 'Polygon':
        new_coords = []
        for ring in coords:
            new_ring = [list(transformer.transform(x, y)) for x, y in ring]
            new_coords.append(new_ring)
        return {'type': 'Polygon', 'coordinates': new_coords}
    
    elif geom_type == 'MultiPoint':
        new_coords = [list(transformer.transform(x, y)) for x, y in coords]
        return {'type': 'MultiPoint', 'coordinates': new_coords}
    
    elif geom_type == 'MultiLineString':
        new_coords = []
        for line in coords:
            new_line = [list(transformer.transform(x, y)) for x, y in line]
            new_coords.append(new_line)
        return {'type': 'MultiLineString', 'coordinates': new_coords}
    
    elif geom_type == 'MultiPolygon':
        new_coords = []
        for polygon in coords:
            new_polygon = []
            for ring in polygon:
                new_ring = [list(transformer.transform(x, y)) for x, y in ring]
                new_polygon.append(new_ring)
            new_coords.append(new_polygon)
        return {'type': 'MultiPolygon', 'coordinates': new_coords}
    
    return geom


def fiona_to_geojson(shp_path: str) -> dict:
    """Use fiona to convert shapefile to GeoJSON"""
    import fiona
    
    features = []
    with fiona.open(shp_path, 'r') as src:
        for feature in src:
            features.append(dict(feature))
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.post("/convert_shapefiles")
async def convert_shapefiles(files: List[UploadFile] = File(...)):
    """
    将多个 Shapefile 组件文件 (.shp, .shx, .dbf, .prj) 转换为 GeoJSON
    """
    import os
    
    print(f"[Shapefile] Received {len(files)} files")
    for f in files:
        print(f"  - {f.filename}")
    
    # 检查是否有 .shp 文件
    shp_files = [f for f in files if f.filename.lower().endswith('.shp')]
    if not shp_files:
        raise HTTPException(status_code=400, detail="请选择 .shp 文件")
    
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        print(f"[Shapefile] Temp dir: {temp_dir}")
        
        # 保存所有上传的文件，统一文件名前缀
        shp_basename = os.path.splitext(shp_files[0].filename)[0]
        
        for file in files:
            # 获取扩展名
            ext = os.path.splitext(file.filename)[1].lower()
            # 使用统一的基础名 + 小写扩展名
            new_filename = shp_basename + ext
            file_path = os.path.join(temp_dir, new_filename)
            
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            print(f"[Shapefile] Saved: {new_filename} ({len(content)} bytes)")
        
        # 查找 .shp 文件路径
        shp_path = os.path.join(temp_dir, shp_basename + '.shp')
        print(f"[Shapefile] SHP path: {shp_path}")
        
        # 检查必需的配套文件
        base_name = os.path.splitext(shp_path)[0]
        required_exts = ['.shx', '.dbf']
        missing = []
        for ext in required_exts:
            check_path = base_name + ext
            if not os.path.exists(check_path):
                missing.append(ext)
            else:
                print(f"[Shapefile] Found: {ext}")
        
        if missing:
            # 列出目录内容
            dir_contents = os.listdir(temp_dir)
            print(f"[Shapefile] Directory contents: {dir_contents}")
            raise HTTPException(
                status_code=400, 
                detail=f"缺少必需的配套文件: {', '.join(missing)}。请同时选择 .shp, .shx, .dbf 文件"
            )
        
        # 使用 pyshp 读取
        try:
            import shapefile
            print(f"[Shapefile] Using pyshp to read...")
            geojson = shapefile_to_geojson(shp_path)
            print(f"[Shapefile] Converted to GeoJSON with {len(geojson.get('features', []))} features")
            
            # 调试：打印第一个要素的几何信息
            if geojson.get('features'):
                first_geom = geojson['features'][0].get('geometry', {})
                geom_type = first_geom.get('type')
                coords = first_geom.get('coordinates')
                print(f"[Shapefile] First feature geometry type: {geom_type}")
                if coords:
                    # 显示坐标结构
                    if geom_type == 'Polygon':
                        print(f"[Shapefile] First ring has {len(coords[0])} points")
                        print(f"[Shapefile] First point: {coords[0][0]}")
                    elif geom_type == 'MultiPolygon':
                        print(f"[Shapefile] Has {len(coords)} polygons")
                        print(f"[Shapefile] First polygon first point: {coords[0][0][0]}")
                    elif geom_type == 'Point':
                        print(f"[Shapefile] Point: {coords}")
        except ImportError:
            try:
                import fiona
                geojson = fiona_to_geojson(shp_path)
            except ImportError:
                raise HTTPException(
                    status_code=500, 
                    detail="服务器缺少 Shapefile 读取库"
                )
        except Exception as e:
            print(f"[Shapefile] Error reading: {e}")
            raise
        
        return geojson
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Shapefile 转换失败: {str(e)}")
    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
