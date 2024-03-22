# Core concepts

The core component is the `DockerTester` class, that is responsible for creating the
Docker bridge network, creating, starting and stopping containers, keeping track of it
all and tearing it all down at the end of the test run. What it also does is make the
created containers accessible in a convenient way.

Of course, you're not supposed to instantiate this class yourself, you should use the
`dockertester` fixture. This fixture, in turn, relies on the `dockertester_config` and
`docker_image_manager` fixtures. All three can be imported from the
`pytest_docker_network_fixtures` directly. You can - and probably should - provide your
own `dockertester_config` or `docker_image_manager` fixtures to override the default
behaviour of the `DockerTester`. But if you're not overriding them, you need to import
them, because that's how Pytest fixtures are designed to work. So, this would then
result in something like this:

```python

from pytest_docker_network_fixtures import DockerTester

# Fixtures
from pytest_docker_network_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager)


def test_example(dockertester: DockerTester):
    ...

```

It would then be up to you to do some meaningful test using the `DockerTester` instance
provided. Now, this is not your typical use case, as you really need to have some 
re-usable fixtures, and the `dockertester` fixture is just a base building block for 
creating them.
