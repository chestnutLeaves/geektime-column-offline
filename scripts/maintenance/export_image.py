"""流式导出 Docker 镜像，直接压缩以避免占用双份磁盘空间。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import gzip
import hashlib
import shutil
import subprocess
from pathlib import Path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='lianglianglee-library:local')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary = output.with_suffix(output.suffix+'.partial')
    process = subprocess.Popen(['docker','image','save',args.image],stdout=subprocess.PIPE)
    with gzip.open(temporary,'wb',compresslevel=1) as archive:
        shutil.copyfileobj(process.stdout,archive,1024*1024)
    if process.wait() != 0:
        raise SystemExit('Docker 导出失败，保留 partial 文件供排查。')
    temporary.replace(output)
    with output.open('rb') as stream:
        checksum = hashlib.file_digest(stream,'sha256').hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(checksum+'  '+output.name+'\n',encoding='ascii')
    print(str(output),output.stat().st_size,checksum,flush=True)
