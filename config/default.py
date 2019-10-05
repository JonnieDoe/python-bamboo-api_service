#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

"""Reads the data in order to run the app."""


import redis

from configparser import ConfigParser
from importlib import resources


DEBUG = False

CFG = ConfigParser()
CFG.read_string(resources.read_text('config', "config.txt"))

BAMBOO_SERVER = CFG.get('bamboo', "server")
BAMBOO_USER = CFG.get('bamboo', "username")
BAMBOO_PASS = CFG.get('bamboo', "password")

HOST_NAME = CFG.get('host_name', "fqdn")
HOST_PORT = CFG.get('host_name', "port")
APP_CONFIG = {
    # This is important in order to know what URL to send back to user request
    'host': HOST_NAME,
    'port': HOST_PORT
}

REDIS_HOST = CFG.get('redis_server', "server")
REDIS_PORT = CFG.get('redis_server', "port")
REDIS_PASS = CFG.get('redis_server', "password")
REDIS = redis.StrictRedis(host=REDIS_HOST,
                          port=REDIS_PORT,
                          db=0,
                          password=REDIS_PASS,
                          socket_timeout=None,
                          connection_pool=None,
                          charset='utf-8',
                          errors='strict',
                          unix_socket_path=None,
                          decode_responses=True)
