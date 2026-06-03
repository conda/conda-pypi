"""
Errors specific to conda pypi.
"""

from conda.exceptions import CondaError


class CondaPypiError(CondaError):
    pass


class UnableToConvertToRepodataEntry(CondaPypiError):
    pass
