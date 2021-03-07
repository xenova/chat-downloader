
.. py:module:: chat_downloader
.. py:currentmodule:: chat_downloader


:py:class:`ChatDownloader`
**************************


.. autoclass:: chat_downloader.ChatDownloader
    :members:
    :undoc-members:
    :show-inheritance:

Examples
--------

#. Message groups and types

   Options are specified as a list of strings.

   .. code:: python

       from chat_downloader import ChatDownloader

       downloader = ChatDownloader()

       url = 'https://www.youtube.com/watch?v=n5aQeLwwEns'

       # 1. Using message groups:
       groups_example = downloader.get_chat(url, message_groups=['messages', 'superchat'])

       # 2. Using message types:
       types_example = downloader.get_chat(url, message_types=['membership_item'])

#. 2
