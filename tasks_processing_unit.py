#!/usr/bin/python -tt
# -*- coding: utf-8 -*-

"""Main processing module:
Takes the tasks from the Redis DB and starts to consume them. Also, it updates the Redis DB entries.
"""


import argparse
import redis
import sys

from collections import namedtuple
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from json import loads, dumps
from os import path, sep
from time import sleep, time
from urllib.parse import urlparse

# Add custom libs
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
from bamboo_api import BambooAPI
from config.default import REDIS_HOST, REDIS_PASS, REDIS_PORT
from utils import FileUtils, LoggingUtils


LOGS = dict()


class RedisCommunication(object):
    """Redis server communication data."""

    CLIENT = redis.StrictRedis(host=REDIS_HOST,
                               port=REDIS_PORT,
                               db=0,
                               password=REDIS_PASS,
                               socket_timeout=None,
                               connection_pool=None,
                               charset='utf-8',
                               errors='strict',
                               unix_socket_path=None,
                               decode_responses=True)


class BambooUtils(BambooAPI):
    """Bamboo utils class used to interact with Bamboo API from 'bamboo_api' module."""

    def __init__(self, verbose=False, bamboo_server=None):
        super().__init__(verbose=verbose, bamboo_server=bamboo_server)

        if verbose:
            BambooAPI.verbose.fset(self, verbose)

        if bamboo_server:
            BambooAPI.bamboo_server.fset(self, bamboo_server)

    ###########################################################################################
    def trigger_bamboo_plan(self, values=None):
        """Trigger specific Bamboo plan using custom plan options.
        :param values: Options to send to Bamboo when triggering plan [dictionary]
        :return A dictionary
        """

        # Default response to return
        response = {
            'response': None,
            'content': False
        }

        if not values:
            response['content'] = "Incorrect input provided"
            return response

        try:
            plan_trigger = self.trigger_plan_build(bamboo_server=values.get('bamboo_server'),
                                                   plan_key=values.get('bamboo_plan_key'),
                                                   req_values=(True, values.get('bamboo_plan_variables')))
        except Exception as err:
            response['response'] = False
            response['content'] = err
            return response

        response_status_code = plan_trigger.get('status_code')
        if response_status_code != 200:
            err_msg = (
                "status_code: {status_code}\n"
                "{content}".format(status_code=response_status_code, content=plan_trigger.get('content'))
            )
            if self.verbose:
                print(err_msg)

            response['response'] = False
            response['content'] = response_status_code

            return response

        # Get returned content
        response['content'] = {
            'build_result_key': plan_trigger.get('content', {}).get('buildResultKey'),
            'build_plan_url': plan_trigger.get('content', {}).get('link', {}).get('href')
        }

        # Set flag: True
        response['response'] = True

        return response

    ###########################################################################################
    def get_plan_status(self, bamboo_server=None, plan_key=None):
        """Get the status of a specific Bamboo plan.
        :param bamboo_server: Bamboo server used in API call (e.g.:<bamboo1/bamboo2>) [string]
        :param plan_key: Key of the Bamboo plan [string]
        :return: None, wrong input/wrong API response
                 True, plan is still building
                 False, plan has finished
        """

        # INFO
        #   isBuilding: True => plan is currently running
        #   isBuilding: False => plan may be queued or has finished running

        # Default response to return
        response = {
            'response': None,
            'api_life_cycle_flag': None,
            'extra_info': "Incorrect input!"
        }

        if not plan_key:
            return response

        # Use default bamboo server value from API if not specified
        if not bamboo_server:
            bamboo_server = self.bamboo_server

        try:
            query_plan = self.query_plan(bamboo_server=bamboo_server,
                                         plan_key=plan_key,
                                         query_type="plan_info")
        except Exception as err:
            response['extra_info'] = err
            return response

        response_status_code = query_plan.get('status_code')
        if response_status_code != 200:
            err_msg = (
                "status_code: {status_code}"
                "\n{content}".format(status_code=response_status_code, content=query_plan.get('content'))
            )
            if self.verbose:
                print(err_msg)

            response['extra_info'] = err_msg
            return response

        # Get returned content
        response_content = query_plan.get('content', {})
        finished_status = response_content.get('finished')
        life_cycle = response_content.get('lifeCycleState')
        success_flag = response_content.get('successful')
        build_state = response_content.get('buildState')

        # Debug purpose
        response['extra_info'] = {
            "plan_info": "Plan '{0}' details".format(plan_key),
            "finished": finished_status,
            "lifeCycleState": life_cycle,
            "successful": success_flag,
            "buildState": build_state
        }

        if self.verbose:
            print(
                "\n--------------------------------"
                "\nPlan '{0}' details"
                "\n\t[finished] flag: '{1}'"
                "\n\t[lifeCycleState] flag: '{2}'"
                "\n\t[successful] flag: '{3}'"
                "\n\t[buildState] flag: '{4}'"
                "\n--------------------------------".format(
                    plan_key, finished_status, life_cycle, success_flag, build_state
                )
            )

        # Plan has finished if Bamboo 'finished' flag is true
        if finished_status is False:
            response['response'] = False
            response['api_life_cycle_flag'] = life_cycle
        elif finished_status or life_cycle == "Finished":
            response['response'] = True
            response['success_flag'] = success_flag
            response['api_life_cycle_flag'] = life_cycle

            # Extra check
            if life_cycle != 'Finished':
                response['response'] = False

                if self.verbose:
                    err_msg = (
                        "Plan has finished: {pk}"
                        "\n\tPlan state: {state}"
                        "\n\tPlan life cycle: {life_cycle}"
                        "\n\tFinished: {fin}".format(
                            pk=plan_key, state=response_content.get('state'), life_cycle=life_cycle,
                            fin=finished_status
                        )
                    )
                    print(err_msg)

                response['extra_info'] = (
                    "Plan has finished but 'lifeCycleState' flag is not 'Finished': '{0}'".format(life_cycle)
                )
        else:
            response['extra_info'] = (
                "Plan '{0}' did not returned True/False for 'finished' flag: '{1}'".format(
                    plan_key, finished_status
                )
            )

        return response

    ###########################################################################################
    def query_for_artifacts(self, bamboo_server=None, plan_key=None, job_name=None, artifact_names=None,
                            url_extra_values=None):
        """Query Bamboo plan run for stage artifacts.
        :param bamboo_server: Bamboo server used in API call (e.g.:<bamboo1/bamboo2>) [string]
        :param plan_key: Key of the Bamboo plan [string]
        :param job_name: Bamboo job name [string]
        :param artifact_names: Names of the artifacts as in Bamboo plan stage job [tuple]
        :param url_extra_values: Extra values to compound the URL [string]
        :return: {"response": True, "artifacts": artifacts_list, "artifacts_links": artifacts_links}, on success
                 {"response": None}, no input
        """

        # Default response
        response = {
            'response': None,
            'content': None
        }

        if not plan_key or not job_name or not artifact_names:
            response['content'] = "Incorrect input provided"
            return response

        # Use default bamboo server value from API if not specified
        if not bamboo_server:
            bamboo_server = self.bamboo_server

        try:
            artifacts = self.query_job_for_artifacts(bamboo_server=bamboo_server,
                                                     plan_key=plan_key,
                                                     query_type="query_for_artifacts",
                                                     job_name=job_name,
                                                     artifact_names=artifact_names,
                                                     url_extra_values=url_extra_values)
        except Exception as err:
            response['response'] = False
            response['content'] = err
            return response

        if artifacts.get('response') is None:
            if self.verbose:
                print(
                    "Error when trying to query plan for artifacts"
                    "\nMethod returned: {0}\n".format(artifacts.get('content'))
                )

            response['response'] = False
            return response

        if artifacts.get('response') is False:
            if self.verbose:
                print(
                    "Error when trying to query plan for artifacts"
                    "\nURL: {0}"
                    "\nPlan_key: {1}"
                    "\nStage_name: {2}"
                    "\nResponse content: {3}\n".format(
                        artifacts.get('url'), plan_key, job_name, artifacts.get('content')
                    )
                )

            response['response'] = False
            return response

        if self.verbose:
            print(
                "\nSuccessfully queried plan for artifacts"
                "\nPlan_key: {0}"
                "\nStage_name: {1}\n".format(plan_key, job_name)
            )

        response['response'] = True
        response['artifacts'] = artifacts.get('artifacts', [])
        response['artifacts_links'] = artifacts.get('artifacts_links', [])

        return response


