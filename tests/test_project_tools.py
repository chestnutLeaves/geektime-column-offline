"""检查根目录静态服务的隔离边界及资源包的完整性处理。"""
import hashlib
from http.server import ThreadingHTTPServer
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dev_server import PreviewHandler
from public_paths import iter_public_files
from resources import export_resources, import_resources


class ProjectToolsTest(unittest.TestCase):
    """使用小型临时项目检查关键行为，不依赖完整资料或真实外网。"""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='reading-library-test-')
        self.root = Path(self.directory.name).resolve()
        self.root.joinpath('data/manifests').mkdir(parents=True)
        self.root.joinpath('assets').mkdir()
        self.payload = b'example-resource'
        self.root.joinpath('assets/example.png').write_bytes(self.payload)
        self.row = {'target': 'assets/example.png', 'size': len(self.payload), 'sha256': hashlib.sha256(self.payload).hexdigest()}
        self.root.joinpath('data/manifests/resources.jsonl').write_text(json.dumps(self.row) + '\n', encoding='utf-8')

    def tearDown(self):
        self.directory.cleanup()

    def test_export_import_preserves_resource(self):
        """完整资源包可恢复丢失资源，并与清单逐字节一致。"""
        bundle = self.root / 'resources.zip'
        self.assertEqual(export_resources(self.root, bundle), 1)
        self.root.joinpath('assets/example.png').unlink()
        self.assertEqual(import_resources(self.root, bundle), 1)
        self.assertEqual(self.root.joinpath('assets/example.png').read_bytes(), self.payload)

    def test_invalid_bundle_does_not_overwrite_existing_resource(self):
        """包内字节不符时不能损坏当前可用图片。"""
        bundle = self.root / 'bad.zip'
        with zipfile.ZipFile(bundle, 'w') as archive:
            archive.writestr(self.row['target'], b'x' * self.row['size'])
        with self.assertRaises(ValueError):
            import_resources(self.root, bundle)
        self.assertEqual(self.root.joinpath('assets/example.png').read_bytes(), self.payload)

    def test_bundle_cannot_write_extra_project_files(self):
        """额外脚本及目录穿越均被拒绝。"""
        for name in ['../escaped.txt', 'scripts/tool.py', 'assets/../index.html']:
            with self.subTest(name=name):
                bundle = self.root / 'extra.zip'
                with zipfile.ZipFile(bundle, 'w') as archive:
                    archive.writestr(self.row['target'], self.payload)
                    archive.writestr(name, b'extra')
                with self.assertRaises(ValueError):
                    import_resources(self.root, bundle)
        self.assertFalse(self.root.joinpath('scripts/tool.py').exists())

    def test_public_files_and_http_exclude_internal_directories(self):
        """项目与网站共用根目录，HTTP 仍只能读取白名单内的公开内容。"""
        self.root.joinpath('index.html').write_text('<h1>Library</h1>', encoding='utf-8')
        self.root.joinpath('.git').mkdir()
        self.root.joinpath('.git/config').write_text('private', encoding='utf-8')
        self.root.joinpath('assets/.hidden').write_text('private', encoding='utf-8')
        self.root.joinpath('data/review.json').write_text('{}', encoding='utf-8')
        names = {path.relative_to(self.root).as_posix() for path in iter_public_files(self.root)}
        self.assertEqual(names, {'index.html', 'assets/example.png'})
        handler = partial(PreviewHandler, directory=str(self.root))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(origin + '/') as response:
                self.assertEqual(response.status, 200)
                self.assertIn('text/html', response.headers['Content-Type'])
            for path in ['/data/review.json', '/.git/config', '/%2egit/config', '/assets/.hidden', '/assets/../data/review.json']:
                with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(origin + path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
