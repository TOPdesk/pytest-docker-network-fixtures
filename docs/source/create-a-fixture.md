# Create a fixture

In this tutorial we start with an existing Docker image and create a fixture out of it.
This might be an image that comes from Dockerhub, or some other public registry, or a 
private registry, or just a local one: while there are some differences, the general 
way of creating a fixture is the same.

We start with creating a fixture that in turn depends on _at least_ the `dockertester` 
fixture. Note that that fixture in turn depends on two others, called 
`dockertester_config`, and `docker_image_manager`, so be sure to import them. Why we 
need three imports instead of just the one is explained HERE.

```{todo}
Link to explanation
```

Of course, we use type annotations ro make our life easier, so that's another import. 
After that, we just need to make a `pytest` fixture to start things off:

```python
import pytest

from pytest_docker_network_fixtures import DockerTester

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)


@pytest.fixture
def server(dockertester: DockerTester):
    yield "WHAT????"
```

Now we actually must _do_ something with the `dockertester` object to spin up a Docker 
container, and we also want to tear down the container after use. So let's add that:

```python
@pytest.fixture
def server(dockertester: DockerTester):
    internal_port = 9187
    managed_container = dockertester.launch_container(
        "bitnami/postgres-exporter",
        "postgres-exporter",
        ports=[internal_port],
        force_pull=True,
    )
    yield managed_container
    
    managed_container.dump_logs_to_stdout()
    managed_container.remove_container()
    
```

This works, and a `ManagedContainer` is definitely a useful fixture to have, but it's 
not as convenient as it could be. Also, the container may have started, but how do we 
know it's ready?