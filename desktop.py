"""
TIF下载工具 - 桌面端入口
使用 pywebview 将 FastAPI 应用嵌入到桌面窗口中
"""

import os
import sys
import threading
import time
import socket
import webview
import uvicorn

# 确保能找到 app 模块
if getattr(sys, 'frozen', False):
    # 打包后的路径
    BASE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)
else:
    # 开发环境
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 设置环境变量
os.environ['PROJ_DATA'] = os.path.join(BASE_DIR, 'proj_data')

from app.main import app


# 全局变量存储窗口引用
_window = None


class Api:
    """暴露给前端的 Python API"""
    
    def save_file_dialog(self, default_filename: str):
        """
        打开系统原生的保存文件对话框
        返回用户选择的保存路径，如果取消则返回 None
        """
        global _window
        if not _window:
            print("Window not initialized")
            return None
        
        # 获取默认目录（用户的下载文件夹或桌面）
        default_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(default_dir):
            default_dir = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser('~')
        
        print(f"Opening save dialog: {default_filename} in {default_dir}")
        
        try:
            # pywebview 6.x 使用 SAVE_DIALOG
            dialog_type = getattr(webview, 'SAVE_DIALOG', None)
            if dialog_type is None:
                # 新版本可能用 FileDialog.SAVE
                dialog_type = webview.SAVE_DIALOG if hasattr(webview, 'SAVE_DIALOG') else 1
            
            result = _window.create_file_dialog(
                dialog_type,
                directory=default_dir,
                save_filename=default_filename
            )
            print(f"Dialog result: {result}")
        except Exception as e:
            print(f"File dialog error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # pywebview 返回元组或字符串，统一处理
        if result:
            if isinstance(result, (list, tuple)):
                path = result[0] if result else None
            else:
                path = result
            print(f"Selected path: {path}")
            return path
        print("Dialog cancelled")
        return None
    
    def is_desktop(self):
        """检查是否运行在桌面端"""
        return True
    
    def get_default_save_dir(self):
        """获取默认保存目录"""
        default_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(default_dir):
            default_dir = os.path.join(os.path.expanduser('~'), 'Desktop')
        return default_dir


def find_free_port():
    """找一个可用的端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_server(port, timeout=30):
    """等待服务器启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', port))
                return True
        except ConnectionRefusedError:
            time.sleep(0.1)
    return False


def run_server(port):
    """在后台线程中运行 FastAPI 服务器"""
    config = uvicorn.Config(
        app,
        host='127.0.0.1',
        port=port,
        log_level='warning',
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    global _window
    
    # 找一个可用端口
    port = find_free_port()
    url = f'http://127.0.0.1:{port}'
    
    # 在后台线程启动服务器
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    if not wait_for_server(port):
        print("服务器启动超时")
        sys.exit(1)
    
    # 创建 API 实例
    api = Api()
    
    # 创建桌面窗口，pywebview 6.x 在 create_window 中指定 js_api
    _window = webview.create_window(
        title='TIF地图下载工具',
        url=url,
        width=1400,
        height=900,
        min_size=(1000, 700),
        resizable=True,
        text_select=True,
        js_api=api
    )
    
    # 启动窗口 (阻塞直到窗口关闭)
    webview.start()


if __name__ == '__main__':
    main()
