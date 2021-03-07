Command Line Usage
==================


Overview
--------

A full list of command line arguments can be obtained by running the help command:

.. code:: console

   $ chat_downloader -h

The output of which is as follows:

.. program-output:: cd .. && python -m chat_downloader -h
    :shell:

Examples
--------

#. Message groups and types

   Options are specified by a space- or comma-separated list. If you specify more than one item, enclose the argument in quotation marks.

   - Using message groups:

   .. code:: console

       $ chat_downloader https://www.youtube.com/watch?v=n5aQeLwwEns --message_groups "messages superchat"

   -  Using message types:

   .. code:: console

       $ chat_downloader https://www.youtube.com/watch?v=n5aQeLwwEns --message_types membership_item


#. Output to file

.. code:: console

   $ chat_downloader https://www.youtube.com/watch?v=n5aQeLwwEns --output chat.json
