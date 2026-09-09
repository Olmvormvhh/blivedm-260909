# -*- coding: utf-8 -*-
"""setuptools 兼容入口。项目元数据以 pyproject.toml 为准，此处只提供动态 version。"""
from setuptools import setup
import os


def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'blivedm', '__init__.py')
    with open(version_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip("'").strip('"')
    return '2.0.0'


setup(
    version=get_version(),
)
