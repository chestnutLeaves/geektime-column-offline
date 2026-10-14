"""检查、导出和导入独立图片/PDF 资源包；无需联网或第三方依赖。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile


def load_resources(project):
    """只接受清单中的资源路径，拒绝绝对路径、目录穿越和 Windows 替代数据流。"""
    project = Path(project).resolve()
    result = {}
    for line in (project / 'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        name = row['target']
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] not in {'assets', 'downloads'} or len(parts) < 2
                or any(part in {'.', '..'} or part.startswith('.') for part in parts)
                or '\\' in name or ':' in name or '\x00' in name
                or PurePosixPath(name).as_posix() != name):
            raise ValueError('资源清单包含不允许的路径：' + name)
        target = (project / name).resolve()
        if (not target.is_relative_to(project) or target == project
                or target.relative_to(project).as_posix() != name):
            raise ValueError('资源目标越过项目边界：' + name)
        if name in result:
            raise ValueError('资源清单存在重复路径：' + name)
        result[name] = row
    return result


def copy_verified(source, destination, row):
    """流式复制并核对大小及 SHA-256，避免将损坏资源写入最终位置。"""
    checksum = hashlib.sha256()
    size = 0
    while chunk := source.read(1024 * 1024):
        size += len(chunk)
        if size > row['size']:
            raise ValueError('资源超过清单大小：' + row['target'])
        checksum.update(chunk)
        if destination is not None:
            destination.write(chunk)
    if size != row['size'] or checksum.hexdigest() != row['sha256']:
        raise ValueError('资源校验不一致：' + row['target'])


def check_resources(project):
    """完整检查资源包是否已安装且字节与项目清单一致。"""
    rows = load_resources(project)
    for number, (name, row) in enumerate(rows.items(), 1):
        with (Path(project) / name).open('rb') as source:
            copy_verified(source, None, row)
        if number % 5000 == 0:
            print(f'Checked {number}/{len(rows)}', flush=True)
    return len(rows)


def export_resources(project, archive_path):
    """按清单导出资源；ZIP64 支持大于 4 GiB 的资源包，不重复压缩图片。"""
    rows = load_resources(project)
    archive_path = Path(archive_path).resolve()
    temporary = archive_path.with_suffix(archive_path.suffix + '.partial')
    if archive_path.exists() or temporary.exists():
        raise FileExistsError('输出文件已存在，请使用新的文件名。')
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for name, row in rows.items():
            with (Path(project) / name).open('rb') as source, archive.open(name, 'w', force_zip64=True) as destination:
                copy_verified(source, destination, row)
    temporary.replace(archive_path)
    return len(rows)


def import_resources(project, archive_path):
    """先核对资源包全部内容，再覆盖资源；拒绝包内多余文件，不调用 extractall。"""
    project = Path(project).resolve()
    rows = load_resources(project)
    cache = project / '.cache'
    if cache.resolve() != cache:
        raise ValueError('临时目录不可通过链接跳转到其他位置。')
    cache.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        items = archive.infolist()
        if len(items) != len(rows) or {item.filename for item in items} != set(rows):
            raise ValueError('资源包文件清单不匹配，未导入任何文件。')
        if any(item.is_dir() or item.file_size != rows[item.filename]['size'] for item in items):
            raise ValueError('资源包类型或大小与清单不匹配。')
        # 临时目录位于项目内部，整包通过验证后才安装，失败时清理临时文件。
        with tempfile.TemporaryDirectory(prefix='resource-import-', dir=cache) as temporary:
            for item in items:
                target = Path(temporary) / item.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open('wb') as destination:
                    copy_verified(source, destination, rows[item.filename])
            for name in rows:
                destination = (project / name).resolve()
                if not destination.is_relative_to(project) or destination.relative_to(project).as_posix() != name:
                    raise ValueError('安装目标越过项目边界。')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(Path(temporary) / name), str(destination))
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'export', 'import'])
    parser.add_argument('archive', nargs='?', type=Path)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.action != 'check' and args.archive is None:
        parser.error('导入或导出时需要指定资源包路径。')
    project = args.project.resolve()
    if args.action == 'check':
        count = check_resources(project)
    elif args.action == 'export':
        count = export_resources(project, args.archive)
    else:
        count = import_resources(project, args.archive)
    print(f'{args.action}: {count} resource files verified.', flush=True)


if __name__ == '__main__':
    main()
