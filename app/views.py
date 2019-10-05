#!flask/bin/python
# -*- coding: utf-8 -*-

"""Views returned by the server APP:
Takes the tasks from the Redis DB and returns the status of them. Also, it updates the Redis DB entries.
"""


import hashlib
import sys

from collections import defaultdict, namedtuple
from datetime import datetime
from flask import render_template, request
from json import dumps, loads
from os import path
from time import time

# Add custom libs
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from app import APP
from app.utils import ShaUtils, ResponseUtils


# Root route
@APP.route('/')
def root():
    """Returns the welcome page for the user accessing the API by using a browser."""
    return render_template('under_construction.html', **locals())


@APP.route('/dump_db_content', methods=['POST'])
@ResponseUtils.return_json
def dump_db_content():
    """Dump the content of the Redis DB as a JSON."""

    Response = namedtuple('Response', "return_code return_data")

    redis_client = APP.config.get('REDIS')
    if not redis_client:
        return Response(return_code=400, return_data={
            "dataBody": {
                "response": "---",
                "reason": "Unknown"
            },
            "error": True
        })

    dump_content = dict()
    for key in redis_client.scan_iter():
        dump_content.update({key: loads(redis_client.get(key))})

    if not dump_content:
        return Response(return_code=200, return_data={"dataBody": "EMPTY", "error": False})

    return Response(return_code=200, return_data=dump_content)


@APP.route('/get_product_info/<product>/<object_id>', methods=['GET'])
@ResponseUtils.return_json
def get_product_info(object_id=None):
    """Get status about a product and object ID from Redis.
    :param object_id: Object ID in Redis (SHA512) [string]
    """

    Response = namedtuple('Response', "return_code return_data")

    # Check if received ID is SHA512
    if not ShaUtils.is_sha512(maybe_sha=object_id):
        return Response(return_code=400, return_data={
            "dataBody": {
                "response": "Bad request",
                "reason": "Wrong ID"
            },
            "error": True
        })

    redis_object = APP.config.get('REDIS')
    if not redis_object:
        return Response(return_code=400, return_data={
            "dataBody": {
                "response": "---",
                "reason": "Unknown"
            },
            "error": True
        })

    object_info = redis_object.get(object_id)
    if not object_info:
        return Response(return_code=424, return_data={
            "dataBody": {
                "response": "Bad request",
                "reason": "Requested ID does not exist in the DB"
            },
            "error": True
        })

    # Return response depending on the findings
    return_data = defaultdict(dict)
    return_data.update(
        {
            "dataBody": {
                "status": loads(object_info).get('status'),
                "bambooUrl": loads(object_info).get('bamboo_build_url') or "NO_URL",
            },
            "error": False
        }
    )

    # If plan has finished => add artifact links
    if return_data['dataBody']['status'] == 'FINISHED':
        return_data['dataBody']['artifactsUrl'] = loads(object_info).get('artifacts', [])

    return Response(return_code=200, return_data=return_data)


@APP.route('/create_task/<product>/<resource>', methods=['GET', 'POST'])
@ResponseUtils.return_json
def create_task(product=None):
    """Creates a request for a specific product.
    :param product: The name of the product [string]
    """

    Response = namedtuple('Response', "return_code return_data")

    # Notify user if he/she uses a wrong method in API call
    if request.method == 'GET':
        return Response(return_code=405, return_data={
            "dataBody": {
                "response": "Bad request",
                "reason": "Please only use 'POST' requests"
            },
            "error": True
        })

    bamboo_server = APP.config.get('BAMBOO_SERVER')
    bamboo_main_plan_url = request.values.get('planUrl')
    bamboo_wait_for_plan_to_finish = request.values.get('waitForPlan')
    bamboo_artifact_on_stage = request.values.get('artifactsOnStage')
    bamboo_artifact_names = request.values.get('artifactNames', '').strip().split(",")

    redis_object = APP.config.get('REDIS')
    if not redis_object:
        return Response(return_code=400, return_data={
            "dataBody": {
                "response": "---",
                "reason": "Unknown"
            },
            "error": True
        })

    internal_id = hashlib.sha512(str(datetime.now()).encode()).hexdigest()

    # Check if the user supplied some options or not
    request_opts = dict()
    if request.args:
        request_opts = request.args

    # Set object in Redis
    redis_object.set(
        internal_id,
        dumps(
            {
                'bamboo_artifact_names': bamboo_artifact_names,
                'bamboo_artifact_on_stage': bamboo_artifact_on_stage,
                'bamboo_main_plan_url': bamboo_main_plan_url,
                'bamboo_server': bamboo_server,
                'bamboo_state': "NEW",
                'bamboo_wait_for_plan_to_finish': bamboo_wait_for_plan_to_finish,
                'request_options': request_opts,
                'product_name': product,
                'status': "NEW_REQUEST",
                'start_build_retries': 0,
                'stop_build_retries': 0,
                'insert_time': time()
            }
        )
    )

    # Return response depending on the findings
    app_config = APP.config.get('APP_CONFIG', {})
    if not redis_object.get(internal_id):
        return Response(return_code=400, return_data={"error": True})

    return Response(
        return_code=200,
        return_data={
            "dataBody":
                {
                    "bambooMainPlanUrl": bamboo_main_plan_url,
                    "id": internal_id,
                    "urlToCheckForStatus": r"http://{host}:{port}/get_product_info/{product}/{id}".format(
                        host=app_config.get('host', "host"), port=app_config.get('port', "0000"),
                        product=product, id=internal_id
                    )
                },
            "error": False
        }
    )
