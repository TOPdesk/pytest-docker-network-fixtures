import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
import yaml

from pytest_docker_network_fixtures import DockerTester
from pytest_docker_network_fixtures.container_waiters import wait_for_web_service
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides
from pytest_docker_network_fixtures.docker_services import UrlRequester

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.dockertester import (
    DockerStartTimeoutException,
    TestContainerMixin,
    ManagedContainer,
)


@dataclass
class ScrapeTarget:
    job_name: str
    static_configs: List[str]

    def as_dict(self):
        return {
            "job_name": self.job_name,
            "static_configs": [{"targets": self.static_configs}],
        }


@dataclass
class ScrapeConfig:
    scrape_targets: List[ScrapeTarget]
    scrape_interval: str = "15s"

    def as_dict(self):
        return {
            "global": {
                "scrape_interval": self.scrape_interval,
            },
            "scrape_configs": [st.as_dict() for st in self.scrape_targets],
        }


@pytest.fixture
def scrape_config():
    yield ScrapeConfig([])


@pytest.fixture
def victoria_metrics(request, dockertester: DockerTester, scrape_config: ScrapeConfig):
    environment = get_environment_with_overrides(request, "victoriametrics")
    internal_port = 8428

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        with (tempdir / "config.yml").open("w") as outp:
            yaml.dump(scrape_config.as_dict(), stream=outp)
            print(yaml.dump(scrape_config.as_dict()))

        managed_container = dockertester.launch_container(
            "victoriametrics/victoria-metrics",
            "victoriametrics",
            image_tag=None,
            environment=environment,
            ports=[internal_port],
            force_pull=True,
            command="-promscrape.config=/vm/config.yml",
            mounts=[(tempdir, Path("vm"))],
        )

    try:
        yield wait_for_web_service(
            managed_container, UrlRequester, internal_port, "metrics"
        )

    finally:
        managed_container.dump_logs_to_stdout()
        managed_container.remove_container()
