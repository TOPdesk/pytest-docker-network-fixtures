# Fake services

Ideally, of course, you wouldn't even need fake services, because nothing beats the 
real thing when it comes to integration testing, but in practice there might be any 
number of reasons this wouldn't work:

- You need to test against a 3rd party API
- The real service is either
  - Not available in a Docker container
  - Resource hungry
  - Too slow to start
  - Dependent on other services (where does the recursion stop?)
  - Not flexible enough to force testable corner cases
  - ...

But, depending on how elaborate your fake service needs to emulate the real thing, it 
might prove to be relatively easy to build one. So here we go:

## The fake service code

It's up to you how you want to build this, but for this example we're creating a 
minimal [Flask](https://flask.palletsprojects.com/en/3.0.x/) server. 

Start by creating a separate directory for your code, like `service`

Add a file called `server.py`:

```python
from flask import Flask

app = Flask(__name__)


@app.route('/test')
def test():
    return 'Hello World!'


if __name__ == '__main__':
    app.run("0.0.0.0", 8080, debug=True)
```

Also, create a `requirements.txt` like this:

```
flask==3.0.2
```

## Building a Docker image

Now we create the `Dockerfile`:

```dockerfile
FROM python:3.12-alpine

WORKDIR /opt/server
COPY ["server.py", "requirements.txt", "/opt/server/"]
RUN pip install -r requirements.txt
EXPOSE 8080
ENTRYPOINT ["python", "-u", "server.py"]
```

Our `server` directory should look like this, now:

```
server
   +--- server.py
   +--- requirements.txt
   +--- Dockerfile
```

We can now ask Docker to build the image like this:

```shell
docker build -t tutorial-server:main-snapshot . --platform=linux/amd64
```

## Creating the fixture

You now have a local Docker image on your machine. Let's make a fixture out of this:

```python
import pytest

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.container_waiters import wait_for_web_service
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides
from pytest_docker_network_fixtures.docker_services import UrlRequester

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_image_manager,
)


@pytest.fixture
def server(request, dockertester: DockerTester):
    environment = get_environment_with_overrides(request, "server")
    internal_port = 8080
    managed_container = dockertester.launch_container(
        "tutorial-server",
        "server",
        image_tag="main-snapshot",
        environment=environment,
        ports=[internal_port],
        force_pull=False,
    )

    try:
        yield wait_for_web_service(
            managed_container, UrlRequester, internal_port, "test"
        )

    finally:
        managed_container.dump_logs_to_stdout()
        managed_container.remove_container()


def test_run(server):
    print(server.get("test").text)
```

Included in here is the `test_run` test, so it's easy to validate if things are 
working. The fixture itself is about 25 lines of admittedly boilerplate-heavy code, 
ignoring the imports.

But what did we achieve?

- There's a service called `server` available in the Docker network, running on
  port 8080. It can be reached under this name and port from withing the Docker network, 
  i.e. http://server:8080 can be used by other services.

- The fixture will give you a convenient way to connect to that service from the 
  outside, that is: your test code. Exactly what ip:port combination will be used 
  depends on a few factors, but it should just work. In the above example a 
  `UrlRequester` is returned, which is a convenience class to do http-requests to the 
  service.

- The fixture will be torn down after the test, and its log will be dumped to stdout. 
  In case of test errors that makes it a lot easier to debug the problem





