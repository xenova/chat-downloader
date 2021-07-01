General Options
===============

This page provides descriptions for the different available options. For the most part, there are two types of

For implementation details, see the corresponding Command-line or Python usage guide.

Message groups and types
------------------------

There are two ways to specify what types of chat messages will be included:

1. Message types - The value of `message_type` for the chat object

2. Message groups - A site-specific collection of message types. One message group contains a list of message types, and each site has a number of message groups which can be used. See below for message groups (and their associated message types) for the supported sites.

Please note that these two options are **mutually exclusive**. So, you may only specify one at a time.

For examples, see Command-line or Python Usage



Outputting to a file
--------------------
