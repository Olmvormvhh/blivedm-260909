# -*- coding: utf-8 -*-
"""
构建 blivedm wheel 包的脚本
"""
import os
import sys
import shutil

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("Building blivedm wheel package...")
    print(f"Project directory: {PROJECT_DIR}")

    os.chdir(PROJECT_DIR)

    for dir_name in ['build', 'dist', 'blivedm.egg-info']:
        dir_path = os.path.join(PROJECT_DIR, dir_name)
        if os.path.exists(dir_path):
            print(f"Removing {dir_name}...")
            shutil.rmtree(dir_path, ignore_errors=True)

    dist_dir = os.path.join(PROJECT_DIR, 'dist')
    os.makedirs(dist_dir, exist_ok=True)

    # 使用 PEP 517 hook，避免已弃用的 `python setup.py bdist_wheel`
    print("\nBuilding wheel with setuptools.build_meta...")
    try:
        from setuptools.build_meta import build_wheel
        wheel_name = build_wheel(dist_dir)
    except Exception as e:
        print(f"\nBuild failed: {e}")
        return 1

    print("\nBuild succeeded!")
    files = os.listdir(dist_dir)
    print("\nGenerated files in dist/:")
    for f in files:
        file_path = os.path.join(dist_dir, f)
        size = os.path.getsize(file_path)
        print(f"  - {f} ({size} bytes)")
    if wheel_name:
        print(f"\nWheel: {wheel_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
