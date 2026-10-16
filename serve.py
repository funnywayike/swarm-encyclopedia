# -*- coding: utf-8 -*-
"""本地预览服务器：python serve.py [--port 8000] [--no-open]

为什么不直接用 `python -m http.server`：它的 MIME 类型取自系统注册表，Windows 上 .js/.mjs 常被标成
text/plain，浏览器会拒绝把它们当作 module 脚本执行（页面停在「交互演示正在加载…」）。
本脚本只依赖标准库，固定好 .js/.mjs/.wasm 等类型，并在端口被占用时自动换下一个。
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))

TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".zip": "application/zip",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".cnf": "text/plain; charset=utf-8",
    ".col": "text/plain; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # 本地预览：改了文件刷新即生效
        super().end_headers()

    def log_message(self, fmt, *args):  # 只打印出错请求，避免刷屏
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser(description="本地预览服务器")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()
    httpd = None
    for port in range(args.port, args.port + 20):
        try:
            httpd = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit(f"端口 {args.port}–{args.port + 19} 都被占用，请用 --port 指定其他端口")
    url = f"http://localhost:{httpd.server_address[1]}/"
    print(f"本地预览已启动：{url}    （关闭此窗口或按 Ctrl+C 停止）")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
