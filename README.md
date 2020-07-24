# Chat Replay Downloader
## Retrieve YouTube/Twitch chat for past broadcasts/VODs.

### Requirements:
Please run `pip install -r requirements.txt` to ensure you have all the necessary dependencies.

### Command line:
#### Usage
```
usage: ChatReplayDownloader.py [-h] [-start_time START_TIME]
                               [-end_time END_TIME] [-output OUTPUT]
                               url

Retrieve YouTube/Twitch chat for past broadcasts/VODs.

positional arguments:
  url                   YouTube/Twitch video URL

optional arguments:
  -h, --help            show this help message and exit
  -start_time START_TIME, -from START_TIME
                        start time in seconds (default: 0)
  -end_time END_TIME, -to END_TIME
                        end time in seconds (default: None = until the end)
  -output OUTPUT, -o OUTPUT
                        output file (default: None = print to standard output)
```

#### Examples
##### 1. Output file of all chat messages, given a url
```
python chat_replay_downloader.py <video_url> -output <file_name>
```
If the file name ends in `.json`, the array will be written to the file in JSON format. Otherwise, the chat messages will be outputted to the file in the following format:\
`[<time>] <author>: <message>`

##### 2. Output file of chat messages, starting at a certain time (in seconds) until the end
```
python chat_replay_downloader.py <video_url> -start_time <time_in_seconds> -output <file_name>
```

##### 3. Output file of chat messages, starting from the beginning and ending at a certain time (in seconds)
```
python chat_replay_downloader.py <video_url> -end_time <time_in_seconds> -output <file_name>
```

##### 4. Output file of chat messages, starting and ending at certain times (in seconds)
```
python chat_replay_downloader.py <video_url> -start_time <time_in_seconds> -end_time <time_in_seconds> -output <file_name>
```

### Python module

#### Importing the module

```python
import chat_replay_downloader
```
or

```python
from chat_replay_downloader import get_chat_replay, get_youtube_messages, get_twitch_messages
```
The following examples will use the second form of importing.

#### Examples
##### 1. Return list of all chat messages, given a video url:
```python
youtube_messages = get_chat_replay('https://www.youtube.com/watch?v=xxxxxxxxxxx')
twitch_messages = get_chat_replay('https://www.twitch.tv/videos/xxxxxxxxx')
```

##### 2. Return list of all chat messages, given a video id
```python
youtube_messages = get_youtube_messages('xxxxxxxxxxx')
twitch_messages = get_twitch_messages('xxxxxxxxx')
```
<br/>

The following examples use parameters which all three methods (`get_chat_replay`, `get_youtube_messages`, `get_twitch_messages`) have. Both of the following parameters are optional:
* `start_time`: start time in seconds (Default is 0, which is the start of the video)
* `end_time`: end time in seconds (Default is None, which means it will continue until the video ends)

##### 3. Return list of chat messages, starting at a certain time (in seconds)
```python
messages = get_chat_replay('video_url', start_time = 60) # Start at 60 seconds and continue until the end
```

##### 4. Return list of chat messages, ending at a certain time (in seconds)
```python
messages = get_chat_replay('video_url', end_time = 60) # Start at 0 seconds (beginning) and end at 60 seconds
```

##### 5. Return list of chat messages, starting and ending at certain times (in seconds)
```python
messages = get_chat_replay('video_url', start_time = 60, end_time = 120) # Start at 60 seconds and end at 120 seconds
```
