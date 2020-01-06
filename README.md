<h1 align="center">
<img width="400" src="https://www.python.org/static/community_logos/python-logo-inkscape.svg" alt="Python">
<br>
</h1>


>  # _python-bamboo-api_
- [INFO](#info)
- [REQS](#Requirements)



## INFO
An HTTP(S) REST API layer used to expose Bamboo plans to third parties.

The service is an HTTP REST API layer used to expose Bamboo plans to third parties (e.g Jenkins).
It was written in Python3.8.
It relies on tasks and uses Redis as a database to keep track of tasks states.

The service handles authentication on behalf of the user, thus the user does not need to supply any
credentials or tokens.
The service is capable to stop all Bamboo plans it has started and which are now in a hung state.
If the Bamboo plan has artifacts on a particular stage, it can crawl the Bamboo server and return the direct
link to the artifact.


## Requirements

- It will run on Python3.7 also.
- For development I have used [Pycharm CE](https://www.jetbrains.com/pycharm/),
[Pyenv](https://github.com/pyenv/pyenv) and
[Pipenv](https://pipenv-fork.readthedocs.io/en/latest/).
