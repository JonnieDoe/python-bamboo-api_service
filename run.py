#!flask/bin/python
# -*- coding: utf-8 -*-

"""Start the Flask server."""


import sys
from os import path

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from app import APP


APP.run(host="0.0.0.0", port=8888, debug=True)
