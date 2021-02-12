
## Installation
### Install using `pip`
```

```


### Install using `git`
```

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
