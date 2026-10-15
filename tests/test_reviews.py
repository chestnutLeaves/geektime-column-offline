"""验证维护时能发现漏评、错配、证据变化及不安全路径。"""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_reviews import local_file, validate_document


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / 'articles').mkdir()
        self.body = '<h1>示例文章</h1><p>已审阅内容</p>'
        (self.project / 'articles/example.html').write_text('<main class="reading-main" id="main-content">' + self.body + '<footer class="reading-footer">', encoding='utf-8')
        self.path = '/articles/example.html'
        self.expected = {self.path: '示例文章'}
        self.data = dict(schema_version=1, kind='articles', reviewed_at='2026-10-15', reviewer='测试', methodology='正文摘样', references={}, entries=[dict(path=self.path, title='示例文章', recommendation='recommended', currency='stable', summary='阅读价值', currency_note='原理稳定', reading_advice='配合实验', reference_ids=[], evidence=[dict(path=self.path, title='示例文章', sha256=hashlib.sha256(self.body.encode()).hexdigest())])])

    def test_complete_review_passes(self):
        self.assertEqual(validate_document(self.project, self.data, 'articles', self.expected), 1)

    def test_missing_duplicate_and_mismatched_reviews_fail(self):
        for mutation in ('missing', 'duplicate', 'title', 'reference', 'hash'):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                if mutation == 'missing': data['entries'] = []
                elif mutation == 'duplicate': data['entries'] *= 2
                elif mutation == 'title': data['entries'][0]['title'] = '另一篇文章'
                elif mutation == 'reference': data['entries'][0]['reference_ids'] = ['不存在']
                else: data['entries'][0]['evidence'][0]['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    validate_document(self.project, data, 'articles', self.expected)

    def test_untrusted_paths_fail(self):
        for path in ('//example.org/a.html', '/articles/../example.html', '/articles/example.html?q=1', '/articles\\example.html', '/data/private.html'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                local_file(self.project, path)


if __name__ == '__main__':
    unittest.main()
