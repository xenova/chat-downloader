import os
import json
import csv

from ..utils import flatten_json


class CW:
    """
    Base class for continuous file writers.

    Can be used as a context manager (using the `with` keyword).
    Otherwise, the writer can be explicitly closed.
    """

    def __init__(self, file_name, overwrite=False):
        self.file_name = file_name
        # subclasses must set self.file

        if not os.path.exists(file_name) or overwrite:
            directory = os.path.dirname(file_name)
            if directory:  # (non-empty directory - i.e. not in current folder)
                # must make parent directory
                os.makedirs(directory, exist_ok=True)
            open(file_name, 'w').close()  # create an empty file

    def __enter__(self):
        return self

    def close(self):
        self.file.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def write(self, item, flush=False):
        raise NotImplementedError

    def flush(self):
        self.file.flush()


class JSONCW(CW):
    """
    Class used to control the continuous writing of a list of dictionaries to a JSON file.
    """

    def __init__(self, file_name, overwrite=False, indent=None, separator=', ', indent_character=' ', sort_keys=True):
        super().__init__(file_name, overwrite)
        # open file for appending and reading in binary mode.
        self.file = open(self.file_name, 'rb+')

        # self.file.seek(0)  # go to beginning of file

        previous_items = []  # save previous
        if not overwrite:  # may have other data
            try:
                previous_items = json.load(self.file)
            except json.decoder.JSONDecodeError:
                pass
        self.file.truncate(0)  # empty file

        self.indent = indent
        self.separator = separator
        self.indent_character = indent_character
        self.sort_keys = sort_keys

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
            # print(self.file.closed)
            # seek to last character
            self.file.seek(-len(indent_padding) - 1, os.SEEK_END)
            self.file.write(self.separator.encode())  # Write the separator

            # self.file.truncate()

        self.file.write(to_write.encode())  # Dump the item
        self.file.write((indent_padding + ']').encode())  # Close the array

        if flush:
            self.flush()


class CSVCW(CW):
    """
    Class used to control the continuous writing of a list of dictionaries to a CSV file.
    """

    def __init__(self, file_name, overwrite=False, sort_keys=True):
        super().__init__(file_name, overwrite)

        self.file = open(self.file_name, 'a+', newline='',
                         encoding='utf-8')  # , buffering=1

        if not overwrite:
            # save previous data
            self.file.seek(0)  # go to beginning of file
            csv_dict_reader = csv.DictReader(self.file)
            self.columns = list(csv_dict_reader.fieldnames or [])
            self.all_items = [dict(x) for x in csv_dict_reader]
        else:
            self.columns = []
            self.all_items = []

        self._reset_dict_writer()
        self.sort_keys = sort_keys

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


class TXTCW(CW):
    """
    Class used to control the continuous writing of a text to a TXT file.
    """

    def __init__(self, file_name, overwrite=False):
        super().__init__(file_name, overwrite)
        self.file = open(self.file_name, 'a',
                         encoding='utf-8')  # , buffering=1

    def write(self, item, flush=False):
        print(item, file=self.file, flush=flush)  # , flush=True


class ContinuousWriter:
    _SUPPORTED_WRITERS = {
        'json': JSONCW,
        'csv': CSVCW,
        'txt': TXTCW
    }

    def __init__(self, file_name, **kwargs):
        extension = os.path.splitext(file_name)[1][1:].lower()
        writer_class = self._SUPPORTED_WRITERS.get(extension, TXTCW)

        # remove invalid keyword arguments
        new_kwargs = {
            key: kwargs[key] for key in kwargs if key in writer_class.__init__.__code__.co_varnames}
        self.writer = writer_class(file_name, **new_kwargs)

    def write(self, item, flush=False):
        self.writer.write(item, flush)

    def __enter__(self):
        return self

    def close(self):
        self.writer.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
