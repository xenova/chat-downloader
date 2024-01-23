..
    TODO
    - temp move ... move back to root
    - auto-generate using other rst files

***************
Chat Downloader
***************

.. image:: https://img.shields.io/pypi/pyversions/chat-downloader
   :target: https://pypi.org/project/chat-downloader
   :alt: Python

.. image:: https://img.shields.io/pypi/v/chat-downloader.svg
   :target: https://pypi.org/project/chat-downloader
   :alt: PyPI version

.. image:: https://pepy.tech/badge/chat-downloader/month
   :target: https://pypi.org/project/chat-downloader
   :alt: Downloads

.. image:: https://img.shields.io/github/license/xenova/chat-downloader
  :target: https://github.com/xenova/chat-downloader/blob/master/LICENSE
  :alt: License

.. image:: https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fxenova%2Fchat-downloader%2Fmaster%2Fdocs%2F_dynamic%2Fcoverage.json
  :target: https://pypi.org/project/chat-downloader
  :alt: Coverage

..
    [![GitHub issues](https://img.shields.io/github/issues/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
    [![GitHub forks](https://img.shields.io/github/forks/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
    [![GitHub stars](https://img.shields.io/github/stars/xenova/chat-downloader)](https://badge.fury.io/py/chat-downloader)
    [![Downloads](https://img.shields.io/github/downloads/xenova/chat-downloader/total.svg)](https://github.com/xenova/chat-downloader/releases)

`Chat Downloader`_ is a simple tool used to retrieve chat messages from livestreams,
videos, clips and past broadcasts. No authentication needed!

.. _Chat Downloader: https://github.com/xenova/chat-downloader

############
Installation
############

This tool is distributed on PyPI_ and can be installed with ``pip``:

.. _PyPI: https://pypi.org/project/chat-downloader/

.. code:: console

   $ pip install chat-downloader

To update to the latest version, add the ``--upgrade`` flag to the above command.

Alternatively, the tool can be installed with ``git``:

.. code:: console

   $ git clone https://github.com/xenova/chat-downloader.git
   $ cd chat-downloader
   $ python setup.py install

The tool can be used with ``docker``:

.. code:: console

   $ docker run -v /path/to/download/:/home/download/ -e channelURL='https://www.twitch.tv/twitch' -e channelName='twitch' -e fileFormat='json' -e uid='1000' -e gid='1000' ghcr.io/xenova/chat-downloader:master


#####
Usage
#####


Command line
------------

.. code:: console

    usage: chat_downloader [-h] [--version] [--start_time START_TIME]
                           [--end_time END_TIME]
                           [--message_types MESSAGE_TYPES | --message_groups MESSAGE_GROUPS]
                           [--max_attempts MAX_ATTEMPTS]
                           [--retry_timeout RETRY_TIMEOUT]
                           [--interruptible_retry [INTERRUPTIBLE_RETRY]]
                           [--max_messages MAX_MESSAGES]
                           [--inactivity_timeout INACTIVITY_TIMEOUT]
                           [--timeout TIMEOUT] [--format FORMAT]
                           [--format_file FORMAT_FILE] [--chat_type {live,top}]
                           [--ignore IGNORE]
                           [--message_receive_timeout MESSAGE_RECEIVE_TIMEOUT]
                           [--buffer_size BUFFER_SIZE] [--output OUTPUT]
                           [--overwrite [OVERWRITE]] [--sort_keys [SORT_KEYS]]
                           [--indent INDENT] [--pause_on_debug | --exit_on_debug]
                           [--logging {none,debug,info,warning,error,critical} | --testing | --verbose | --quiet]
                           [--cookies COOKIES] [--proxy PROXY]
                           url


For example, to save messages from a livestream to a JSON file, you can use:

.. code:: console

   $ chat_downloader https://www.youtube.com/watch?v=jfKfPfyJRdk --output chat.json



For a description of these options, as well as advanced command line use-cases and examples, consult the `Command Line Usage <https://chat-downloader.readthedocs.io/en/latest/cli.html#command-line-usage>`_ page.


Python
------

.. code:: python

   from chat_downloader import ChatDownloader

   url = 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
   chat = ChatDownloader().get_chat(url)       # create a generator
   for message in chat:                        # iterate over messages
       chat.print_formatted(message)           # print the formatted message


For advanced python use-cases and examples, consult the `Python Documentation <https://chat-downloader.readthedocs.io/en/latest/source/index.html#python-documentation>`_.


Docker
------
    
- **/home/download** - the place where the file will be saved. Mount it to a desired place with -v option.
- **channelURL** - the url of the stream you want to record.
- **channelName** - the name for the stream.
- **fileFormat** - file extension to be used.
- **uid** - UserID, map to your desired User ID (fallback to 9001)
- **gid** - GroupID, map to your desired Group ID (fallback to 9001)

The File will be saved as channelName-YearMonthDate-HourMinuteSecond.ext


##########
Chat Items
##########

Chat items/messages are parsed into JSON objects (a.k.a. dictionaries) and should follow a format similar to this:

.. code-block::

    {
        ...
        "message_id": "xxxxxxxxxx",
        "message": "actual message goes here",
        "message_type": "text_message",
        "timestamp": 1613761152565924,
        "time_in_seconds": 1234.56,
        "time_text": "20:34",
        "author": {
            "id": "UCxxxxxxxxxxxxxxxxxxxxxxx",
            "name": "username_of_sender",
            "images": [
                ...
            ],
            "badges": [
                ...
            ]
        },
        ...
    }


For an extensive, documented list of included fields, consult the `Chat Item Fields <https://chat-downloader.readthedocs.io/en/latest/items.html#chat-item-fields>`_ page.

##########################
Frequently Asked Questions
##########################

*Coming soon*

######
Issues
######

Found a bug or have a suggestion? File an issue `here`_. To assist the
developers in fixing the issue, please follow the issue template as
closely as possible.

.. _here: https://github.com/xenova/chat-downloader/issues/new/choose


############
Contributing
############

If you would like to help improve the tool, you'll find more
information on contributing in our `Contributing Guide <https://chat-downloader.readthedocs.io/en/latest/contributing.html#contributing-guide>`_.


################
Supported sites:
################

-  YouTube.com - Livestreams, past broadcasts and premieres.
-  Twitch.tv - Livestreams, past broadcasts and clips.
-  Zoom.us - Past broadcasts
-  Facebook.com (currently in development) - Livestreams and past
   broadcasts.

.. _Chat Item Wiki: https://github.com/xenova/chat-downloader/wiki/Item-Template
.. _Command Line Wiki: https://github.com/xenova/chat-downloader/wiki/Command-Line-Usage
.. _Python Wiki: https://github.com/xenova/chat-downloader/wiki/Python-Documentation

