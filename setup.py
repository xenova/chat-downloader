#!/usr/bin/env python

"""The setup script."""
from setuptools import setup, find_packages


# Get metadata without importing the package
with open('chat_downloader/metadata.py') as metadata_file:
    exec(metadata_file.read())
    metadata = locals()

with open('README.rst') as readme_file:
    readme = readme_file.read()

# with open('HISTORY.rst') as history_file:
#     history = history_file.read()

requirements = [
    'requests',
    'datetime',
    'isodate',
    'regex',
    'argparse',
    'docstring-parser',
    'colorlog',
    'websocket-client'
]

setup(
    author=metadata['__author__'],
    author_email=metadata['__email__'],
    url=metadata['__url__'],
    version=metadata['__version__'],
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Operating System :: OS Independent',
    ],
    description=metadata['__summary__'],
    entry_points={
        'console_scripts': [
            'chat_downloader=chat_downloader.cli:main',
        ],
    },
    install_requires=requirements,
    extras_require={
        'dev': [
            'flake8',
            'twine',
            'wheel',
            'tox',
            'pytest',
            'pytest-xdist',
            'sphinx',
            'sphinx-rtd-theme',
            'sphinxcontrib-programoutput'
        ]
    },
    license='MIT license',
    long_description=readme,  # + '\n\n' + history,
    long_description_content_type='text/x-rst',
    include_package_data=True,
    keywords='python chat downloader youtube twitch',
    name='chat-downloader',
    packages=find_packages(include=['chat_downloader', 'chat_downloader.*']),
    package_data={
        'chat_downloader': ['formatting/*.json']
    },
    test_suite='tests',
    zip_safe=False,
)
