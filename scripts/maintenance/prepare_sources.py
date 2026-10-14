"""按 data/upstream.json 锁定的提交准备 bare 仓库，仅完整重建时显式运行。"""
import argparse
import json
from pathlib import Path
import re
import subprocess


def main():
    """读取固定版本，不自动追踪远程最新分支，也不检出原仓库代码。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    project = args.project.resolve()
    records = json.loads((project / 'data/upstream.json').read_text(encoding='utf-8'))['repositories']
    names = {'yvan': 'Yvan0329-lianglianglee.git', 'xixi': 'xixiwenxuanhe-learn-liangliang.git'}
    for key, name in names.items():
        record = records[key]
        commit = record['commit']
        if not re.fullmatch(r'[0-9a-f]{40}', commit) or not record['url'].startswith('https://github.com/'):
            raise ValueError('原始仓库配置必须包含明确的 GitHub HTTPS 地址与完整提交号。')
        target = project / '.cache/upstream' / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'init', '--bare', str(target)], check=True)
            subprocess.run(['git', '--git-dir', str(target), 'remote', 'add', 'origin', record['url']], check=True)
        remote = subprocess.check_output(['git', '--git-dir', str(target), 'remote', 'get-url', 'origin'], text=True).strip()
        if remote != record['url']:
            raise ValueError('已有缓存仓库的来源不一致，停止操作。')
        subprocess.run(['git', '--git-dir', str(target), 'fetch', '--depth=1', 'origin', commit], check=True)
        subprocess.run(['git', '--git-dir', str(target), 'update-ref', 'HEAD', commit], check=True)
        actual = subprocess.check_output(['git', '--git-dir', str(target), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise ValueError('原始仓库版本校验失败。')
        print(f'{key}: pinned source ready.', flush=True)


if __name__ == '__main__':
    main()
