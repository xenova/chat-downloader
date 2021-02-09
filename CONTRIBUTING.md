## Developer Instructions

If you wish to assist in development, first install the developer dependencies:
```
pip install -e .[dev]
```

### Basic developer guide


1. [Fork this repository](https://github.com/xenova/chat-downloader/fork).
2. Clone the forked repository with:

    ```
    git clone git@github.com:YOUR_GITHUB_USERNAME/chat-downloader.git
    ```

3. Start a new branch with:

    ```
    cd chat-downloader
    git checkout -b name
    ```

4. Make changes. See below for common changes to be made.


5. Test your changes with pytest:

    Depending on the changes made, run the appropriate tests to ensure everything still works as intended.


    1. To run all tests:

        ```
        pytest -v
        ```

    2. To run tests for all sites:

        ```
        pytest -v tests/test_chat_downloader.py::TestChatDownloader
        ```

    3. To run the tests for a specific site:

        ```
        pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YourChatDownloader_TestNumber
        ```

        e.g.

        ```
        pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YouTubeChatDownloader_1
        ```


6. Make sure your code follows our coding conventions and check the code with [flake8](https://flake8.pycqa.org/en/latest/):
    ```
    flake8 path/to/code/to/check.py
    ```

    While we encourage users to follow flake8 conventions, some warnings are not very important and can be ignored, e.g:
    ```
    flake8 path/to/code/to/check.py --ignore E501,W503,W504
    ```



7. When the tests pass, [add](https://git-scm.com/docs/git-add) the new files and [commit](https://git-scm.com/docs/git-commit) them and [push](https://git-scm.com/docs/git-push) the result, like this:
    ```
    git add path/to/code.py
    git commit -m 'message'
    git push origin name
    ```

8. Finally, [create a pull request](https://help.github.com/articles/creating-a-pull-request). We'll then review and merge it.





### Templates
*Coming soon*
