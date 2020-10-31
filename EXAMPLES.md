## Examples
This file was automatically generated using `python run_tests.py`
### 1. [YouTube] Get live chat replay
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100)
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100
```

[TXT output](<examples/[YouTube] Get live chat replay.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -output "examples/[YouTube] Get live chat replay.txt"
```

[CSV output](<examples/[YouTube] Get live chat replay.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -output "examples/[YouTube] Get live chat replay.csv"
```

[JSON output](<examples/[YouTube] Get live chat replay.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -output "examples/[YouTube] Get live chat replay.json"
```

### 2. [YouTube] Get live chat replay with start and end time
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=JIB3JbIIbPU', start_time=300, end_time=400)
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=JIB3JbIIbPU" -start_time 300 -end_time 400
```

[TXT output](<examples/[YouTube] Get live chat replay with start and end time.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=JIB3JbIIbPU" -start_time 300 -end_time 400 -output "examples/[YouTube] Get live chat replay with start and end time.txt"
```

[CSV output](<examples/[YouTube] Get live chat replay with start and end time.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=JIB3JbIIbPU" -start_time 300 -end_time 400 -output "examples/[YouTube] Get live chat replay with start and end time.csv"
```

[JSON output](<examples/[YouTube] Get live chat replay with start and end time.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=JIB3JbIIbPU" -start_time 300 -end_time 400 -output "examples/[YouTube] Get live chat replay with start and end time.json"
```

### 3. [YouTube] Get superchat messages from live chat replay
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=97w16cYskVI', end_time=100, message_type='superchat')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=97w16cYskVI" -end_time 100 -message_type superchat
```

[TXT output](<examples/[YouTube] Get superchat messages from live chat replay.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=97w16cYskVI" -end_time 100 -message_type superchat -output "examples/[YouTube] Get superchat messages from live chat replay.txt"
```

[CSV output](<examples/[YouTube] Get superchat messages from live chat replay.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=97w16cYskVI" -end_time 100 -message_type superchat -output "examples/[YouTube] Get superchat messages from live chat replay.csv"
```

[JSON output](<examples/[YouTube] Get superchat messages from live chat replay.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=97w16cYskVI" -end_time 100 -message_type superchat -output "examples/[YouTube] Get superchat messages from live chat replay.json"
```

### 4. [YouTube] Get messages from live chat replay
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=wXspodtIxYU', start_time=100, end_time=200, message_type='all')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -start_time 100 -end_time 200 -message_type all
```

[TXT output](<examples/[YouTube] Get messages from live chat replay.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -start_time 100 -end_time 200 -message_type all -output "examples/[YouTube] Get messages from live chat replay.txt"
```

[CSV output](<examples/[YouTube] Get messages from live chat replay.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -start_time 100 -end_time 200 -message_type all -output "examples/[YouTube] Get messages from live chat replay.csv"
```

[JSON output](<examples/[YouTube] Get messages from live chat replay.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -start_time 100 -end_time 200 -message_type all -output "examples/[YouTube] Get messages from live chat replay.json"
```

### 5. [YouTube] Get all types of messages from top chat replay
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100, chat_type='top')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -chat_type top
```

[TXT output](<examples/[YouTube] Get all types of messages from top chat replay.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -chat_type top -output "examples/[YouTube] Get all types of messages from top chat replay.txt"
```

[CSV output](<examples/[YouTube] Get all types of messages from top chat replay.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -chat_type top -output "examples/[YouTube] Get all types of messages from top chat replay.csv"
```

[JSON output](<examples/[YouTube] Get all types of messages from top chat replay.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=wXspodtIxYU" -end_time 100 -chat_type top -output "examples/[YouTube] Get all types of messages from top chat replay.json"
```

### 6. [YouTube] Get messages from premiered video
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=zVCs9Cug_qM')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=zVCs9Cug_qM" 
```

[TXT output](<examples/[YouTube] Get messages from premiered video.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=zVCs9Cug_qM"  -output "examples/[YouTube] Get messages from premiered video.txt"
```

[CSV output](<examples/[YouTube] Get messages from premiered video.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=zVCs9Cug_qM"  -output "examples/[YouTube] Get messages from premiered video.csv"
```

[JSON output](<examples/[YouTube] Get messages from premiered video.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=zVCs9Cug_qM"  -output "examples/[YouTube] Get messages from premiered video.json"
```

### 7. [YouTube] Ending has strange times
#### Python:
```python
get_chat_replay('https://www.youtube.com/watch?v=DzEbfQI4TPQ', start_time='3:30:46')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=DzEbfQI4TPQ" -start_time 3:30:46
```

[TXT output](<examples/[YouTube] Ending has strange times.txt>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=DzEbfQI4TPQ" -start_time 3:30:46 -output "examples/[YouTube] Ending has strange times.txt"
```

[CSV output](<examples/[YouTube] Ending has strange times.csv>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=DzEbfQI4TPQ" -start_time 3:30:46 -output "examples/[YouTube] Ending has strange times.csv"
```

[JSON output](<examples/[YouTube] Ending has strange times.json>)
```
python chat_replay_downloader.py "https://www.youtube.com/watch?v=DzEbfQI4TPQ" -start_time 3:30:46 -output "examples/[YouTube] Ending has strange times.json"
```

### 8. [Twitch] Get live chat replay
#### Python:
```python
get_chat_replay('https://www.twitch.tv/videos/449716115')
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115" 
```

[TXT output](<examples/[Twitch] Get live chat replay.txt>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115"  -output "examples/[Twitch] Get live chat replay.txt"
```

[CSV output](<examples/[Twitch] Get live chat replay.csv>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115"  -output "examples/[Twitch] Get live chat replay.csv"
```

[JSON output](<examples/[Twitch] Get live chat replay.json>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115"  -output "examples/[Twitch] Get live chat replay.json"
```

### 9. [Twitch] Get live chat replay with start and end time
#### Python:
```python
get_chat_replay('https://www.twitch.tv/videos/449716115', start_time=100, end_time=200)
```

#### Command line:
Print to standard output:
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115" -start_time 100 -end_time 200
```

[TXT output](<examples/[Twitch] Get live chat replay with start and end time.txt>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115" -start_time 100 -end_time 200 -output "examples/[Twitch] Get live chat replay with start and end time.txt"
```

[CSV output](<examples/[Twitch] Get live chat replay with start and end time.csv>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115" -start_time 100 -end_time 200 -output "examples/[Twitch] Get live chat replay with start and end time.csv"
```

[JSON output](<examples/[Twitch] Get live chat replay with start and end time.json>)
```
python chat_replay_downloader.py "https://www.twitch.tv/videos/449716115" -start_time 100 -end_time 200 -output "examples/[Twitch] Get live chat replay with start and end time.json"
```

