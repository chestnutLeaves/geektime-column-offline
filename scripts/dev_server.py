"""从项目根目录提供本机静态预览，仅开放网站内容，禁用开发缓存。"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from public_paths import is_public_path


class PreviewHandler(SimpleHTTPRequestHandler):
    """首页与维护文件共用项目根目录时，按白名单隔离内部文件。"""

    def send_head(self):
        target = Path(self.translate_path(self.path))
        if not is_public_path(self.directory, target):
            self.send_error(404, 'Page not found')
            return None
        return super().send_head()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404, 'Page not found')
        return None


def main():
    """固定绑定回环地址；端口可覆盖，路径始终从脚本位置定位。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18890, help='本机预览端口，默认 18890')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / 'index.html').is_file():
        parser.error('缺少根目录 index.html，请先生成首页。')
    handler = partial(PreviewHandler, directory=str(root))
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        print(f'Local: http://127.0.0.1:{args.port}/', flush=True)
        print('从项目根目录提供网页；修改后刷新即可，Ctrl+C 停止。', flush=True)
        if not (root / 'assets').is_dir():
            print('尚未安装图片资源包。请按 README 导入资源后完整阅读。', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
