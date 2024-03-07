from __future__ import annotations

import time
from typing import Callable

import requests

from pytest_docker_network_fixtures import (
    DockerStartTimeoutException,
    TestContainerMixin,
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


try:
    import pymssql

    class MssqlTestContainer(TestContainerMixin):
        def __init__(self, server: str, port: int, user: str, password: str):
            self.server = server
            self.port = port
            self.user = user
            self.password = password

    def wait_for_mssql_available(
        managed_container: ManagedContainer, internal_port, user, password
    ):
        host, port = managed_container.get_connectable_host_and_port(internal_port)

        service_name = managed_container.get_service_name()

        start_time = time.time()
        conn = None
        exception = ""

        # added for GK-727: the pymssql.connect hangs indefinitely if done too early
        time.sleep(10)

        while time.time() < (start_time + 40):
            # noinspection PyBroadException
            try:
                conn = pymssql.connect(
                    server=host,
                    port=port,
                    user=user,
                    password=password,
                    database="master",
                )
                with conn.cursor(as_dict=False) as cursor:
                    cursor.execute("SELECT 1;")
                    print(
                        f"Database came online in {time.time() - start_time:2.2f} seconds"
                    )

                manager = MssqlTestContainer(host, port, user, password)
                manager.initialize_container_manager(managed_container)
                return manager

            except Exception as exc:
                exception = str(exc)

            finally:
                if conn is not None:
                    conn.close()
                conn = None

            time.sleep(0.7)

        raise DockerStartTimeoutException(
            "Timeout starting service '{}: {}'".format(service_name, exception)
        )

except ImportError:
    pass
