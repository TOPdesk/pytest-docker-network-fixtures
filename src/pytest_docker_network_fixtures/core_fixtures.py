from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

import pytest

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.images import (
    DockerImageManager,
    DockerRegistry,
    PUBLIC_DOCKER_REGISTRY_NAME,
    BUILD_DOCKER_REGISTRY_NAME,
)


@pytest.fixture(scope="session")
def docker_image_manager():
    manager = DockerImageManager()
    manager.add_registry(
        DockerRegistry(PUBLIC_DOCKER_REGISTRY_NAME, "docker.io", "latest")
    )
    manager.add_registry(
        DockerRegistry(BUILD_DOCKER_REGISTRY_NAME, "my-registry.loc")
    )  # This is an example
    yield manager


@dataclass(frozen=True)
class BaseDockertesterConfig:
    basename: str = "dockertester-test"
    virtual_domain = "test.loc"


@pytest.fixture(scope="session")
def dockertester_config():
    yield BaseDockertesterConfig()


@pytest.fixture(scope="session")
def dockertester(
    dockertester_config: BaseDockertesterConfig,
    docker_image_manager: DockerImageManager,
):
    print("Instantiating DockerTester")
    docker_host = os.getenv("DOCKERTESTHOST", "localhost")
    docker_version = os.getenv("DOCKERTESTVERSION", None)
    client = DockerTester(
        docker_image_manager,
        dockertester_config.basename,
        docker_host,
        virtual_domain=dockertester_config.virtual_domain,
        version=docker_version,
    )

    username = os.getenv("DOCKERLOGINUSER", None)
    registry = os.getenv("DOCKERREGISTRY", None)

    if username is not None:
        password = os.getenv("DOCKERLOGINPASS", None)
        if password is None:
            raise Exception("Can't login without password")
        client.login(username, password, registry)
        client.update_images = True

    try:
        yield client

    finally:
        client.remove_all()


def get_environment_with_overrides(
    request, service: str, **kwargs: str
) -> Dict[str, str]:
    """A utility function to return environment variables to be inserted into the docker
    container. If a `@pytest.mark.environment_<fixture name>` added to the test,
    these additions will override the keyword arguments passed to this function, allowing
    for a per-test configuration of the container fixture."""

    result = kwargs.copy()
    marker = request.node.get_closest_marker(f"environment_{service}")

    if marker is not None:
        result.update(marker)

    return result
