#!/usr/bin/python -tt
# -*- coding: utf-8 -*-


"""Bamboo API Module."""


import base64
import json
import os
import requests
import sys

from bs4 import BeautifulSoup

# Add custom libs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.default import BAMBOO_PASS, BAMBOO_USER


class BambooAccount:
    """Bamboo Account."""

    def __init__(self):
        self.__username, self.__password = self.__load_credentials()

    @property
    def username(self):
        """Get the username."""
        return self.__username

    @property
    def password(self):
        """Get the password."""
        return self.__password

    @staticmethod
    def __load_credentials():
        return BAMBOO_USER, base64.b64decode(BAMBOO_PASS)


class BambooAPI:
    """Bamboo API related tasks."""

    def __init__(self, verbose=False, bamboo_server=None):
        self.__account = BambooAccount()

        self.__trigger_plan_url_mask = r'https://{bamboo_server_name}/rest/api/latest/queue/'
        self.__stop_plan_url_mask = r'https://{bamboo_server_name}/build/admin/stopPlan.action'
        self.__plan_results_url_mask = r'https://{bamboo_server_name}/rest/api/latest/result/'
        self.__query_plan_url_mask = r'https://{bamboo_server_name}/rest/api/latest/plan/'
        self.__latest_queue_url_mask = r'https://{bamboo_server_name}/rest/api/latest/queue.json'
        self.__artifact_url_mask = \
            r'https://{bamboo_server_name}.sw.nxp.com/browse/{plan_key}/artifact/{job_name}/{artifact_name}/'

        self.__bamboo_server = bamboo_server
        self.__plan_key = None
        self.__job_name = None
        self.__artifact_name = None
        self.__url_extra_values = ''
        self.__verbose = verbose

        self.__headers = {
            "Connection": "Keep-Alive",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "User-Agent": "Garbage browser: 5.6"
        }

    @property
    def account(self):
        """Get account object."""
        return self.__account

    @property
    def artifact_name(self):
        """Get artifact name."""
        return self.__artifact_name

    @artifact_name.setter
    def artifact_name(self, artifact_name_value):
        self.__artifact_name = artifact_name_value

    @property
    def bamboo_server(self):
        """Get Bamboo server name."""
        return self.__bamboo_server

    @bamboo_server.setter
    def bamboo_server(self, bamboo_server_value):
        self.__bamboo_server = bamboo_server_value

    @property
    def plan_key(self):
        """Get Bamboo plan key."""
        return self.__plan_key

    @plan_key.setter
    def plan_key(self, plan_key_value):
        self.__plan_key = plan_key_value

    @property
    def job_name(self):
        """Get Bamboo plan stage job name."""
        return self.__job_name

    @job_name.setter
    def job_name(self, job_name_value):
        self.__job_name = job_name_value

    @property
    def url_extra_values(self):
        """Get extra values to compound the url."""
        return self.__url_extra_values

    @url_extra_values.setter
    def url_extra_values(self, extra_values):
        self.__url_extra_values = extra_values

    @property
    def trigger_plan_url_mask(self):
        """Get the url mask to trigger builds."""
        return self.__trigger_plan_url_mask

    @property
    def stop_plan_url_mask(self):
        """Get the url mask to stop the current running plan."""
        return self.__stop_plan_url_mask

    @property
    def plan_results_url_mask(self):
        """Get plan results url mask."""
        return self.__plan_results_url_mask

    @property
    def query_plan_url_mask(self):
        """Get the query url mask."""
        return self.__query_plan_url_mask

    @property
    def latest_queue_url_mask(self):
        """Get latest queue url mask."""
        return self.__latest_queue_url_mask

    @property
    def artifact_url_mask(self):
        """Get artifact url mask."""
        return self.__artifact_url_mask

    @property
    def headers(self):
        """Compound the headers for HTTP request."""
        return self.__headers

    @property
    def verbose(self):
        """Get verbose."""
        return self.__verbose

    @verbose.setter
    def verbose(self, value):
        self.__verbose = value

    ###########################################################################################
    @staticmethod
    def pack_response_to_client(**values_to_pack):
        """Pack the response to user.
        :param values_to_pack: Values to pack in response dict
        """

        response = dict()
        for key, value in values_to_pack:
            response[key] = value

        return response

    ###########################################################################################
    def compound_url(self, query_type=None):
        """Compound the URL.
        :param query_type: Type of the query (e.g.: <plan_info/plan_status/stop_plan/query_results>) [string]
        :return: URL
        """

        if not query_type:
            raise ValueError("No query type supplied!")

        if query_type == 'plan_status':
            url = "{url}{plan_key}.json{opt}".format(
                url=self.query_plan_url_mask.format(self.bamboo_server),
                plan_key=self.plan_key,
                opt="?includeAllStates=true"
            )
        elif query_type == 'plan_info':
            url = "{url}{plan_key}.json{opt}".format(
                url=self.plan_results_url_mask.format(self.bamboo_server),
                plan_key=self.plan_key,
                opt="?max-results=10000"
            )
        elif query_type == 'stop_plan':
            url = "{url}?planResultKey={plan_key}".format(
                url=self.stop_plan_url_mask.format(self.bamboo_server),
                plan_key=self.plan_key
            )
        elif query_type == 'query_queue':
            url = "{url}{opt}".format(
                url=self.latest_queue_url_mask.format(self.bamboo_server),
                opt="?expand=queuedBuilds"
            )
        elif query_type in ['download_artifact', 'query_for_artifacts']:
            url = (
                "{url}{opt}".format(
                    url=self.artifact_url_mask.format(
                        self.bamboo_server, self.plan_key, self.job_name, self.artifact_name
                    ),
                    opt=self.url_extra_values)
            )
        else:
            raise ValueError("Query type not supported!")

        return url

    ###########################################################################################
    def trigger_plan_build(self, bamboo_server=None, plan_key=None, req_values=None):
        """Trigger a build using Bamboo API.
        :param bamboo_server: Bamboo server used in API call [string]
        :param plan_key: Bamboo plan key [string]
        :param req_values: Values to insert into request (tuple)
        :return: A dictionary containing HTTP status_code and request content
        :raise: Exception, ValueError on Errors
        """

        if not bamboo_server and not self.bamboo_server:
            return {'content': "No Bamboo server supplied!"}

        if not plan_key:
            return {'content': "Incorrect input provided!"}

        # Execute all stages by default if no options received
        request_payload = {'stage&executeAllStages': [True]}
        if req_values:
            # req_values[0] = True/False
            request_payload['stage&executeAllStages'] = [req_values[0]]

            # Example
            # req_value[1] = {'bamboo.driver': "xyz", bamboo.test': "xyz_1"}
            # API supports a list as values
            for key, value in req_values[1].items():
                # Use custom revision when triggering build
                if key.lower() == 'custom.revision':
                    request_payload["bamboo.customRevision"] = [value]
                    continue

                request_payload["bamboo.{key}".format(key=key)] = [value]

        url = "{url}{plan_key}.json".format(url=self.trigger_plan_url_mask.format(bamboo_server), plan_key=plan_key)
        if self.verbose:
            print("URL used to trigger build: '{url}'".format(url=url))
        try:
            response = requests.request('POST',
                                        url=url,
                                        auth=requests.auth.HTTPBasicAuth(self.account.username, self.account.password),
                                        headers=self.headers,
                                        data=json.dumps(request_payload),
                                        timeout=30,
                                        allow_redirects=False)
        except (requests.RequestException, requests.ConnectionError, requests.HTTPError,
                requests.ConnectTimeout, requests.Timeout) as err:
            raise ValueError(
                "Error when requesting URL: '{url}'{line_sep}{err}".format(url=url, line_sep=os.linesep, err=err)
            )
        except Exception as err:
            raise Exception(
                "Unknown error when requesting URL: '{url}'{line_sep}{err}".format(
                    url=url, line_sep=os.linesep, err=err
                )
            )

        # Check HTTP response code
        if response.status_code != 200:
            return self.pack_response_to_client(
                response=False, status_code=response.status_code, content=response.json(), url=url
            )

        try:
            # Get the JSON reply from the web page
            response.encoding = "utf-8"
            response_json = response.json()
        except ValueError as err:
            raise ValueError("Error decoding JSON: {err}".format(err=err))
        except Exception as err:
            raise Exception("Unknown error: {err}".format(err=err))

        # Send response to client
        return self.pack_response_to_client(
            response=True, status_code=response.status_code, content=response_json, url=url
        )

    ###########################################################################################
    def query_plan(self, bamboo_server=None, plan_key=None, query_type=None):
        """Query a plan build using Bamboo API.
        :param bamboo_server: Bamboo server used in API call [string]
        :param plan_key: Bamboo plan key [string]
        :param query_type: Type of the query (e.g.: <plan_info/plan_status/stop_plan/query_results>) [string]
        :return: A dictionary containing HTTP status_code and request content
        :raise: Exception, ValueError on errors
        """

        if not bamboo_server and not self.bamboo_server:
            return {'content': "No Bamboo server supplied!"}

        if not plan_key or not query_type:
            return {'content': "Incorrect input provided!"}

        self.bamboo_server = bamboo_server
        self.plan_key = plan_key

        url = self.compound_url(query_type)
        if self.verbose:
            print("URL used in query: '{url}'".format(url=url))

        try:
            response = requests.request('GET',
                                        url=url,
                                        auth=requests.auth.HTTPBasicAuth(self.account.username, self.account.password),
                                        headers=self.headers,
                                        timeout=30,
                                        allow_redirects=False)
        except (requests.RequestException, requests.ConnectionError, requests.HTTPError,
                requests.ConnectTimeout, requests.Timeout) as err:
            raise ValueError(
                "Error when requesting URL: '{url}'{line_sep}{err}".format(url=url, line_sep=os.linesep, err=err)
            )
        except Exception as err:
            raise Exception(
                "Unknown error when requesting URL: '{url}'{line_sep}{err}".format(
                    url=url, line_sep=os.linesep, err=err
                )
            )

        # Check HTTP response code
        if response.status_code != 200:
            return self.pack_response_to_client(
                response=False, status_code=response.status_code, content=response.json(), url=url
            )

        try:
            # Get the JSON reply from the web page
            response.encoding = "utf-8"
            response_json = response.json()
        except ValueError as err:
            raise ValueError("Error decoding JSON: {err}".format(err=err))
        except Exception as err:
            raise Exception("Unknown error: {err}".format(err=err))

        # Send response to client
        return self.pack_response_to_client(
            response=True, status_code=response.status_code, content=response_json, url=url
        )

    ###########################################################################################
    def query_job_for_artifacts(self, bamboo_server=None, plan_key=None, query_type=None, job_name=None,
                                artifact_names=None, url_extra_values=None):
        """Query Bamboo plan run for stage artifacts.
        :param bamboo_server: Bamboo server used in API call [string]
        :param plan_key: Bamboo plan key [string]
        :param query_type: Type of the query (e.g.: <plan_info/plan_status/stop_plan/download_artifact>) [string]
        :param job_name: Bamboo plan job name [string]
        :param artifact_names: Names of the artifacts as in Bamboo plan stage job [tuple]
        :param url_extra_values: Extra values to compound the URL [string]
        :return: A dictionary containing HTTP status_code, request content and list of artifacts
        :raise: Exception, ValueError on Errors
        """

        if not bamboo_server and not self.bamboo_server:
            return {'content': "No Bamboo server supplied!"}

        if not plan_key or not query_type or not job_name or not artifact_names:
            return {'content': "Incorrect input provided!"}

        self.bamboo_server = bamboo_server
        self.plan_key = plan_key
        self.job_name = job_name

        if url_extra_values:
            self.url_extra_values = url_extra_values

        # Lists of artifacts to return
        artifacts = list()
        artifacts_links = list()

        http_failed_conn_counter = 0
        for artifact in artifact_names:
            self.artifact_name = artifact
            url = self.compound_url(query_type)

            if self.verbose:
                print("URL used to query for artifacts: '{url}'".format(url=url))

            try:
                response = requests.request('GET',
                                            url=url,
                                            auth=requests.auth.HTTPBasicAuth(self.account.username,
                                                                             self.account.password),
                                            headers=self.headers,
                                            timeout=60,
                                            allow_redirects=True)
            except (requests.RequestException, requests.ConnectionError, requests.HTTPError,
                    requests.ConnectTimeout, requests.Timeout) as err:
                raise ValueError(
                    "Error when requesting URL: '{url}'{line_sep}{err}".format(url=url, line_sep=os.linesep, err=err)
                )
            except Exception as err:
                raise Exception(
                    "Unknown error when requesting URL: '{url}'{line_sep}{err}".format(
                        url=url, line_sep=os.linesep, err=err
                    )
                )

            # Check HTTP response code
            if response.status_code != 200:
                http_failed_conn_counter += 1
                continue

            try:
                # page = requests.get(url).text  <-- Works if Bamboo plan does not require AUTH
                soup = BeautifulSoup(response.text, 'html.parser')
                # All "<a href></a>" elements
                a_html_elements = (soup.find_all('a'))

                for html_elem in a_html_elements:
                    # File name, as href tag value
                    file_name = html_elem.extract().get_text()

                    # Do not add HREF value in case PAGE NOT FOUND error
                    if file_name != "Site homepage":
                        artifacts.append(file_name)
                        artifacts_links.append("{url}{resource}".format(url=url, resource=file_name))

                    # TODO: add support to download artifacts from sub-dirs as well
            except ValueError as err:
                raise ValueError("Error when downloading artifact: {err}".format(err=err))
            except Exception as err:
                raise Exception("Unknown error when downloading artifact: {err}".format(err=err))

        http_return_code = 200
        if http_failed_conn_counter == len(artifact_names):
            http_return_code = 444

        response_to_client = self.pack_response_to_client(
            response=True, status_code=http_return_code, content=None, url=None
        )
        response_to_client['artifacts'] = artifacts
        response_to_client['artifacts_links'] = artifacts_links
        # Send response to client
        return response_to_client

    ###########################################################################################
    def get_artifact(self, bamboo_server=None, plan_key=None, query_type=None, job_name=None, artifact_name=None,
                     url_extra_values=None, destination_file=None):
        """Download artifacts from Bamboo plan.
        :param bamboo_server: Bamboo server used in API call [string]
        :param plan_key: Bamboo plan key [string]
        :param query_type: Type of the query (e.g.: <plan_info/plan_status/stop_plan/download_artifact>) [string]
        :param job_name: Bamboo plan job name [string]
        :param artifact_name: Name of the artifact as in Bamboo plan stage job [string]
        :param url_extra_values: Extra values to compound the URL [string]
        :param destination_file: Full path to destination file [string]
        :return: A dictionary containing HTTP status_code and request content
        :raise: Exception, ValueError on Errors
        """

        if not bamboo_server and not self.bamboo_server:
            return {'content': "No Bamboo server supplied!"}

        if not plan_key or not query_type or not job_name or not artifact_name or not destination_file:
            return {'content': "Incorrect input provided!"}

        self.bamboo_server = bamboo_server
        self.plan_key = plan_key
        self.job_name = job_name
        self.artifact_name = artifact_name

        if url_extra_values:
            self.url_extra_values = url_extra_values

        url = self.compound_url(query_type)

        if self.verbose:
            print("URL used to download artifact: '{url}'".format(url=url))

        try:
            response = requests.request('GET',
                                        url=url,
                                        auth=requests.auth.HTTPBasicAuth(self.account.username, self.account.password),
                                        headers=self.headers,
                                        timeout=60,
                                        allow_redirects=False)
        except (requests.RequestException, requests.ConnectionError, requests.HTTPError,
                requests.ConnectTimeout, requests.Timeout) as err:
            raise ValueError(
                "Error when requesting URL: '{url}'{line_sep}{err}".format(url=url, line_sep=os.linesep, err=err)
            )
        except Exception as err:
            raise Exception(
                "Unknown error when requesting URL: '{url}'{line_sep}{err}".format(
                    url=url, line_sep=os.linesep, err=err
                )
            )

        # Check HTTP response code
        if response.status_code != 200:
            return self.pack_response_to_client(
                response=False, status_code=response.status_code, content=response.json(), url=url
            )

        try:
            get_file = requests.get(url)

            with open(destination_file, 'wb') as f:
                f.write(get_file.content)
        except ValueError as err:
            raise ValueError("Error when downloading artifact: {err}".format(err=err))
        except Exception as err:
            raise Exception("Unknown error when downloading artifact: {err}".format(err=err))

        # Send response to client
        return self.pack_response_to_client(
            response=True, status_code=response.status_code, content=None, url=url
        )

    ###########################################################################################
    def stop_build(self, bamboo_server=None, plan_key=None, query_type=None):
        """Stop a running plan from Bamboo using Bamboo API.
        :param bamboo_server: Bamboo server used in API call [string]
        :param plan_key: Bamboo plan key [string]
        :param query_type: Type of the query (e.g.: <plan_info/plan_status/stop_plan/query_results>) [string]
        :return: A dictionary containing HTTP status_code and request content
        :raise: Exception, ValueError on errors
        """

        if not bamboo_server and not self.bamboo_server:
            return {'content': "No Bamboo server supplied!"}

        if not plan_key:
            return {'content': "No Bamboo plan key provided!"}

        self.bamboo_server = bamboo_server
        self.plan_key = plan_key

        url = self.compound_url(query_type)

        if self.verbose:
            print("URL used to stop plan: '{url}'".format(url=url))

        try:
            response = requests.request('POST',
                                        url=url,
                                        auth=requests.auth.HTTPBasicAuth(self.account.username, self.account.password),
                                        headers=self.headers,
                                        timeout=30,
                                        allow_redirects=True)
        except (requests.RequestException, requests.ConnectionError, requests.HTTPError,
                requests.ConnectTimeout, requests.Timeout) as err:
            raise ValueError(
                "Error when requesting URL: '{url}'{line_sep}{err}".format(url=url, line_sep=os.linesep, err=err)
            )
        except Exception as err:
            raise Exception(
                "Unknown error when requesting URL: '{url}'{line_sep}{err}".format(
                    url=url, line_sep=os.linesep, err=err
                )
            )

        # Check HTTP response code
        if response.status_code != 200:
            return self.pack_response_to_client(
                response=False, status_code=response.status_code, content=response.json(), url=url
            )

        # Send response to client
        try:
            response.encoding = "utf-8"
            response_json = response.json()
        except Exception as err:
            if self.verbose:
                print("Unknown error when setting encoding to 'utf-8': {err}".format(err=err))

            response_json = ""

        return self.pack_response_to_client(
            response=True, status_code=response.status_code, content=response_json, url=url
        )
