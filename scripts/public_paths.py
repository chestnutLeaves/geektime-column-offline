"""定义可以对外访问的网站文件；项目资料和运行缓存不属于网站内容。"""
import os
from pathlib import Path

PUBLIC_FILES = frozenset({'index.html', 'about.html', 'course-sources.html'})
PUBLIC_DIRECTORIES = frozenset({'courses', 'articles', 'geektime', 'relationships', 'downloads', 'assets', 'static'})


def is_public_path(root, target):
    """按解析后的真实路径检查边界，拒绝隐藏文件、维护资料及指向项目外的链接。"""
    root = Path(root).resolve()
    try:
        parts = Path(target).resolve().relative_to(root).parts
    except (ValueError, OSError):
        return False
    if not parts:
        return True
    if any(part.startswith('.') or ':' in part for part in parts):
        return False
    return parts[0] in PUBLIC_DIRECTORIES or (len(parts) == 1 and parts[0] in PUBLIC_FILES)


def iter_public_files(root):
    """供检查和发布工具共用白名单，不扫描模板、历史报告、缓存或 Git 内部文件。"""
    root = Path(root).resolve()
    for name in sorted(PUBLIC_FILES):
        path = root / name
        if path.is_file() and is_public_path(root, path):
            yield path
    for name in sorted(PUBLIC_DIRECTORIES):
        folder = root / name
        if not folder.is_dir() or not is_public_path(root, folder):
            continue
        for current, directories, files in os.walk(folder, followlinks=False):
            directories[:] = [item for item in directories if not item.startswith('.') and not Path(current, item).is_symlink()]
            for item in sorted(files):
                path = Path(current, item)
                if is_public_path(root, path) and path.is_file():
                    yield path
