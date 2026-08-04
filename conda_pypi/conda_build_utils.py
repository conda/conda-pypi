# Copied from and adapted from conda-build
# Copyright (C) 2014 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

import hashlib
from enum import Enum
from os import DirEntry
from os.path import isfile, islink


class PathType(Enum):
    """
    Refers to if the file in question is hard linked or soft linked. Originally
    designed to be used in paths.json
    """

    hardlink = "hardlink"
    softlink = "softlink"
    directory = "directory"  # rare or unused?

    # these additional types should not be included by conda-build in packages
    linked_package_record = "linked_package_record"  # a package's .json file in conda-meta
    pyc_file = "pyc_file"
    unix_python_entry_point = "unix_python_entry_point"
    windows_python_entry_point_script = "windows_python_entry_point_script"
    windows_python_entry_point_exe = "windows_python_entry_point_exe"

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name


def sha256_checksum(filename, entry: DirEntry | None = None, buffersize=1 << 18):
    if not entry:
        is_link = islink(filename)
        is_file = isfile(filename)
    else:
        is_link = entry.is_symlink()
        is_file = entry.is_file()
    if is_link and not is_file:
        # symlink to nowhere so an empty file
        # this is the sha256 hash of an empty file
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    if not is_file:
        return None
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(buffersize), b""):
            sha256.update(block)
    return sha256.hexdigest()
