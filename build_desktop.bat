@echo off
chcp 65001 >nul
echo ========================================
echo TIF下载工具 - 桌面端打包脚本
echo ========================================
echo.

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装打包依赖
echo [1/4] 安装打包依赖...
pip install pywebview pyinstaller -q

:: 测试桌面端是否能正常运行
echo [2/4] 测试桌面端启动...
echo       (如果窗口正常显示，请手动关闭继续打包)
python desktop.py
if %errorlevel% neq 0 (
    echo 测试失败，请检查错误信息
    pause
    exit /b 1
)

:: 打包
echo [3/4] 开始打包...
pyinstaller tif_downloader.spec --noconfirm

:: 完成
echo.
echo ========================================
echo [4/4] 打包完成！
echo 输出目录: dist\TIF地图下载工具\
echo 运行: dist\TIF地图下载工具\TIF地图下载工具.exe
echo ========================================
pause
