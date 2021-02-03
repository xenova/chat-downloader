# Chat Downloader
A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!

[![Python](https://img.shields.io/pypi/pyversions/chat-downloader)](https://pypi.org/project/chat-downloader)
[![PyPI version](https://img.shields.io/pypi/v/chat-downloader.svg)](https://pypi.org/project/chat-downloader)
[![PyPI Downloads](https://img.shields.io/pypi/dm/chat-downloader)](https://pypi.org/project/chat-downloader)
[![GitHub license](https://img.shields.io/github/license/xenova/chat-downloader)](https://github.com/xenova/chat-downloader/blob/master/LICENSE)



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
Found a bug or have a suggestion? File an issue [here](https://github.com/xenova/chat-downloader/issues/new). To assist the developers in fixing the issue, please follow the issue template (automatically generated when creating a new issue).

## Contributing
### Become a contributor
#### Run as a developer
To run the program as a developer, you do not need to build anything separately. Simply execute:
```
python -m chat_downloader
```
[work in progress]

#### Add support for a new site:
1. [Fork](https://github.com/xenova/chat-downloader/fork) this repository.
2. Clone the source code with:

        git clone git@github.com:YOUR_GITHUB_USERNAME/chat-downloader.git
3. Start a new branch with:

        cd youtube-dl
        git checkout -b site
4. *Rest of guide in progress...*

### Test the program
If you are unable to write code but still wish to assist, we encourage users to run commands with the `--testing` flag included. This will print debugging messages and pause once something unexpected happens (e.g. when an unknown item is being parsed). If something happens, please raise an issue and we will fix it or add support for it as soon as possible!
Note that this will not affect any output you write to files (using `--output`).
 For example:

```
chat_downloader https://www.youtube.com/watch?v=5qap5aO4i9A --testing
```

Some extractors use undocumented endpoints and may and as a result, users may encounter items which will not be parsed correctly. Increased testing will improve functionality of the software for other users and is greatly appreciated.


## Chat Items
Chat items are parsed into JSON objects (a.k.a. dictionaries) and follow this template:

[work in progress]

For a more in-depth output template, consult the [Item Wiki](https://github.com/xenova/chat-downloader/wiki/Item-Template).

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
