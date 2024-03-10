from __future__ import annotations

import weakref

import pytest

from pytest_docker_network_fixtures.dockertester import (
    TestContainerMixin,
    ManagedContainer,
)

from pytest_docker_network_fixtures.core_fixtures import (
    DefaultDockerImageManager,
    BaseDockertesterConfig,
)

# Fixtures
from pytest_docker_network_fixtures.core_fixtures import dockertester
from pytest_docker_network_fixtures.databases import mongodb, postgres


class DockerTesterMock:
    # noinspection PyMethodMayBeStatic
    def get_logs(self, container_id: str) -> str:
        return f"the logs from '{container_id}'"


def test_container_mixin():
    test_container = TestContainerMixin()
    with pytest.raises(Exception):
        _ = test_container.managed_container

    docker_tester = DockerTesterMock()
    container_id = "xxxxxxxxxxxxxxxx"

    managed_container = ManagedContainer(weakref.ref(docker_tester), container_id)
    assert managed_container.docker_tester is docker_tester

    test_container.initialize_container_manager(managed_container)

    assert test_container.managed_container is managed_container
    assert test_container.docker_tester is docker_tester
    assert test_container.container_id == container_id

    assert test_container.get_logs() == f"the logs from '{container_id}'"


@pytest.fixture(scope="session")
def docker_image_manager():
    class MyDockerImageManager(DefaultDockerImageManager):
        def get_docker_registry(self) -> str | None:
            return "my-registry"

    yield MyDockerImageManager()


@pytest.fixture(scope="session")
def dockertester_config():
    class TestDockertesterConfig(BaseDockertesterConfig):
        virtual_domain = "mydomain.loc"

    yield TestDockertesterConfig()


def test_fixture_override(dockertester):
    assert dockertester.image_manager.get_docker_registry() == "my-registry"
    assert dockertester._virtual_domain == "mydomain.loc"


def get_environment_override(request, service: str):
    marker = request.node.get_closest_marker(f"environment_{service}")
    if marker is None:
        return {}
    else:
        return marker.kwargs


@pytest.fixture
def my_service(request):
    env = {"CI": "false"}
    env.update(get_environment_override(request, "my_service"))
    yield env


@pytest.mark.environment_my_service(CI="true")
def test_fixt(my_service):
    assert my_service == {"CI": "true"}


def test_fixt2(my_service):
    assert my_service == {"CI": "false"}
