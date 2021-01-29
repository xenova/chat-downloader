#!/usr/bin/env python

"""The setup script."""

import chat_replay_downloader
from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.md') as history_file:
    history = history_file.read()

requirements = [
    'requests',
    'datetime',
    'isodate',
    'regex',
    'argparse',
    'docstring-parser',
    'colorlog'
]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest>=3', ]

setup(
    author=chat_replay_downloader.__author__,
    author_email=chat_replay_downloader.__email__,
    url=chat_replay_downloader.__url__,
    version=chat_replay_downloader.__version__,
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: OS Independent',
    ],
    description='A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!',
    entry_points={
        'console_scripts': [
            'chat_replay_downloader=chat_replay_downloader.cli:main',
        ],
    },
    install_requires=requirements,
    license='MIT license',
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    include_package_data=True,
    keywords='chat_replay_downloader',
    name='chat_replay_downloader',
    packages=find_packages(include=['chat_replay_downloader', 'chat_replay_downloader.*']),
    package_data={
        'chat_replay_downloader':['formatting/*.json']
    },
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    zip_safe=False,
)
