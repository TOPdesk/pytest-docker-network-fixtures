from __future__ import annotations

import time
from typing import Callable

import requests

from pytest_docker_network_fixtures import (
    DockerStartTimeoutException,
)
from pytest_docker_network_fixtures.docker_services import UrlRequester
from pytest_docker_network_fixtures.dockertester import ManagedContainer


def wait_for_web_service(
    managed_container: ManagedContainer,
    builder: Callable[[str], UrlRequester],
    internal_port: int,
    endpoint: str | None = None,
):
    service_name = managed_container.get_service_name()

    base_url = managed_container.base_url_for_container(internal_port)
    test_url = f"{base_url}/{endpoint}" if endpoint else base_url
    start_time = time.time()
    while time.time() < (start_time + 20):
        # noinspection PyBroadException
        try:
            requests.get(test_url)
            print(
                f"Service '{service_name}' started in {time.time() - start_time:2.2f} seconds with URL {test_url}"
            )
            result: UrlRequester = builder(base_url)
            result.initialize_container_manager(managed_container)
            return result

        except Exception:
            pass

        time.sleep(0.01)

    raise DockerStartTimeoutException(
        "Timeout starting service '{}'".format(service_name)
    )
