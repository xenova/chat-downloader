from chat_downloader.utils import multi_get
import sys
import json
import requests
import re
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


live_url = _YT_HOME + '/channel/UC4R8DWoMoI7CAwX8_LjQHig'


# print(ytInitialData)

ytInitialData = get_initial_info(live_url)

sections = ytInitialData['contents']['twoColumnBrowseResultsRenderer'][
    'tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents']

cmd_template = 'python -m chat_downloader https://www.youtube.com/watch?v={} --timeout 180'
# --max_messages 100
for s in sections:
    section_info = s['itemSectionRenderer']['contents'][0]['shelfRenderer']

    # print(section_info)

    section_title = section_info['title']['runs'][0]['text']

    # items = section_info['content']['horizontalListRenderer']['items']

    playlist_url = _YT_HOME + \
        section_info['endpoint']['commandMetadata']['webCommandMetadata']['url']
    # print(playlist_url)
    # playlist_url = 'https://www.youtube.com/playlist?list=PLErukX1W1OYjFx2pG8zjWiMuPMG0F-LbI'
    # playlist_url = 'https://www.youtube.com/playlist?list=PLiZwe6-ujEU0vx0RU8QUw5EoRTNA3zV9M'
    print(section_title)

    playlist_info = get_initial_info(playlist_url)
    # print(playlist_info)

    items = playlist_info['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content'][
        'sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['playlistVideoListRenderer']['contents']

    for item in items:
        video_id = multi_get(item, 'playlistVideoRenderer', 'videoId')
        if video_id:
            print(cmd_template.format(video_id))

            # "continuationItemRenderer":{
            #     "trigger":"CONTINUATION_TRIGGER_ON_ITEM_SHOWN",
            #     "continuationEndpoint":{
            #         "clickTrackingParams":"CCgQ7zsYACITCNT0zMKim-4CFU-V1QodgR4KyA==",
            #         "commandMetadata":{
            #             "webCommandMetadata":{
            #             "sendPost":true,
            #             "apiUrl":"/youtubei/v1/browse"
            #             }
            #         },
            #         "continuationCommand":{
            #             "token":"4qmFsgJhEiRWTFBMRXJ1a1gxVzFPWWpGeDJwRzh6aldpTXVQTUcwRi1MYkkaFENBRjZCbEJVT2tOSFVRJTNEJTNEmgIiUExFcnVrWDFXMU9ZakZ4MnBHOHpqV2lNdVBNRzBGLUxiSQ%3D%3D",
            #             "request":"CONTINUATION_REQUEST_TYPE_BROWSE"
            #         }
            #     }
            # }
    # exit()
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
