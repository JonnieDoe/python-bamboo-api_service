#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

"""The module controls the load and the run of Flask server."""


from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension


APP = Flask(__name__, template_folder="templates", static_folder="static", instance_relative_config=True)

# Load the default configuration
# Now we can access the configuration variables via app.config["VAR_NAME"]
# APP.config.from_object('config.development')
APP.config.from_object('config.default')

# The toolbar is only enabled in debug mode and if ['SECRET_KEY'] is enabled
TOOLBAR = DebugToolbarExtension()
TOOLBAR.init_app(APP)


from app import views
