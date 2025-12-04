@echo off
echo ========================================
echo TIF下载工具 - 启动脚本
echo ========================================

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 设置PROJ数据库路径，避免版本冲突
set PROJ_DATA=%~dp0venv\Lib\site-packages\rasterio\proj_data

:: 启动服务
echo 正在启动服务...
echo 访问地址: http://localhost:8000
echo 按 Ctrl+C 停止服务
echo ========================================

uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
