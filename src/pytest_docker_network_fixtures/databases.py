import time
from typing import Callable

import pytest

from pytest_docker_network_fixtures import DockerTester

# Fixtures
from pytest_docker_network_fixtures import dockertester
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides
from pytest_docker_network_fixtures.dockertester import ManagedContainer, DockerStartTimeoutException, \
    TestContainerMixin

try:
    from pymongo import MongoClient


    class MongoContainer(MongoClient, TestContainerMixin):
        pass


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
            while time.time() < (start_time + 20):
                # noinspection PyBroadException
                try:
                    client = MongoContainer(base_url)
                    print(
                        f"Service '{service_name}' started in {time.time() - start_time:2.2f} seconds with URL {base_url}"
                    )
                    client.initialize_container_manager(managed_container)
                    return client

                except Exception:
                    pass

                time.sleep(0.01)

            raise DockerStartTimeoutException(
                "Timeout starting service '{}'".format(service_name)
            )

        try:
            yield wait_for_mongodb()

        finally:
            managed_container.dump_logs_to_stdout()
            managed_container.remove_container()


except ImportError:
    pass
