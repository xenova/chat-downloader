Contributing Guide
==================


Developers
~~~~~~~~~~

The following section outlines the basic procedure for people who
want to assist in development.

Add features, fix bugs or write documentation
---------------------------------------------

#. `Fork this repository`_.

#. Clone the forked repository with:

   .. code:: console

       $ git clone git@github.com:YOUR_GITHUB_USERNAME/chat-downloader.git


#. Start a new branch with:

   .. code:: console

       $ cd chat-downloader
       $ git checkout -b name


#. Set up your environment by installing the developer dependencies:

   .. code:: console

       $ pip install -e .[dev]

#. Make changes. See below for common changes to be made.

#. Test your changes with pytest:

   Depending on the changes made, run the appropriate tests to ensure
   everything still works as intended.

   #. To run all tests:

      .. code:: console

          $ pytest -v

   #. To run tests for all sites:

      .. code:: console

          $ pytest -v tests/test_chat_downloader.py::TestChatDownloader


   #. To run the tests for a specific site:

      .. code:: console

          $ pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YourChatDownloader_TestNumber

      e.g.

      .. code:: console

          $ pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YouTubeChatDownloader_1

#. Make sure your code follows our coding conventions and check the code
   with `flake8`_:

   .. code:: console

       $ flake8 path/to/code/to/check.py


   While we encourage users to follow flake8 conventions, some warnings
   are not very important and can be ignored, e.g:

   .. code:: console

       $ flake8 path/to/code/to/check.py --ignore E501,W503,W504

#. When the tests pass, `add`_ the new files and `commit`_ them and
   `push`_ the result, like this:

   .. code:: console

       $ git add path/to/code.py
       $ git commit -m 'message'
       $ git push origin name


#. Finally, `create a pull request`_. We'll then review and merge it.

Starting templates
------------------

When adding new features, we encourage developers to use these templates
as starting points. This helps ensure consistency across the codebase.

New site
^^^^^^^^

*Coming soon*




.. _Fork this repository: https://github.com/xenova/chat-downloader/fork
.. _flake8: https://flake8.pycqa.org/en/latest/
.. _add: https://git-scm.com/docs/git-add
.. _commit: https://git-scm.com/docs/git-commit
.. _push: https://git-scm.com/docs/git-push
.. _create a pull request: https://help.github.com/articles/creating-a-pull-request



Testing
~~~~~~~

If you are unable to write code but still wish to assist, we encourage
users to run commands with the ``--testing`` flag included. This will
print debugging messages and pause once something unexpected happens
(e.g. when an unknown item is being parsed). If something happens,
please raise an issue and we will fix it or add support for it as
soon as possible! For example:

.. code:: console

    $ chat_downloader https://www.youtube.com/watch?v=5qap5aO4i9A --testing

Some extractors use undocumented endpoints and as a result, users may
encounter items which will not be parsed correctly. Increased testing
will help find these items and ultimately improve functionality of the
software for other users. Note that this will not affect any output you
write to files (using ``--output``).


Sponsor
~~~~~~~

`Chat Downloader`_ has always and will always be free. If you are feeling
generous, donations are always appreciated!

* https://ko-fi.com/xenova
* https://www.buymeacoffee.com/xenova

.. _Chat Downloader: https://github.com/xenova/chat-downloader
