import sys
import codecs
import json
import requests
import re




sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

session = requests.Session()
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
    'Accept-Language': 'en-US, en'
}

_YT_HOME = 'https://www.youtube.com'
_YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;'


def get_initial_info(url):
    html = session.get(url).text
    info = re.search(_YT_INITIAL_DATA_RE, html)
    return json.loads(info.group(1))




live_url = _YT_HOME+'/channel/UC4R8DWoMoI7CAwX8_LjQHig'



# print(ytInitialData)

ytInitialData = get_initial_info(live_url)

sections = ytInitialData['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents']

cmd_template = 'python -m chat_replay_downloader https://www.youtube.com/watch?v={}'
# --max_messages 100
for s in sections:
    section_info = s['itemSectionRenderer']['contents'][0]['shelfRenderer']

    # print(section_info)

    section_title = section_info['title']['runs'][0]['text']


    # items = section_info['content']['horizontalListRenderer']['items']

    playlist_url = _YT_HOME+section_info['endpoint']['commandMetadata']['webCommandMetadata']['url']
    # print(playlist_url)

    print(section_title)

    playlist_info = get_initial_info(playlist_url)

    items = playlist_info['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['playlistVideoListRenderer']['contents']

    for item in items:
        video_id = item['playlistVideoRenderer']['videoId']
        print(cmd_template.format(video_id))

    print()
    # print(playlist_info)
    # exit()
    # print(section_title)


    # for item in items:

    #     info = item['gridVideoRenderer']
    #     video_id = info['videoId']
    #     title = info['title']['simpleText']


    #     #print(cmd_template.format(video_id))
    # print()

# requests.post()

# Live Now
# Recent Live Streams
# Upcoming Live Streams
# Live Now - News
# Live Now - Gaming
# Live Now - Sports
