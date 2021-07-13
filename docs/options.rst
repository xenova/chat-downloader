General Options
===============

This page provides descriptions for the different available options. For the most part, there are two types of options:

1. Initialization - These options are used when creating a new ``ChatDownloader`` object. All subsequent ``get_chat`` method calls using this object will use these options.
2. Program - These options are passed to the object's ``get_chat`` method. These options are not shared between other calls to ``get_chat``.

For implementation details and examples, see the corresponding Command-line or Python usage guide.

Initialization Options
----------------------


Program Options
----------------------


Message groups and types
~~~~~~~~~~~~~~~~~~~~~~~~

There are two ways to specify what types of chat messages will be included:

1. Message types - The value of `message_type` for the chat object
2. Message groups - A site-specific collection of message types. One message group contains a list of message types, and each site has a number of message groups which can be used. See below for message groups (and their associated message types) for the supported sites.

Please note that these two options are **mutually exclusive**. So, you may only specify one at a time.


Message groups and types for the supported sites are specified as follows:

.. code::

    site.com
    --------
     - message_group_1
       - message_type_1
       - message_type_2
     - message_group_2
       - message_type_3
       - message_type_4

For example, specifying `message_group_1` as a message group will include all messages whose type is `message_type_1` or `message_type_2`. Alternatively, one may specify individual message types, e.g. `message_type_3`.


The following message groups and message types are allowed for each supported site:

.. program-output:: python scripts/generate_message_groups.py
    :shell:


Outputting to a file
~~~~~~~~~~~~~~~~~~~~
