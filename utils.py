#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

"""Utils module: A collection of useful methods."""


from datetime import datetime
from os import path


class FileUtils(object):
    """Utilities for file handling tasks."""

    def __init__(self):
        """Construct the FileUtils instance object."""
        self.__disk_file = None

    @property
    def disk_file(self):
        """Get the path to the actual file."""
        return self.__disk_file

    @disk_file.setter
    def disk_file(self, disk_file_path):
        """Sets the full path tot the disk file."""
        self.__disk_file = disk_file_path

    def write_to_disk_file(self, content=None):
        """Write input content to corresponding log file.
        :param content: Content to write on disk file [string]
        """

        if not self.disk_file or not content:
            return

        current_date = datetime.now()

        try:
            with open(self.disk_file, 'a+') as file_handle:
                header = "*" * 120

                file_content = str(
                    "\n{header}\n{date}\t{content}".format(header=header, date=current_date, content=content)
                )

                file_handle.write(file_content)
        except Exception as err:
            print(
                "\nError when trying to write status on disk log file: [{file}]\n\t{err}\n".format(file=self.disk_file,
                                                                                                   err=err)
            )


class LoggingUtils(object):
    """Utilities for logging."""

    def __init__(self, path_to_parent_dir=None):
        """Create LoggingUtils instance object.
        :param path_to_parent_dir: Full path tot parent dir where to write logs [string]
        """
        self.__path_to_parent_dir = path_to_parent_dir

    @property
    def path_to_parent_dir(self):
        """Get the path to the parent directory."""
        return self.__path_to_parent_dir

    @property
    def logs_paths(self):
        """Compute the logs file paths.
        :return A dict with all paths
        """

        if not self.path_to_parent_dir:
            return {}

        current_date = datetime.now().date()

        # Log files
        err_log_file = path.normpath(
            path.join(self.path_to_parent_dir, "logs", "errors", "errors_{0}.log".format(current_date))
        )
        bamboo_log_file = path.normpath(
            path.join(self.path_to_parent_dir, "logs", "bamboo", "bamboo_{0}.log".format(current_date))
        )
        misc_log_file = path.normpath(
            path.join(self.path_to_parent_dir, "logs", "misc", "misc_{0}.log".format(current_date))
        )

        return {
            'bamboo': bamboo_log_file,
            'errors': err_log_file,
            'misc': misc_log_file,
        }
