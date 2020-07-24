from setuptools import setup

setup(
	name='chat_replay_downloader',
	version='1.0',
	description='Retrieve YouTube/Twitch chat for past broadcasts/VODs',
	author='Joshua Lochner',
	author_email='admin@xenova.com',
	packages=['chat_replay_downloader'],
	install_requires=['requests', 'json', 'datetime', 're', 'argparse', 'bs4']
)