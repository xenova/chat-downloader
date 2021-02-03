from chat_downloader.sites.twitch import TwitchChatDownloader
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


cmd1_template = 'python -m chat_downloader {} --timeout 180'
# cmd2_template = 'python -m chat_downloader --max_messages {} {}'


_TWITCH_URL = 'https://twitch.tv/'

_TWITCH_VIDEOS_URL = _TWITCH_URL + 'videos/'
_TWITCH_CLIPS_URL = 'https://clips.twitch.tv/'

a = TwitchChatDownloader()

username = 'xqcow'
clips = a.get_user_clips(username, 200, 'LAST_DAY')  # ALL_TIME

# print(clips)
# print('got',len(clips),'clips')
print('Clips:')
for clip in clips:
    print(cmd1_template.format(clip['node']['url']))

print()
# exit()

vods = a.get_user_vods(username)

for shelf_info in vods:
    node = shelf_info['node']
    print(node['title'] + ':')
    for item in node['items']:
        slug = item.get('slug')
        vod_id = item.get('id')

        if slug:
            url = _TWITCH_CLIPS_URL + slug
        else:
            url = _TWITCH_VIDEOS_URL + vod_id
        print(cmd1_template.format(url))
    print()


print('Top livestreams:')
streams = a.get_top_livestreams(100)

for stream in streams:
    node = stream['node']

    viewer_count = node['viewersCount']

    print(cmd1_template.format(_TWITCH_URL + node['broadcaster']['login']))