class TasksProcessingUnit(BambooUtils):
    """Tasks processing unit for all tasks found in Redis backend"""

    def __init__(self, bamboo_server=None, path_to_parent_dir=None, verbose=False):
        """Create the TPU instance object using custom config.
        :param bamboo_server: Bamboo server name [string]
        :param path_to_parent_dir: Full path to the dir containing the logs [string]
        :param verbose: True/False [boolean]
        """
        super().__init__(bamboo_server=bamboo_server, verbose=verbose)

        self.bamboo_server = bamboo_server
        self.file_utils = FileUtils()
        self.logging_utils = LoggingUtils(path_to_parent_dir=path_to_parent_dir)
        self.verbose = verbose

    def write_to_disk_file(self, content=None, log_file_type=None):
        """Write content to corresponding log file type.
        :param content: Content to write on file [string]
        :param log_file_type: Type of the log file (error/bamboo/misc) [string]
        """

        if not content:
            print("{os_line_sep}No content to write in log file supplied!{os_line_sep}".format(os_line_sep=sep))
            return

        self.file_utils.disk_file = self.logging_utils.logs_paths.get(log_file_type)
        if not self.file_utils:
            print(
                "{os_line_sep}Could not get the log file based on log_type option '{log_type}'!{os_line_sep}".format(
                    os_line_sep=sep, log_type=log_file_type)
            )
            return

        self.file_utils.write_to_disk_file(content=content)

    def process_task(self, value_to_process=None):
        """Check the status of the current task in Redis DB and process the request.
        :param value_to_process: Values used when processing task [dictionary]
        :return: Status of the task
        """

        Response = namedtuple('Response', "code data")

        if not value_to_process:
            return Response(code=None, data="No input data supplied!")

        # Transform returned Redis data type to dict
        value_to_process = loads(value_to_process)

        # Get Bamboo server name
        bamboo_server = value_to_process.get('bamboo_server')
        if not bamboo_server:
            return Response(code=False, data="Could not get Bamboo server from DB!")

        # Get Bamboo plan key
        bamboo_plan_key = value_to_process.get('bamboo_main_plan_url', "").split("/")[-1]
        if not bamboo_plan_key:
            return Response(code=False, data="Could not get Bamboo plan key from DB!")

        # Calculate current time in milliseconds
        current_time_epoch_ts = \
            float(Decimal(str(datetime.now().timestamp())).quantize(Decimal('.00000001'), rounding=ROUND_DOWN))

        build_start_time = value_to_process.get('build_start_time', -1)

        # ------------------------------------------------------------------------------------------------------------ #
        if value_to_process.get('status') == 'NEW_REQUEST':
            request_options = value_to_process.get('request_options', {})
            start_build_retries = value_to_process.get('start_build_retries')

            bamboo_plan_variables = dict()
            for option_name, option_value in request_options.items():
                bamboo_plan_variables[option_name] = option_value

            plan_values = {
                'bamboo_server': bamboo_server,
                'bamboo_plan_key': bamboo_plan_key,
                'bamboo_plan_variables': bamboo_plan_variables
            }

            plan_trigger = self.trigger_bamboo_plan(values=plan_values)
            response_status = plan_trigger.get('response')
            if not response_status:
                if not start_build_retries:
                    # Signal to erase the object from Redis DB
                    return Response(code=True, data={
                        'action_label': "ERASE",
                        'bamboo_status': 'NOT_STARTED',
                        'data': "Could not start the Bamboo plan! Could not get 'start_build_retries' "
                                "from db @2nd attempt",
                        'retry': start_build_retries
                    })

                # This is used in order to avoid to start a plan indefinitely (network failure, Bamboo failure etc)
                if start_build_retries < 5:
                    return Response(code=False, data={
                        'bamboo_status': 'NOT_STARTED',
                        'data': "Could not get start the Bamboo plan! Trying one more time!",
                        'retry': start_build_retries + 1
                    })

                # Signal to erase the object from Redis DB
                return Response(code=True, data={
                    'action_label': "ERASE",
                    'bamboo_status': 'NOT_STARTED',
                    'data': "Could not start the Bamboo plan! Giving up and erasing the entry from db!",
                    'retry': start_build_retries
                })

            response_content = plan_trigger.get('content')
            response_content['action_label'] = "PLAN_TRIGGERED"
            response_content['build_start_time'] = time()

            return Response(code=True, data=response_content)
        # ------------------------------------------------------------------------------------------------------------ #
        if value_to_process.get('status') == 'IN_PROGRESS':
            if build_start_time == -1 and self.verbose:
                print(
                    "Error when trying to get build start time from Redis for Bamboo plan '{0}'!".format(
                        value_to_process.get('bamboo_build_url'))
                )

            if (
                (current_time_epoch_ts - build_start_time) > float(value_to_process.get(
                    'bamboo_wait_for_plan_to_finish', 0))
            ):
                if build_start_time == -1 and not self.verbose:
                    print("Could not get the start-time from DB!")

                stop_build_retries = value_to_process.get('stop_build_retries')

                # Stop current build if it has reached timeout
                try:
                    stopping_status = self.stop_build(bamboo_server=bamboo_server,
                                                      plan_key=value_to_process.get('bamboo_build_result_key'),
                                                      query_type='stop_plan')
                except Exception as err:
                    if not stop_build_retries:
                        # Signal to erase the object from Redis DB
                        return Response(code=True, data={
                            'action_label': "ERASE",
                            'bamboo_status': 'NOT_STOPPED',
                            'data': "Could not stop the Bamboo plan! Giving up and erasing the entry from db!",
                            'err:': err
                        })

                    # This is used in order to avoid to stop a plan indefinitely (network failure, Bamboo failure etc)
                    if stop_build_retries < 3:
                        return Response(code=False, data={
                            'bamboo_status': 'NOT_STOPPED',
                            'data': "Could not stop the Bamboo plan! Trying one more time!",
                            'err:': err,
                            'retry': stop_build_retries + 1
                        })

                    # Signal to erase the object from Redis DB
                    return Response(code=True, data={
                        'action_label': "ERASE",
                        'bamboo_status': 'NOT_STOPPED',
                        'data': "Could not stop the Bamboo plan! Giving up and erasing the entry from db!",
                        'err:': err,
                        'retry': stop_build_retries
                    })

                if not stopping_status.get('response'):
                    if self.verbose:
                        print(stopping_status.get('content'))

                    if not stop_build_retries:
                        # Signal to erase the object from Redis DB
                        return Response(code=True, data={
                            'action_label': "ERASE",
                            'bamboo_status': 'NOT_STOPPED',
                            'data': "Could not stop the Bamboo plan! Giving up and erasing the entry from db!"
                        })

                    # This is used in order to avoid to stop a plan indefinitely (network failure, Bamboo failure etc)
                    if stop_build_retries < 3:
                        return Response(code=False, data={
                            'bamboo_status': 'NOT_STOPPED',
                            'data': "Could not stop the Bamboo plan! Trying one more time!",
                            'err:': stopping_status.get('content'),
                            'retry': stop_build_retries + 1
                        })

                    # Signal to erase the object from Redis DB
                    return Response(code=True, data={
                        'action_label': "ERASE",
                        'bamboo_status': 'NOT_STOPPED',
                        'data': "Could not stop the Bamboo plan! Giving up and erasing the entry from db!",
                        'err:': stopping_status.get('content'),
                        'retry': stop_build_retries
                    })

                return Response(
                    code=True, data={
                        'action_label': "FINISHED",
                        'bamboo_status': 'Manually stopped',
                        'build_stop_time': time(),
                        'data': "0ver 60 Minutes have passed! Stopping current Bamboo build!"
                    }
                )

            plan_info = self.get_plan_status(bamboo_server=bamboo_server,
                                             plan_key=value_to_process.get('bamboo_build_result_key'))
            response = plan_info.get("response")
            if response is None:
                return Response(code=False, data={'data': plan_info.get("extra_info")})

            # Plan is running in Bamboo
            if response is False:
                return Response(code=True, data={
                    'action_label': "IN_PROGRESS",
                    'bamboo_status': plan_info.get("api_life_cycle_flag"),
                    'data': "Bamboo plan is in 'IN_PROGRESS'. Waiting to finish!"
                })

            # Plan did not complete in Bamboo == 'NotBuilt' => stopped (unknown reasons)
            if plan_info.get("api_life_cycle_flag") == "NotBuilt":
                return Response(code=True, data={
                    'action_label': "FINISHED",
                    'bamboo_status': "NotBuilt",
                    'build_stop_time': time(),
                    'data': "Plan did not finished"
                })

            # Plan finished in Bamboo but 'success_flag' is false => FAILED plan
            if not plan_info.get("success_flag"):
                return Response(code=True, data={
                    'action_label': "FINISHED",
                    'bamboo_status': "failed",
                    'build_stop_time': time(),
                    'data': "Plan finished",
                    'result': "Failed"
                })

            return Response(code=True, data={
                'action_label': "FINISHED",
                'bamboo_status': plan_info.get("api_life_cycle_flag"),
                'build_stop_time': time(),
                'data': "Plan finished",
                'result': "OK",
                'post_operation': True
            })
        # ------------------------------------------------------------------------------------------------------------ #
        if value_to_process.get('status') == 'FINISHED':
            build_stop_time = value_to_process.get('build_stop_time', -1)
            if build_stop_time == -1:
                print(
                    "Error when trying to get build stop time for Bamboo plan '{0}'".format(
                        value_to_process.get('bamboo_build_url'))
                )

            # Check if finished plan (no matter the result) is > 10 minutes old: if yes, delete the item
            if (current_time_epoch_ts - build_stop_time) > 600.0:
                msg = "0ver 10 Minutes have passed! Removing entry from Redis DB!"

                return Response(code=True, data={
                    'action_label': "ERASE",
                    'data': msg
                })

            # Failed plan => nothing to download
            if (
                value_to_process.get('bamboo_status', "").lower() == 'notbuilt' or
                value_to_process.get('bamboo_status', "").lower() == 'failed'
            ):
                return Response(code=True, data={'action_label': "POST_FINISHED_OPS"})

            if value_to_process.get('post_operation'):
                # Get all artifacts
                job_name = value_to_process.get('bamboo_artifact_on_stage')
                artifact_names = tuple(value_to_process.get('bamboo_artifact_names', []))

                get_list_of_artifacts = self.query_for_artifacts(
                    bamboo_server=bamboo_server,
                    plan_key=value_to_process.get('bamboo_build_result_key'),
                    job_name=job_name,
                    artifact_names=artifact_names
                )
                if not get_list_of_artifacts.get("response"):
                    msg = (
                        "Could not get list of artifacts for stage '{0}' and '{1}' plan!".format(
                            job_name, bamboo_plan_key)
                    )
                    if self.verbose:
                        print(msg)

                    return Response(code=True, data={
                        'action_label': "FINISHED",
                        'artifacts': [],
                        'data': msg,
                        'post_operation': False,
                        'result': "Err: could not get artifacts"
                    })

                # Plan finished and artifacts were found
                return Response(code=True, data={
                    'action_label': "FINISHED",
                    'artifacts': get_list_of_artifacts.get('artifacts_links', []),
                    'post_operation': False
                })

            return Response(code=True, data={'action_label': "POST_FINISHED_OPS"})

        return Response(code=False, data="NO CASE MATCHED!")


