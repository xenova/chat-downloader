# Chat Downloader
A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!


### Requirements:
* Python 3.
* Run `pip install chat_replay_downloader` to install the package.


### Command line:
#### Usage
```
usage: chat_replay_downloader [-h] [--start_time START_TIME]
                              [--end_time END_TIME]
                              [--message_types MESSAGE_TYPES | --message_groups MESSAGE_GROUPS]
                              [--max_attempts MAX_ATTEMPTS]
                              [--retry_timeout RETRY_TIMEOUT]
                              [--max_messages MAX_MESSAGES]
                              [--inactivity_timeout INACTIVITY_TIMEOUT]
                              [--timeout TIMEOUT] [--format FORMAT]
                              [--format_file FORMAT_FILE]
                              [--chat_type {live,top}]
                              [--message_receive_timeout MESSAGE_RECEIVE_TIMEOUT]
                              [--buffer_size BUFFER_SIZE] [--output OUTPUT]
                              [--sort_keys] [--indent INDENT] [--overwrite]
                              [--pause_on_debug PAUSE_ON_DEBUG]
                              [--logging {none,debug,info,warning,error,critical} | --testing | --verbose]
                              [--cookies COOKIES]
                              url

A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!

Mandatory Arguments:
  url                   The URL of the livestream, video, clip or past broadcast

General Arguments:
  -h, --help            show this help message and exit

Timing Arguments:
  --start_time START_TIME, -s START_TIME
                        Start time in seconds or hh:mm:ss, default is None (as early as possible)
  --end_time END_TIME, -e END_TIME
                        End time in seconds or hh:mm:ss, default is None (until the end)

Message Type Arguments:
  --message_types MESSAGE_TYPES
                        List of messages types to include
  --message_groups MESSAGE_GROUPS
                        List of messages groups (a predefined, site-specific collection of message types) to include

Retry Arguments:
  --max_attempts MAX_ATTEMPTS
                        Maximum number of attempts to retrieve chat messages
  --retry_timeout RETRY_TIMEOUT
                        Number of seconds to wait before retrying. Setting this to a negative number will wait for user input.
                        Default is None (use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)

Termination Arguments:
  --max_messages MAX_MESSAGES
                        Maximum number of messages to retrieve, default is None (unlimited)
  --inactivity_timeout INACTIVITY_TIMEOUT
                        Stop getting messages after not receiving anything for a certain duration (in seconds)
  --timeout TIMEOUT     Stop retrieving chat after a certain duration (in seconds)

Format Arguments:
  --format FORMAT       Specify how messages should be formatted for printing, default uses site default
  --format_file FORMAT_FILE
                        Specify the format file to choose formats from

[Site Specific] YouTube Arguments:
  --chat_type {live,top}
                        Specify chat type, default is live

[Site Specific] Twitch Arguments:
  --message_receive_timeout MESSAGE_RECEIVE_TIMEOUT
                        Time before requesting for new messages
  --buffer_size BUFFER_SIZE
                        Specify a buffer size for retrieving messages

Output Arguments:
  --output OUTPUT, -o OUTPUT
                        Path of the output file, default is None (i.e. print to standard output)
  --sort_keys           Sort keys when outputting to a file
  --indent INDENT       Number of spaces to indent JSON objects by. If nonnumerical input is provided, this will be used to indent the objects.
  --overwrite           Overwrite output file if it exists. Otherwise, append to the end of the file.

Debugging/Testing Arguments:
  --pause_on_debug PAUSE_ON_DEBUG
                        Pause on certain debug messages
  --logging {none,debug,info,warning,error,critical}
                        Level of logging to display
  --testing             Enable testing mode
  --verbose, -v         Print various debugging information. This is equivalent to setting logging to debug

Initialisation Arguments:
  --cookies COOKIES, -c COOKIES
                        Path of cookies file

```
#### TODO
* Set up unit testing
* Improve documentation


#### Examples
(Coming soon)
