# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os

def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'blivedm', '__init__.py')
    with open(version_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip("'").strip('"')
    return '1.2.0'

with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()

setup(
    name='blivedm',
    version=get_version(),
    description='Python获取bilibili直播弹幕的库，使用WebSocket协议',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='xfgryujk',
    author_email='xfgryujk@126.com',
    license='MIT',
    keywords=['bilibili', 'bilibili-live', 'danmaku'],
    packages=find_packages(),
    install_requires=[
        'aiohttp~=3.9.0',
        'Brotli~=1.1.0',
        'pure-protobuf~=3.1.2',
        'yarl~=1.9.3',
    ],
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
    ],
)
