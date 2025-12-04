@echo off
echo ========================================
echo TIF下载工具 - 安装依赖
echo ========================================

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖 (使用阿里云镜像)
echo 正在安装依赖...
pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com fastapi uvicorn aiohttp Pillow requests pydantic numpy aiofiles

:: rasterio 安装较复杂，可能需要单独处理
echo.
echo 尝试安装 rasterio (GeoTIFF支持)...
pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com rasterio

echo.
echo ========================================
echo 安装完成!
echo 如果 rasterio 安装失败，可以:
echo 1. 从 https://www.lfd.uci.edu/~gohlke/pythonlibs/ 下载 rasterio wheel
echo 2. 使用 conda 安装: conda install rasterio
echo 3. 不安装 rasterio 也可使用 (仅PNG/JPEG输出)
echo ========================================
pause
