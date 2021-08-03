import os
import sys

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa

# from chat_downloader import ChatDownloader
from chat_downloader.sites import get_all_sites

for site in get_all_sites():
    message_groups = getattr(site, '_MESSAGE_GROUPS', {})

    print(site._NAME, '\n', len(site._NAME)*'-', sep='')
    for group, item in message_groups.items():
        print(f'- {group}')
        for i in item:
            print(f'  - {i}')
    print()
