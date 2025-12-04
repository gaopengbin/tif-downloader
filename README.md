# TIF 地图下载工具 (Map Downloader)

一个功能强大的地图瓦片下载与拼接工具，支持多种在线图源，可将瓦片拼接并导出为 GeoTIFF、PNG 或 JPEG 格式。同时支持矢量数据（OSM、行政区划）下载与查看。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)
![Leaflet](https://img.shields.io/badge/frontend-Leaflet-199900.svg)

## ✨ 主要功能

### 🗺️ 地图瓦片下载
- **多图源支持**：Google Maps/Satellite, OpenStreetMap, 天地图 (矢量/影像), ArcGIS, Carto 等
- **高精度拼接**：自动下载指定区域瓦片并无缝拼接
- **多种格式**：导出带有地理坐标信息的 **GeoTIFF**，或普通 **PNG/JPEG** 图像
- **按边界裁剪**：支持按行政区划或自定义多边形裁剪，生成透明背景图像
- **大图支持**：优化的内存管理，支持下载百万级瓦片

### 📍 矢量数据工具
- **OSM 下载**：支持下载选定区域的 OpenStreetMap 矢量数据（道路、建筑、水系、POI 等）
- **行政区划**：自动获取中国省/市/区县的 GeoJSON 边界数据
- **本地加载**：支持加载查看本地 GeoJSON 和 Shapefile (zip) 文件
- **格式转换**：内置 Shapefile 转 GeoJSON 工具

### 🖥️ 桌面端体验
- **原生应用**：基于 PyWebView 的独立桌面程序，无需浏览器即可运行
- **文件对话框**：原生文件保存体验，直接保存到本地磁盘
- **智能交互**：地名搜索自动定位行政区划，坐标网格显示

## 🚀 快速开始

### 环境要求
- Python 3.10 或更高版本
- GDAL (通常通过 rasterio 安装)

### 安装依赖

```bash
# 创建虚拟环境 (推荐)
python -m venv venv
# Windows 激活
venv\Scripts\activate
# Linux/Mac 激活
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行 Web 版

```bash
# Windows
run.bat

# 或手动运行
uvicorn app.main:app --reload
```
访问 http://127.0.0.1:8000

### 运行桌面版

```bash
python desktop.py
```

## 📦 打包发布

本项目支持打包为 Windows 可执行文件 (.exe)。

```bash
# 安装打包工具
pip install pywebview pyinstaller

# 运行打包脚本
build_desktop.bat
```
打包完成后，可执行文件位于 `dist/TIF地图下载工具/` 目录。

## 🛠️ 技术栈

- **后端**：FastAPI, Uvicorn, Rasterio (GDAL), PIL (Pillow), PyShp
- **前端**：HTML5, CSS3 (GeoAI Pro Theme), JavaScript, Leaflet.js, Leaflet.Draw
- **桌面封装**：PyWebView, PyInstaller

## 📝 注意事项

- **天地图 Key**：本项目内置了测试用 Key，建议在 `app/config.py` 中替换为您自己的天地图 Key。
- **网络代理**：访问 Google 等国外图源时，请在界面勾选"启用代理"并配置正确的代理地址 (默认 http://127.0.0.1:10808)。
- **版权声明**：下载的地图数据版权归原图商所有，请遵守相关使用条款。

## 📄 许可证

MIT License
