#!/usr/bin/env python3
"""
FoxCode 代码统计脚本

统计 FoxCode 项目的代码行数，包括：
- 按文件类型统计
- 按目录统计
- 总体统计

使用方法:
    python count_lines.py
"""

from pathlib import Path
from collections import defaultdict


def count_lines(directory: Path, extensions: list[str] | None = None) -> dict:
    """
    统计指定目录下特定扩展名文件的行数
    
    Args:
        directory: 目标目录
        extensions: 文件扩展名列表，默认为常见代码文件
        
    Returns:
        统计结果字典
    """
    if extensions is None:
        extensions = [
            '.py', '.js', '.vue', '.ts', '.tsx', '.jsx',
            '.css', '.scss', '.html', '.json', '.md',
            '.toml', '.yaml', '.yml', '.sh', '.bat',
        ]
    
    stats = {
        'total_lines': 0,
        'total_files': 0,
        'by_extension': defaultdict(lambda: {'lines': 0, 'files': 0}),
        'by_directory': defaultdict(lambda: {'lines': 0, 'files': 0}),
        'largest_files': [],
    }
    
    # 排除的目录
    exclude_dirs = {
        '__pycache__', 'node_modules', '.git', '.venv', 'venv',
        'dist', 'build', '.idea', '.vscode', '.foxcode',
        '新建文件夹', '.mypy_cache', '.pytest_cache',
    }
    
    # 收集所有文件
    all_files = []
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix in extensions:
            # 检查是否在排除目录中
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            all_files.append(file_path)
    
    # 统计每个文件
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = len(f.readlines())
            
            ext = file_path.suffix
            rel_path = file_path.relative_to(directory)
            parent = str(rel_path.parent)
            
            # 更新总计数
            stats['total_lines'] += lines
            stats['total_files'] += 1
            
            # 按扩展名统计
            stats['by_extension'][ext]['lines'] += lines
            stats['by_extension'][ext]['files'] += 1
            
            # 按目录统计
            stats['by_directory'][parent]['lines'] += lines
            stats['by_directory'][parent]['files'] += 1
            
            # 记录大文件
            stats['largest_files'].append({
                'path': str(rel_path),
                'lines': lines,
                'ext': ext,
            })
            
        except Exception as e:
            print(f"无法读取文件 {file_path}: {e}")
    
    return stats


def print_stats(stats: dict, title: str = "FoxCode 代码统计结果") -> None:
    """打印统计结果"""
    total_lines = stats['total_lines']
    
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()
    
    # 总体统计
    print("【总体统计】")
    print(f"  总文件数: {stats['total_files']}")
    print(f"  总行数:   {total_lines:,}")
    print()
    
    # 按扩展名统计
    print("【按文件类型统计】")
    print("-" * 70)
    print(f"  {'扩展名':<12} {'文件数':>8} {'行数':>12} {'占比':>8}")
    print("-" * 70)
    
    sorted_ext = sorted(
        stats['by_extension'].items(),
        key=lambda x: x[1]['lines'],
        reverse=True
    )
    
    for ext, data in sorted_ext:
        percentage = (data['lines'] / total_lines * 100) if total_lines > 0 else 0
        print(f"  {ext:<12} {data['files']:>8} {data['lines']:>12,} {percentage:>7.1f}%")
    
    print()
    
    # 按目录统计 (显示前15个)
    print("【按目录统计 (Top 15)】")
    print("-" * 70)
    print(f"  {'目录':<40} {'文件数':>8} {'行数':>12}")
    print("-" * 70)
    
    sorted_dirs = sorted(
        stats['by_directory'].items(),
        key=lambda x: x[1]['lines'],
        reverse=True
    )[:15]
    
    for dir_path, data in sorted_dirs:
        display_path = dir_path if len(dir_path) <= 38 else "..." + dir_path[-35:]
        print(f"  {display_path:<40} {data['files']:>8} {data['lines']:>12,}")
    
    print()
    
    # 最大的文件 (Top 10)
    print("【最大文件 (Top 10)】")
    print("-" * 70)
    print(f"  {'文件':<50} {'行数':>10}")
    print("-" * 70)
    
    sorted_files = sorted(
        stats['largest_files'],
        key=lambda x: x['lines'],
        reverse=True
    )[:10]
    
    for file_info in sorted_files:
        display_path = file_info['path']
        if len(display_path) > 48:
            display_path = "..." + display_path[-45:]
        print(f"  {display_path:<50} {file_info['lines']:>10,}")
    
    print()
    print("=" * 70)


def main():
    """主函数"""
    # FoxCode 源代码目录
    foxcode_dir = Path(__file__).parent / "src" / "foxcode"
    
    if not foxcode_dir.exists():
        print(f"错误: 找不到 FoxCode 目录: {foxcode_dir}")
        return 1
    
    print(f"正在统计: {foxcode_dir}")
    print()
    
    stats = count_lines(foxcode_dir)
    print_stats(stats)
    
    return 0


if __name__ == "__main__":
    exit(main())
