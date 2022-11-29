import os
import json
import csv
import shutil

from ..utils.core import flatten_json


class CW:
    """
    Base class for continuous file writers.
    """

    def __init__(self, file_name, overwrite=True, **kwargs):
        """Create a CW object.

        :param file_name: The name of the file to write to
        :type file_name: str
        :param overwrite: Whether to overwrite if the file already exists, defaults to True
        :type overwrite: bool, optional
        """
        self.file_name = file_name
        self.overwrite = overwrite

    def close(self):
        self.file.close()

    def write(self, item, flush=False):
        """Write a chat item to the file. This method should be implemented in subclasses.

        :param item: The chat item
        :type item: dict
        :param flush: Whether to force the file to be flushed after writing,
            defaults to False
        :type flush: bool, optional
        :raises NotImplementedError: if the method is not implemented
            and called from a subclass.
        """
        raise NotImplementedError

    def flush(self):
        self.file.flush()


class JSONCW(CW):
    """
    Class used to control the continuous writing of a list of dictionaries to a JSON file.
    """

    def __init__(self, file_name, indent=None, separator=', ', indent_character=' ', sort_keys=True, **kwargs):
        super().__init__(file_name, **kwargs)

        self.indent = indent
        self.separator = separator
        self.indent_character = indent_character
        self.sort_keys = sort_keys

        # open file for appending and reading in binary mode.
        self.file = open(self.file_name, 'rb+')

        previous_items = []  # save previous
        if not self.overwrite:  # may have other data
            try:
                previous_items = json.load(self.file)
            except json.decoder.JSONDecodeError:
                # TODO create .tmp, file shutil.copy(), self.file.read()
                pass

        self.file.truncate(0)  # empty file

        # rewrite with new formatting
        for previous_item in previous_items:
            self.write(previous_item)

    def _multiline_indent(self, text):
        padding = self.indent * \
            self.indent_character if isinstance(
                self.indent, int) else self.indent
        return ''.join(map(lambda x: padding + x, text.splitlines(True)))

    def write(self, item, flush=False):

        self.file.seek(0, os.SEEK_END)  # Go to the end of file

        to_write = json.dumps(
            item, indent=self.indent, sort_keys=self.sort_keys)
        if self.indent is not None:
            indent_padding = '\n'  # to add on a new line
            to_write = indent_padding + self._multiline_indent(to_write)
        else:
            indent_padding = ''

        if self.file.tell() == 0:  # Check if file is empty
            # If empty, write the start of an array
            self.file.write('['.encode())
        else:
            # seek to last character
            self.file.seek(-len(indent_padding) - 1, os.SEEK_END)
            self.file.write(self.separator.encode())  # Write the separator

        self.file.write(to_write.encode())  # Dump the item
        self.file.write((indent_padding + ']').encode())  # Close the array

        if flush:
            self.flush()


class CSVCW(CW):
    """
    Class used to control the continuous writing of a list of dictionaries to a CSV file.
    """

    def __init__(self, file_name, sort_keys=True, **kwargs):
        super().__init__(file_name, **kwargs)
        self.sort_keys = sort_keys
        self.file = open(self.file_name, 'a+', newline='', encoding='utf-8')

        if not self.overwrite:
            # save previous data
            self.file.seek(0)  # go to beginning of file
            csv_dict_reader = csv.DictReader(self.file)
            self.columns = list(csv_dict_reader.fieldnames or [])
            self.all_items = [dict(x) for x in csv_dict_reader]
        else:
            self.columns = []
            self.all_items = []

        self._reset_dict_writer()

    def _reset_dict_writer(self):
        self.csv_dict_writer = csv.DictWriter(
            self.file, fieldnames=self.columns)

    def write(self, item, flush=False, flatten=True):
        if flatten:
            item = flatten_json(item)
        self.all_items.append(item)

        new_columns = [column for column in item.keys()
                       if column not in self.columns]
        if new_columns:  # new column(s) found, must rewrite whole file
            self.columns += new_columns
            if self.sort_keys:
                self.columns.sort()

            self.file.truncate(0)  # empty file

            self._reset_dict_writer()  # update writer with new columns
            self.csv_dict_writer.writeheader()  # write new header
            self.csv_dict_writer.writerows(self.all_items)  # write previous
        else:
            self.csv_dict_writer.writerow(item)  # write newest item

        if flush:
            self.flush()


class JSONLCW(CW):
    """
    Class used to control the continuous writing of a JSON lines.
    """

    def __init__(self, file_name, sort_keys=True, **kwargs):
        super().__init__(file_name, **kwargs)
        self.sort_keys = sort_keys
        self.file = open(self.file_name, 'a', encoding='utf-8')

    def write(self, item, flush=False):
        print(json.dumps(item, sort_keys=self.sort_keys),
              file=self.file, flush=flush)


class TXTCW(CW):
    """
    Class used to control the continuous writing of a text to a TXT file.
    """

    def __init__(self, file_name, **kwargs):
        super().__init__(file_name, **kwargs)
        self.file = open(self.file_name, 'a', encoding='utf-8')

    def write(self, item, flush=False):
        print(item, file=self.file, flush=flush)


class ContinuousWriter:
    _SUPPORTED_WRITERS = {
        'json': JSONCW,
        'csv': CSVCW,
        'jsonl': JSONLCW,
        'txt': TXTCW
    }

    def __init__(self, file_name=None, overwrite=True, format=None, lazy_initialise=False, **kwargs):
        """Create a ContinuousWriter object.

        :param file_name: The name of the file to write to
        :type file_name: str
        :param overwrite: Whether to overwrite if the file already exists, defaults to True
        :type overwrite: bool, optional
        :param format: The output format, defaults to None (use the extension to decide)
        :type format: str, optional
        :param lazy_initialise: Skip file creation on initialisation, defaults to False.
        :type lazy_initialise: bool, optional
        """
        super().__setattr__('data', dict())
        self.file_name = file_name
        self.overwrite = overwrite
        self.format = format
        self.lazy_initialise = lazy_initialise
        self.writer = None
        self.data.update(kwargs)

        self._initialised = False
        if not self.lazy_initialise:
            self._real_init()

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]

        raise AttributeError(
            f"'ContinuousWriter' object has no attribute '{name}'")

    def __setattr__(self, key, value):
        self.data[key] = value

    def is_default(self):
        return isinstance(self.writer, TXTCW)

    def is_initialised(self):
        return self._initialised

    def _real_init(self):
        if self._initialised:
            return

        self._initialised = True

        if self.file_name is None:
            raise AttributeError('File name not set')

        if not os.path.exists(self.file_name) or self.overwrite:
            directory = os.path.dirname(self.file_name)
            if directory:  # (non-empty directory - i.e. not in current folder)
                # must make parent directory
                os.makedirs(directory, exist_ok=True)
            open(self.file_name, 'w').close()  # create an empty file

        extension = self.format or os.path.splitext(self.file_name)[
            1][1:].lower()
        writer_class = ContinuousWriter._SUPPORTED_WRITERS.get(
            extension, TXTCW)
        self.writer = writer_class(**self.data)

    def write(self, item, flush=False):
        if not self._initialised:  # create file when first item is written
            self._real_init()

        self.writer.write(item, flush)

    def __enter__(self):
        return self

    def close(self):
        if self._initialised:
            self.writer.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
