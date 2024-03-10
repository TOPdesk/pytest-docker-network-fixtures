from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

import pytest

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.dockertester import DockerImageManager


class DefaultDockerImageManager(DockerImageManager):
    def get_docker_registry(self) -> str | None:
        return os.getenv("DOCKER_REGISTRY")

    def get_image(self, image: str, extend_image_name):
        if not extend_image_name or self.get_docker_registry() is None:
            return image

        return f"{self.get_docker_registry()}/{image}"

    def get_image_tag(self, image_tag: str, change_image_tag: bool) -> str:
        if not change_image_tag:
            return image_tag

        ci_commit_ref_name = os.getenv("CI_COMMIT_REF_NAME", None)
        if ci_commit_ref_name == "master" or ci_commit_ref_name == "main":
            commit_short_sha = os.getenv("CI_COMMIT_SHORT_SHA", None)
            return commit_short_sha if commit_short_sha else image_tag
        else:
            ci_commit_ref_no_underscores = os.getenv(
                "CI_COMMIT_REF_NO_UNDERSCORES", None
            )
            return (
                f"{ci_commit_ref_no_underscores}-snapshot"
                if ci_commit_ref_no_underscores
                else image_tag
            )


@pytest.fixture(scope="session")
def docker_image_manager():
    yield DefaultDockerImageManager()


@dataclass(frozen=True)
class BaseDockertesterConfig:
    basename: str = "dockertester-test"
    virtual_domain = "test.loc"


@pytest.fixture(scope="session")
def dockertester_config():
    yield BaseDockertesterConfig()


@pytest.fixture(scope="session")
def dockertester(
        dockertester_config: BaseDockertesterConfig, docker_image_manager: DockerImageManager
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


def get_environment_with_overrides(request, service: str, **kwargs: Dict[str, str]) -> Dict[str, str]:
    """A utility function to return environment variables to be inserted into the docker
    container. If a `@pytest.mark.environment_<fixture name>` added to the test,
    these additions will override the keyword arguments passed to this function, allowing
    for a per-test configuration of the container fixture."""

    result = kwargs.copy()
    marker = request.node.get_closest_marker(f"environment_{service}")

    if marker is not None:
        result.update(marker)

    return result
