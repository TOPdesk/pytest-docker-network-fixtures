from __future__ import annotations

import time

import pytest

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides
from pytest_docker_network_fixtures.dockertester import (
    DockerStartTimeoutException,
    TestContainerMixin,
)

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures import dockertester

try:
    from pymongo import MongoClient

    class MongoContainer(MongoClient, TestContainerMixin):
        pass

    # noinspection PyShadowingNames
    @pytest.fixture
    def mongodb(dockertester: DockerTester, request):
        environment = get_environment_with_overrides(request, "mongodb")
        internal_port = 27017
        managed_container = dockertester.launch_container(
            "mongo",
            "mongodb",
            image_tag=None,
            environment=environment,
            ports=[internal_port],
            force_pull=True,
        )

        service_name = managed_container.get_service_name()
        base_url = managed_container.base_url_for_container(internal_port, "mongodb")

        def wait_for_mongodb():
            start_time = time.time()
            exception = None

            while time.time() < (start_time + 20):
                # noinspection PyBroadException
                try:
                    client = MongoContainer(base_url)
                    print(
                        f"Service '{service_name}' started in {time.time() - start_time:2.2f} seconds with URL {base_url}"
                    )
                    client.initialize_container_manager(managed_container)
                    return client

                except Exception as e:
                    exception = e

                time.sleep(0.01)

            raise DockerStartTimeoutException(
                f"Timeout starting service '{service_name}', last exception {exception}"
            )

        try:
            yield wait_for_mongodb()

        finally:
            managed_container.dump_logs_to_stdout()
            managed_container.remove_container()


except ImportError:
    pass
    # No MongoDB available


try:
    import psycopg

    class PostgresContainer(str, TestContainerMixin):
        connection: psycopg.Connection | None = None

    # Image used: https://hub.docker.com/_/postgres

    # noinspection PyShadowingNames
    @pytest.fixture
    def postgres(request, dockertester: DockerTester):
        environment = get_environment_with_overrides(
            request,
            "postgres",
            POSTGRES_USER="postgres",
            POSTGRES_PASSWORD="admin",
            POSTGRES_DB="postgres",
        )

        user = environment["POSTGRES_USER"]
        password = environment["POSTGRES_PASSWORD"]
        database = environment["POSTGRES_DB"]

        internal_port = 5432
        managed_container = dockertester.launch_container(
            "postgres",
            "postgres",
            image_tag=None,
            environment=environment,
            ports=[internal_port],
            force_pull=True,
        )

        service_name = managed_container.get_service_name()
        base_url = managed_container.base_url_for_container(
            internal_port, "postgres", user=user, password=password
        )
        connection_string = f"{base_url}/{database}"
        print(connection_string)

        # postgresql://[userspec@][hostspec][/dbname][?paramspec]

        def wait_for_postgres():
            start_time = time.time()
            exception = None

            while time.time() < (start_time + 20):
                # noinspection PyBroadException
                try:
                    client = psycopg.connect(connection_string)
                    print(
                        f"Service '{service_name}' started in {time.time() - start_time:2.2f} seconds with URL {base_url}"
                    )
                    container = PostgresContainer(connection_string)
                    container.connection = client
                    container.initialize_container_manager(managed_container)
                    return container

                except Exception as e:
                    exception = e

                time.sleep(0.01)

            raise DockerStartTimeoutException(
                f"Timeout starting service '{service_name}', last exception {exception}"
            )

        try:
            yield wait_for_postgres()

        finally:
            managed_container.dump_logs_to_stdout()
            managed_container.remove_container()

except ImportError:
    pass
    # No Postgres available
