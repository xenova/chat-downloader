###########
Basic Usage
###########


Chat items are parsed into JSON objects (a.k.a. dictionaries). For a
comprehensive, documented list of included fields, consult the `Chat
Item Wiki`_.

Command line:
-------------

.. code:: console

   $ chat_downloader https://www.youtube.com/watch?v=5qap5aO4i9A

For advanced command line use-cases and examples, consult the `Command
Line Wiki`_.

Python:
-------

.. code:: python

   from chat_downloader import ChatDownloader

   url = 'https://www.youtube.com/watch?v=5qap5aO4i9A'
   chat = ChatDownloader().get_chat(url)       # create a generator
   for message in chat:                        # iterate over messages
       chat.print_formatted(message)           # print the formatted message

For advanced python use-cases and examples, consult the `Python Wiki`_.
