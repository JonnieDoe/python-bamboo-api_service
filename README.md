# python-bamboo-api
An HTTP(S) REST API layer used to expose Bamboo plans to third parties.

The service is an HTTP REST API layer used to expose Bamboo plans to third parties (e.g Jenkins).
It was written in Python3.7.
It relies on tasks and uses Redis as a database to keep track of tasks states.

The service handles authentication on behalf of the user, thus the user does not need to supply any credentials or tokens.
The service is capable to stop all Bamboo plans it has started and which are now in a hung state.
If the Bamboo plan has artifacts on a particular stage, it can crawl the Bamboo server and return the direct link to the artifact.
