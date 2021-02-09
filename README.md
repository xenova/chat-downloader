# Chat Downloader
A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!

[![Python](https://img.shields.io/pypi/pyversions/chat-downloader)](https://pypi.org/project/chat-downloader)
[![PyPI version](https://img.shields.io/pypi/v/chat-downloader.svg)](https://pypi.org/project/chat-downloader)
[![Downloads](https://pepy.tech/badge/chat-downloader)](https://pypi.org/project/chat-downloader)
[![GitHub license](https://img.shields.io/github/license/xenova/chat-downloader)](https://github.com/xenova/chat-downloader/blob/master/LICENSE)


<!-- [![PyPI Downloads](https://img.shields.io/pypi/dm/chat-downloader)](https://pypi.org/project/chat-downloader) -->
<!---
[![GitHub issues](https://img.shields.io/github/issues/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
[![GitHub forks](https://img.shields.io/github/forks/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
[![GitHub stars](https://img.shields.io/github/stars/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
[![Downloads](https://img.shields.io/github/downloads/xenova/chat-downloader/total.svg)](https://github.com/xenova/chat-downloader/releases)
-->

## Installation
### Install using `pip`
```
pip install chat-downloader
```

To update to the latest version, add the `--upgrade` flag to the above command.
### Install using `git`
```
git clone https://github.com/xenova/chat-downloader.git
cd chat-downloader
python setup.py install
```

## Usage
Chat items are parsed into JSON objects (a.k.a. dictionaries). For a comprehensive, documented list of included fields, consult the [Chat Item Wiki](https://github.com/xenova/chat-downloader/wiki/Item-Template).

### Command line:
```
chat_downloader https://www.youtube.com/watch?v=5qap5aO4i9A
```

For advanced command line use-cases and examples, consult the [Command Line Wiki](https://github.com/xenova/chat-downloader/wiki/Command-Line-Usage).


### Python:
```python
from chat_downloader import ChatDownloader

url = 'https://www.youtube.com/watch?v=5qap5aO4i9A'
chat = ChatDownloader().get_chat(url)       # create a generator
for message in chat:                        # iterate over messages
    print(chat.format(message))             # print the formatted message
```
For advanced python use-cases and examples, consult the [Python Wiki](https://github.com/xenova/chat-downloader/wiki/Python-Documentation).

## Issues
Found a bug or have a suggestion? File an issue [here](https://github.com/xenova/chat-downloader/issues/new/choose). To assist the developers in fixing the issue, please follow the issue template as closely as possible.

## Contributing
If you want to contribute to chat-downloader, be sure to follow the [contribution guidelines](https://github.com/xenova/chat-downloader/blob/master/CONTRIBUTING.md).


## Supported sites:
- YouTube.com - Livestreams, past broadcasts and premieres.
- Twitch.tv - Livestreams, past broadcasts and clips.
- Facebook.com (currently in development) - Livestreams and past broadcasts.

## TODO list:
- Finalise unit testing
- Improve documentation
- Add progress bar when duration is known
- Add support for streams by username (i.e. currently live)
- Websites to add:
    - facebook.com (in progress)
    - vimeo.com
    - dlive.tv
    - instagib.tv
    - dailymotion.com
    - reddit live
    - younow.com
- Add `--statistics` tag. This will show a summary of all chat messages retrieved (e.g. sum YouTube superchat, memberships, subscriptions, etc.)