def main():
    """The main function."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', dest='dump', required=False, help='Dump Redis DB content on screen!')
    parser.add_argument('-f', dest='flush', required=False, help='Flush Redis DB content!')
    parser.add_argument('-v', dest='verbose', required=False, help='Get verbose about the output!')
    args = parser.parse_args()

    task_pu = TasksProcessingUnit(verbose=bool(args.verbose), path_to_parent_dir=path.dirname(path.abspath(__file__)))

    redis_comm = RedisCommunication()
    redis_client = redis_comm.CLIENT

    # Dump Redis DB on screen
    if bool(args.dump):
        dump_content = dict()
        for key in redis_client.scan_iter():
            dump_content.update({key: loads(redis_client.get(key))})

        if not dump_content:
            print("\nRedis DB is empty\n")
        else:
            print(dumps(dump_content, indent=4))

        # Exit app after dump
        sys.exit(0)

    # Flush the DB: used for easier debug. USE IT WITH CAUTION!
    if bool(args.flush):
        redis_client.flushdb()
        print("\nSuccessfully flushed the Redis DB!\n")

        # Exit app after dump
        sys.exit(0)

    no_of_retries = 3
    while no_of_retries:
        try:
            for db_entry in redis_client.scan_iter():
                '''
                MIGHT BE USEFUL IN THE FUTURE


                db_entry_values = {}
                entry_type = redis_client.type(db_entry)

                if entry_type == 'KV' or entry_type == 'string':
                    db_entry_values = redis_client.get(db_entry)
                if entry_type == 'HGETALL':
                    db_entry_values = redis_client.hgetall(db_entry)
                if entry_type == 'ZRANGE':
                    db_entry_values = redis_client.zrange(db_entry, 0, -1)
                '''

                db_entry_values = redis_client.get(db_entry)
                if not db_entry_values:
                    err_msg_ = "Error when getting values for entry: '{entry}'".format(entry=db_entry)
                    print(err_msg_)
                    task_pu.write_to_disk_file(content=err_msg_, log_file_type='errors')
                    continue

                task_processing_status = task_pu.process_task(value_to_process=db_entry_values)
                if not task_processing_status.code:
                    err_msg = "Error when processing task!\n'{err}'".format(err=task_processing_status.data)
                    print(err_msg)
                    task_pu.write_to_disk_file(content=err_msg, log_file_type='errors')
                    continue

                task_processing_data = task_processing_status.data
                if (
                    task_processing_data.get('action_label') == 'IN_PROGRESS' or
                    task_processing_data.get('action_label') == 'POST_FINISHED_OPS'
                ):
                    continue
                elif task_processing_data.get('action_label') == 'FINISHED':
                    updated_db_entry_values = loads(db_entry_values)

                    updated_db_entry_values['bamboo_state'] = task_processing_data.get('bamboo_status')
                    updated_db_entry_values['post_operation'] = task_processing_data.get('post_operation')
                    updated_db_entry_values['artifacts'] = task_processing_data.get('artifacts')
                    updated_db_entry_values['status'] = 'FINISHED'

                    # Add plan stopped time in DB if action_label == 'FINISHED'
                    build_stop_time = task_processing_data.get('build_stop_time')
                    if build_stop_time:
                        updated_db_entry_values['build_stop_time'] = task_processing_data.get('build_stop_time')

                    # Add to Redis DB
                    redis_client.set(db_entry, dumps(updated_db_entry_values))
                elif task_processing_data.get('action_label') == 'ERASE':
                    if bool(args.verbose):
                        print(task_processing_data.get('data'))

                    # Remove the entry from DB as there is no
                    redis_client.delete(db_entry)
                elif task_processing_data.get('action_label') == 'PLAN_TRIGGERED':
                    updated_db_entry_values = loads(db_entry_values)

                    updated_db_entry_values['bamboo_build_key_api'] = \
                        task_processing_status.data.get('build_plan_url', "")
                    updated_db_entry_values['bamboo_build_result_key'] = task_processing_data.get('build_result_key')
                    updated_db_entry_values['bamboo_state'] = 'STARTED_IN_PROGRESS'
                    updated_db_entry_values['build_start_time'] = task_processing_data.get('build_start_time', 0)
                    updated_db_entry_values['status'] = 'IN_PROGRESS'

                    # E.g: https://bamboo.com/rest/api/latest/result/ABC-XYZ-100
                    parsed_uri = urlparse(task_processing_data.get('build_plan_url', ""))
                    browse_url = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
                    updated_db_entry_values['bamboo_build_url'] = "{url}browse/{key}".format(
                        url=browse_url, key=task_processing_data.get('build_result_key', "")
                    )

                    redis_client.set(db_entry, dumps(updated_db_entry_values))
                else:
                    err_msg = (
                        "Current entry could not be parsed:\n{0}".format(dumps(loads(redis_client.get(db_entry)),
                                                                               indent=4))
                    )
                    print(err_msg)
                    task_pu.write_to_disk_file(content=err_msg, log_file_type='errors')

            # Add a delay of 60 seconds before performing another search
            sleep(60)
        except Exception as err:
            no_of_retries -= 1

            err_msg = "Error when trying to query REDIS DB: '{err}'".format(err=err)
            print(err_msg)
            task_pu.write_to_disk_file(content=err_msg, log_file_type='errors')

            sleep(30)

    sys.exit(0)


####################################################################################################
# Standard boilerplate to call the main() function to begin the program.
# This only runs if the module was *not* imported.
#
if __name__ == '__main__':
    main()
