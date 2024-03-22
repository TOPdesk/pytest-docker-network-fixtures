import time

import pytest

# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)
from pytest_docker_network_fixtures.telemetry import (
    victoria_metrics,
    ScrapeConfig,
    ScrapeTarget,
)


@pytest.fixture
def scrape_config():
    yield ScrapeConfig(
        [ScrapeTarget(job_name="self", static_configs=["victoriametrics:8428"])],
        scrape_interval="2s",
    )


def test_victoria_metrics(victoria_metrics):
    print(victoria_metrics)
    time.sleep(3)  # Should be just enough to do a single self-scrape
    result = victoria_metrics.get("api/v1/labels").json()
    assert result["status"] == "success"
    assert "__name__" in result["data"]
    assert "scrape_job" in result["data"]
