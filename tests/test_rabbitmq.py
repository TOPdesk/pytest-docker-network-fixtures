# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.rabbitmq import rabbitmq


def test_rabbitmq(rabbitmq):
    rabbitmq.basic_publish("some.key", "some message")
