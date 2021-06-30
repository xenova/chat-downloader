*********
Changelog
*********

master
======

v0.0.4
======

:Date: 11 February 2021

Sites
-----

* Use ``_NAME`` attribute and improve class structure
* [YouTube] Unpack value returned from ``parse_runs`` (Fixes #59)
* [Twitch] Move ``is_moderator``, ``is_subscriber`` and ``is_turbo`` to author dictionary


v0.0.3
======

:Date: 10 February 2021

Core
----

* Allow reusing of sessions

Sites
-----

* Improved remapping (more advanced)
* YouTube and Twitch: Parse emotes to get emote id and URLs

Testing
-------

* Improved unit testing with pytest

Workflows
---------

* CI with GitHub actions
* Automatic distribution with twine on release


v0.0.2
======

:Date: 3 February 2021

* Ensure mutual exclusion for message groups and types


v0.0.1
======

:Date: 2 February 2021

* Initial release
