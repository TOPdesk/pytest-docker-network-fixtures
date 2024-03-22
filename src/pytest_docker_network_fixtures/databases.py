from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides
from pytest_docker_network_fixtures.dockertester import (
    DockerStartTimeoutException,
    TestContainerMixin,
    ManagedContainer,
)
from pytest_docker_network_fixtures.images import docker_image

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
            dockertester.registry_manager.public.image("mongo"),
            "mongodb",
            environment=environment,
            ports=[internal_port],
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
            dockertester.registry_manager.public.image("postgres"),
            "postgres",
            environment=environment,
            ports=[internal_port],
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


try:
    import pymssql

    @dataclass
    class MssqlTestContainer(TestContainerMixin):
        host: str
        port: int
        user: str
        password: str

        def connect(self, database: str = "tempdb"):
            return pymssql.connect(
                server=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=database,
            )

    def _wait_for_mssql_available(
        managed_container: ManagedContainer, internal_port, user, password
    ):
        host, port = managed_container.get_connectable_host_and_port(internal_port)

        service_name = managed_container.get_service_name()

        manager = MssqlTestContainer(host, port, user, password)
        manager.initialize_container_manager(managed_container)

        start_time = time.time()
        conn = None
        exception = None

        # TODO inspect logs before trying to connect?

        while time.time() < (start_time + 40):
            # noinspection PyBroadException
            try:
                conn = manager.connect()
                with conn.cursor(as_dict=False) as cursor:
                    cursor.execute("SELECT 1;")
                    print(
                        f"Database came online in {time.time() - start_time:2.2f} seconds"
                    )

                return manager

            except Exception as exc:
                exception = exc

            finally:
                if conn is not None:
                    conn.close()
                conn = None

            time.sleep(0.7)

        raise DockerStartTimeoutException(
            f"Timeout starting service '{service_name}': last exception {exception}"
        )

    # noinspection PyShadowingNames
    @pytest.fixture
    def mssql_2019(request, dockertester: DockerTester):
        environment = get_environment_with_overrides(
            request,
            "mssql-2019",
            ACCEPT_EULA="Y",
            MSSQL_SA_PASSWORD="yourStrong(!)Password",
            MSSQL_PID="Developer",
        )

        user = "sa"
        password = environment["MSSQL_SA_PASSWORD"]

        internal_port = 1433
        managed_container = dockertester.launch_container(
            docker_image("mcr.microsoft.com/mssql/server:2019-latest"),
            "sql-server-2019",
            environment=environment,
            ports=[internal_port],
        )

        try:
            yield _wait_for_mssql_available(
                managed_container, internal_port, user, password
            )

        finally:
            managed_container.dump_logs_to_stdout(suppress_empty_lines=True)
            managed_container.remove_container()

except ImportError:
    pass
