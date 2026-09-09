# -*- coding: utf-8 -*-
"""
构建 blivedm wheel 包的脚本
"""
import os
import sys
import subprocess
import shutil

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_command(cmd):
    """运行命令"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print("Error:", str(e))
        return False

def main():
    print("Building blivedm wheel package...")
    print(f"Project directory: {PROJECT_DIR}")
    
    # 清理旧的构建
    for dir_name in ['build', 'dist', 'blivedm.egg-info']:
        dir_path = os.path.join(PROJECT_DIR, dir_name)
        if os.path.exists(dir_path):
            print(f"Removing {dir_name}...")
            shutil.rmtree(dir_path, ignore_errors=True)
    
    # 尝试使用 setuptools 构建
    print("\nAttempting to build using setup.py...")
    if os.path.exists(os.path.join(PROJECT_DIR, 'setup.py')):
        if run_command('python setup.py bdist_wheel'):
            print("\nBuild succeeded!")
            # 检查生成的文件
            dist_dir = os.path.join(PROJECT_DIR, 'dist')
            if os.path.exists(dist_dir):
                files = os.listdir(dist_dir)
                print(f"\nGenerated files in dist/:")
                for f in files:
                    file_path = os.path.join(dist_dir, f)
                    size = os.path.getsize(file_path)
                    print(f"  - {f} ({size} bytes)")
            return
    
    print("\nBuild failed or no setup.py found.")

if __name__ == "__main__":
    main()
