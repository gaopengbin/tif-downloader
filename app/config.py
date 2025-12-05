"""Configuration for tile sources and application settings."""

from typing import Dict, Any

# 瓦片大小 (像素)
TILE_SIZE = 256

# 支持的图源配置
TILE_SOURCES: Dict[str, Dict[str, Any]] = {
    "google_satellite": {
        "name": "Google 卫星",
        "url": "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "subdomains": ["0", "1", "2", "3"],
        "max_zoom": 20,
        "attribution": "© Google"
    },
    "google_map": {
        "name": "Google 地图",
        "url": "https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "subdomains": ["0", "1", "2", "3"],
        "max_zoom": 20,
        "attribution": "© Google"
    },
    "google_hybrid": {
        "name": "Google 混合",
        "url": "https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "subdomains": ["0", "1", "2", "3"],
        "max_zoom": 20,
        "attribution": "© Google"
    },
    "osm": {
        "name": "OpenStreetMap",
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "subdomains": ["a", "b", "c"],
        "max_zoom": 19,
        "attribution": "© OpenStreetMap contributors"
    },
    "arcgis_satellite": {
        "name": "ArcGIS 卫星",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "subdomains": [],
        "max_zoom": 19,
        "attribution": "© Esri"
    },
    "carto_light": {
        "name": "Carto Light",
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "subdomains": ["a", "b", "c", "d"],
        "max_zoom": 19,
        "attribution": "© CARTO"
    },
    "carto_dark": {
        "name": "Carto Dark",
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "subdomains": ["a", "b", "c", "d"],
        "max_zoom": 19,
        "attribution": "© CARTO"
    },
    "tianditu_satellite": {
        "name": "天地图 卫星",
        "url": "https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=436ce7e50d27eede2f2929307e6b33c0",
        "subdomains": ["0", "1", "2", "3", "4", "5", "6", "7"],
        "max_zoom": 18,
        "attribution": "© 天地图"
    },
    "tianditu_vector": {
        "name": "天地图 矢量",
        "url": "https://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=436ce7e50d27eede2f2929307e6b33c0",
        "subdomains": ["0", "1", "2", "3", "4", "5", "6", "7"],
        "max_zoom": 18,
        "attribution": "© 天地图"
    }
}

# 输出格式
OUTPUT_FORMATS = ["geotiff", "png", "jpeg"]

# 下载设置
DOWNLOAD_SETTINGS = {
    "max_concurrent": 10,  # 最大并发下载数
    "retry_times": 3,      # 重试次数
    "timeout": 30,         # 超时时间 (秒)
    "delay": 0.1,          # 请求间隔 (秒)
}

# User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 阿里云 DataV 行政区划 API
DATAV_API = "https://geo.datav.aliyun.com/areas_v3/bound/{code}.json"
DATAV_FULL_API = "https://geo.datav.aliyun.com/areas_v3/bound/{code}_full.json"

# Nominatim 地名搜索 API
NOMINATIM_API = "https://nominatim.openstreetmap.org/search"

# HTTP 代理设置 (如果需要)
# 格式: "http://127.0.0.1:7890" 或 None
HTTP_PROXY = "http://127.0.0.1:10808"  # V2Ray 代理

# 天地图默认 Token
TIANDITU_DEFAULT_TOKEN = "436ce7e50d27eede2f2929307e6b33c0"
