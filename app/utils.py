#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

"""Misc utils for APP."""


import functools
import json
import re
import sys

from os import path

# Add custom libs
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from app import APP


class ResponseUtils(object):
    """Utils class used to return custom response back to app."""

    @staticmethod
    def return_json(func):
        """Wrapper to return a custom JSON response."""

        @functools.wraps(func)
        def inner(*args, **kwargs):
            # Default HTTP return code
            returned_code_value = 444

            returned_data = ""

            try:
                # Getting the returned value
                returned_code_value, returned_data = func(*args, **kwargs)
            except TypeError as err:
                print("Error when processing function: {msg}".format(msg=err))
                if not returned_data:
                    return APP.response_class(
                        response=json.dumps("NO DATA TO RETURN"),
                        status=406,
                        mimetype='application/json'
                    )

            if not isinstance(returned_data, dict):
                response = APP.response_class(
                    response=json.dumps("DATA CASTING ERROR"),
                    status=406,
                    mimetype='application/json'
                )
            else:
                response = APP.response_class(
                    response=json.dumps(returned_data),
                    status=returned_code_value,
                    mimetype='application/json'
                )

            # Returning the value to the original frame
            return response

        return inner


class ShaUtils(object):
    """ShaUtils."""

    @staticmethod
    def is_sha512(maybe_sha):
        """Check if string is SHA512.
        :param maybe_sha: String to check for SHA512 [string]
        """
        result = None

        try:
            result = re.match(r'^\w{128}$', maybe_sha).group(0)
        except:
            pass

        return result is not None


def main():
    """The main function"""
    pass


####################################################################################################
# Standard boilerplate to call the main() function to begin the program.
# This only runs if the module was *not* imported.
#
if __name__ == '__main__':
    main()
