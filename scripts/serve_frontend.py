"""
前端静态文件服务器（带异常处理）
解决 ConnectionAbortedError 等网络中断问题
"""
import http.server
import socketserver
import sys
import os
from functools import partial


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """安静的HTTP请求处理器 - 忽略常见的网络中断错误"""
    
    def log_message(self, format, *args):
        """自定义日志输出，只显示重要信息"""
        # 只记录非静态资源的请求
        if not any(ext in args[0] for ext in ['.css', '.js', '.png', '.jpg', '.ico', '.svg']):
            sys.stdout.write("%s - - [%s] %s\n" %
                           (self.address_string(),
                            self.log_date_time_string(),
                            format % args))
    
    def handle_one_request(self):
        """处理单个请求，捕获网络中断异常"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            # 客户端断开连接，这是正常情况（浏览器刷新/关闭等）
            # 不输出错误信息，避免干扰用户
            pass
        except Exception as e:
            # 其他异常仍然输出
            sys.stderr.write(f"⚠️  Request error: {e}\n")


def run_server(port=8080, directory="."):
    """启动HTTP服务器"""
    # 切换到指定目录
    os.chdir(directory)
    
    # 创建处理器（绑定目录）
    handler = partial(QuietHTTPRequestHandler, directory=".")
    
    # 创建服务器（允许端口复用）
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("=" * 50)
        print(f"🌐 前端服务器已启动")
        print(f"📍 地址: http://localhost:{port}")
        print(f"📁 目录: {os.path.abspath(directory)}")
        print("=" * 50)
        print("\n💡 按 Ctrl+C 停止服务器\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ 服务器已停止")
            sys.exit(0)


if __name__ == "__main__":
    # 从脚本目录返回到项目根目录，再进入 frontend
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    frontend_dir = os.path.join(project_root, "frontend")
    
    run_server(port=8080, directory=frontend_dir)
