import contextlib
import os
import time
import json
from pathlib import Path
import datetime
import tempfile
import shutil

import jwt
import pytest
import requests
from prometheus_client.parser import text_string_to_metric_families

import makecert

from dockertester import (
    DockerTester,
    MetricsSupplier,
    UrlRequester,
    DockerStartTimeoutException,
    HttpsUrlRequester,
    TestContainerMixin,
)
from pytest_docker_network_fixtures.container_waiters import wait_for_web_service

INTERACTIVE = os.path.exists(os.path.join(os.path.dirname(__file__), "interactive.txt"))
print(f"Interactive mode = {INTERACTIVE}")


def is_interactive():
    return INTERACTIVE


def interactive_sleep(seconds):
    if not INTERACTIVE:
        return
    time.sleep(seconds)


# Use local versions of the fake-services when a file called "use_local_fakes" exists
def use_local_version():
    workspace_env = os.getenv("WORKSPACE_ROOT")
    if workspace_env:
        test_directory = os.path.join(workspace_env, "integration-tests")
    else:
        test_directory = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(test_directory, "use_local_fakes")
    return os.path.isfile(path)


# Checks if the tests are run in the CI environment or not
def is_CI():
    if os.getenv("IS_IN_CI", None):
        return True
    return False


def container_registry():
    return os.getenv("CONTAINER_REGISTRY", "docker-registry.topdesk.com/topdesk")


def nginx_log_level():
    return os.getenv("NGINX_ERROR_LOG_LEVEL", "debug")


def image_tag() -> str:
    if not is_CI():
        return "main-snapshot"

    tag = os.getenv("IMAGE_TAG")
    if tag is None:
        raise Exception("Missing IMAGE_TAG environment variable")

    return tag


IN_GITLAB_CI_ONLY = is_CI()
PULL_FAKE_SERVICES_FROM_NEXUS = not use_local_version()


def _multi_env_service_config_setting(service, key, values):
    params = [
        pytest.param({"environment": {key: value}}, id=f"{key}={value}")
        for value in values
    ]

    return pytest.mark.parametrize(service, params, indirect=True)


def service_config(servicename, cert_expires_days=None, **environment):
    if len(environment) == 1:
        k, v = list(environment.items())[0]
        if isinstance(v, list):
            return _multi_env_service_config_setting(servicename, k, v)

    return _service_config_setting(servicename, cert_expires_days, environment)


def _service_config_setting(service, cert_expires_days, environment):
    param = {}
    names = []

    name = f"environment-changes({len(environment)})"
    if len(environment) == 1:
        for key, value in environment.items():
            name = f"{key}={value}"

    if len(environment) > 0:
        names.append(name)
        param["environment"] = environment

    if cert_expires_days is not None:
        names.append(f"cert_expires_days={cert_expires_days}")
        param["cert_expires_days"] = cert_expires_days

    assert len(names) > 0
    name = ";".join(names)

    return pytest.mark.parametrize(
        service, [pytest.param(param, id=name)], indirect=True
    )


def create_fake_stb_token(name: str, expiry: datetime.datetime, roles=None):
    payload = {"sub": name, "exp": expiry}

    if roles is not None:
        payload["roles"] = roles

    return jwt.encode(payload, "topdesk", algorithm="HS256")


def create_fake_stb_token_expires_in(name: str, expiry_in_seconds: int, roles=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    expiry = now + datetime.timedelta(seconds=expiry_in_seconds)
    return create_fake_stb_token(name, expiry, roles)


# scope="session"


def use_local_fake_saas_tooling_bridge():
    test_dir = os.path.dirname(os.path.abspath(__file__))

    result = os.path.exists(
        os.path.join(test_dir, ".use_local_fake_saas_tooling_bridge")
    )
    if result:
        print("Using local fake-saas-tooling-bridge")
    else:
        print("Using fake-saas-tooling-bridge from nexus")

    return result


class FakeSaasToolingBridge(UrlRequester):
    def add_instance(
        self,
        name,
        aliases,
        datacenter="hm1",
        location="hm1c01",
        gos="hm1c01app01",
        port=8006,
        **kwargs,
    ):
        json_data = {
            "name": name,
            "aliases": aliases,
            "datacenter": datacenter,
            "location": location,
            "gos": gos,
            "port": port,
        }

        json_data.update(kwargs)

        resp = self.post("debug/tenants", json=json_data)

        if resp.status_code not in (200, 201, 204):
            raise Exception(
                f"Instance creation failed: status={resp.status_code}, body={resp.text}"
            )

        print(f"Instance '{name}' created, status={resp.status_code}")

    def patch_instance(self, name, **kwargs):
        resp = self.patch(f"debug/tenants/{name}", json=kwargs)

        if resp.status_code not in (200, 201, 204):
            raise Exception(
                f"Instance patch failed: status={resp.status_code}, body={resp.text}"
            )

        print(f"Instance '{name}' patched, status={resp.status_code}")

    def delete_instance(self, name):
        resp = self.delete(f"debug/tenants/{name}")

        if resp.status_code not in (200, 201, 204):
            raise Exception(
                f"Instance deletion failed: status={resp.status_code}, body={resp.text}"
            )

        print(f"Instance '{name}' deleted, status={resp.status_code}")

    def add_location(self, name, loadbalancer_name, domain_name):
        location_data = {
            "name": name,
            "loadbalancer_name": loadbalancer_name,
            "domain_name": domain_name,
        }

        resp = self.post("debug/locations", json=location_data)

        if resp.status_code not in (200, 201, 204):
            raise Exception(
                f"Location creation failed: status={resp.status_code}, body={resp.text}"
            )

        print(f"Location '{name}' created, status={resp.status_code}")


@pytest.fixture()
def fake_saas_tooling_bridge(dockertest: DockerTester, request):
    environment = {}

    fixture_params = getattr(request, "param", {})

    # Alternatively: request.node.callspec.params
    if "environment" in fixture_params:
        environment.update(fixture_params["environment"])

    print("Environment variables - fake_saas_tooling_bridge:", environment)

    dumped = False
    managed_container = dockertest.launch_container(
        "docker-registry.topdesk.com/topdesk/fake-saas-tooling-bridge",
        "fake-saas-tooling-bridge",
        image_tag="master-snapshot",
        environment=environment,
        ports=[8092],
        force_pull=not use_local_fake_saas_tooling_bridge(),
    )

    try:
        yield wait_for_web_service(
            managed_container, FakeSaasToolingBridge, 8092, "healthz"
        )

    except Exception as exc:
        print(f"Problem starting service, dumping log; error = {exc}")
        dockertest.dump_logs_to_stdout(managed_container)
        dumped = True
        raise

    finally:
        if not dumped:
            dockertest.dump_logs_to_stdout(managed_container.container_id)
        dockertest.remove(managed_container.container_id)


@pytest.fixture()
def fake_topdesk1(dockertest: DockerTester):
    environment = {"TOPDESK_PORT": "8001"}
    dumped = False
    container_id = dockertest.launch_container(
        container_registry() + "/faketopdesk",
        "instance1",
        additional_dns_names=("hm1c01app01",),
        image_tag=image_tag(),
        environment=environment,
        ports=[8001],
        force_pull=is_CI(),
    )

    try:
        service = UrlRequester(
            dockertest.wait_for_web_service(container_id, 8001, "any")
        )
        service._dockertest = dockertest
        service._container_id = container_id

        yield service

    except Exception as exc:
        print(f"Problem starting service, dumping log; error = {exc}")
        dockertest.dump_logs_to_stdout(container_id)
        dumped = True
        raise

    finally:
        if not dumped:
            dockertest.dump_logs_to_stdout(container_id)
        dockertest.remove(container_id)


@pytest.fixture()
def fake_topdesk2(dockertest: DockerTester):
    environment = {"TOPDESK_PORT": "8002"}
    dumped = False
    container_id = dockertest.launch_container(
        container_registry() + "/faketopdesk",
        "instance2",
        additional_dns_names=("hm1c01app02",),
        image_tag=image_tag(),
        environment=environment,
        ports=[8002],
        force_pull=is_CI(),
    )

    try:
        service = UrlRequester(
            dockertest.wait_for_web_service(container_id, 8002, "any")
        )
        service._dockertest = dockertest
        service._container_id = container_id

        yield service

    except Exception as exc:
        print(f"Problem starting service, dumping log; error = {exc}")
        dockertest.dump_logs_to_stdout(container_id)
        dumped = True
        raise

    finally:
        if not dumped:
            dockertest.dump_logs_to_stdout(container_id)
        dockertest.remove(container_id)


class WaitForChangeTimeoutException(Exception):
    def __init__(self, timeout=10.0):
        self.timeout = timeout
        super().__init__(f"Change wait timed out after {timeout}s")


@contextlib.contextmanager
def wait_for_change(func, delay=1.0, timeout=10.0):
    """A simple contextmanager that can wait for changes in the result of a
    function."""
    val = func()
    yield val

    timeout_after = time.time() + timeout
    while time.time() < timeout_after:
        time.sleep(delay)
        if func() != val:
            return

    raise WaitForChangeTimeoutException(timeout)


class AliasDataService(MetricsSupplier):
    def get_instance_update_count(self):
        resp = self.get("instancedata_update_count")
        assert resp.status_code == 200
        data = resp.json()
        update_count = data["update_count"]
        print("Update count =", update_count)
        return update_count

    def instance_update(self, delay=1.0, timeout=10.0):
        return wait_for_change(
            self.get_instance_update_count, delay=delay, timeout=timeout
        )

    def get_instance_state_update_count(self):
        resp = self.get("instancestate_update_count")
        assert resp.status_code == 200, f"got unexpected status {resp.status_code}"
        data = resp.json()
        update_count = data["update_count"]
        print("Instance state update count =", update_count)
        return update_count

    def instance_state_update(self, delay=1.0, timeout=10.0):
        return wait_for_change(
            self.get_instance_state_update_count, delay=delay, timeout=timeout
        )

    def get_solutions_update_count(self):
        resp = self.get("generic-solutions-update-count")
        assert resp.status_code == 200
        data = resp.json()
        update_count = data["update_count"]
        return update_count

    def wait_for_solutions_update(self, old_count, timeout=10.0):
        timeout_after = time.time() + timeout
        while self.get_solutions_update_count() == old_count:
            time.sleep(1)
            if time.time() > timeout_after:
                raise Exception("Update wait timed out")

    def full_sync_trigger(self):
        resp = self.get("full_sync_trigger")
        assert resp.status_code == 200
        print("Full sync trigger:", resp.text)

    def is_connected_to_rabbitmq(self):
        return bool(self.get_single_metric("rabbitmq_connected"))

    def wait_for_rabbitmq_connection(self, timeout=20.0):
        start = time.time()
        timeout_time = start + timeout
        while not self.is_connected_to_rabbitmq():
            if time.time() >= timeout_time:
                raise TimeoutError()
            time.sleep(0.5)

        print(f"Waited {time.time() - start:.2f}s for connection to RabbitMQ")

    def wait_for_rabbitmq_disconnection(self, timeout=20.0):
        start = time.time()
        timeout_time = start + timeout
        while self.is_connected_to_rabbitmq():
            if time.time() >= timeout_time:
                raise TimeoutError()
            time.sleep(0.5)

        print(f"Waited {time.time() - start:.2f}s for disconnection to RabbitMQ")


@pytest.fixture()
def cache_directory():
    this_dir = Path(__file__).absolute().parent / "test-data/cache"
    print(this_dir)
    return this_dir


@pytest.fixture()
def alias_data_service(
    dockertest: DockerTester,
    fake_saas_tooling_bridge,
    fake_topdesk1,
    fake_topdesk2,
    cache_directory,
    request,
):
    environment = {
        "LOGGING_LEVEL": "debug",
        "SAAS_TOOLING_BRIDGE_URL": "http://fake-saas-tooling-bridge:8092",
        "SAAS_TOOLING_BRIDGE_AUTH_TOKEN": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlIiwiZXhwIjoyNTU3OTEzOTk0fQ.WKjRFB2cuqt97H0CsUtD9-OHMat1LduX4J3a4IdM83Q",
        "SAAS_EXTERNAL_DOMAIN_NAME": "topdeskacc.net",
        "RABBITMQ_HOST_NAME": "rabbitmq",
        "RABBITMQ_PORT_NUMBER": "5672",
        "RABBITMQ_USERNAME": "guest",
        "RABBITMQ_PASSWORD": "guest",
    }

    fixture_params = getattr(request, "param", {})

    # Alternatively: request.node.callspec.params
    if "environment" in fixture_params:
        environment.update(fixture_params["environment"])

    dumped = False
    container_id = dockertest.launch_container(
        container_registry() + "/alias-data-service",
        "alias-data-service",
        image_tag=image_tag(),
        environment=environment,
        ports=[8080],
        force_pull=is_CI(),
        mounts=[(cache_directory, "/go/bin/cache")],
    )

    try:
        service = AliasDataService(
            dockertest.wait_for_web_service(container_id, 8080, "ready")
        )
        service._dockertest = dockertest
        service._container_id = container_id

        yield service

    except Exception as exc:
        print(f"Problem starting service, dumping log; error = {exc}")
        dockertest.dump_logs_to_stdout(container_id)
        dumped = True
        raise

    finally:
        if not dumped:
            dockertest.dump_logs_to_stdout(container_id)
        dockertest.remove(container_id)


@pytest.fixture()
def certs_directory():
    this_dir = Path(__file__).absolute().parent / "certs"
    print(this_dir)
    return this_dir


@pytest.fixture()
def passlayer_ingress_proxy(
    request,
    dockertest: DockerTester,
    alias_data_service,
    fakepasslayer,
    certs_directory: Path,
):
    environment = {
        "ALIAS_DATA_SERVICE": "alias-data-service:8080",
        "SAAS_EXTERNAL_DOMAIN_NAME": "topdeskacc.net",
        "NGINX_ERROR_LOG_LEVEL": nginx_log_level(),
    }
    dumped = False

    fixture_params = getattr(request, "param", {})

    # Alternatively: request.node.callspec.params
    if "environment" in fixture_params:
        environment.update(fixture_params["environment"])

    certs_dir = tempfile.TemporaryDirectory(prefix="pytest")
    shutil.copytree(certs_directory, certs_dir.name, dirs_exist_ok=True)
    print(f"CERTS in {certs_dir.name}")

    if "cert_expires_days" in fixture_params:
        expire_after_days = fixture_params["cert_expires_days"]
        certs_dir_path = Path(certs_dir.name).absolute()
        makecert.makecert_with_ca(certs_dir_path, expire_after_days=expire_after_days)
        print(f"Created proxy cert expiring after {expire_after_days} days")

    # certs_directory = os.path.join(os.path.dirname(os.path.abspath("__file__")), "certs")
    # print("Certs directory", certs_directory)
    # assert os.path.isdir(certs_directory)
    container_id = dockertest.launch_container(
        container_registry() + "/passlayer-ingress-proxy",
        "passlayer-ingress-proxy",
        image_tag=image_tag(),
        environment=environment,
        ports=[8079, 8080, 8081],
        force_pull=is_CI(),
        mounts=[(certs_dir.name, "/usr/local/openresty/certs")],
    )

    try:
        metrics_url = dockertest.wait_for_web_service(
            container_id, 8081, "proxy-health"
        )
        service = HttpsUrlRequester(
            dockertest.base_url_for_container(container_id, 8080, protocol="https")
        )
        service.metrics_supplier = MetricsSupplier(metrics_url)
        service.dockertester = dockertest
        service.container_id = container_id
        service.root_ca = certs_directory / "ca.crt"

        yield service

    except Exception as exc:
        print(f"Problem starting service, dumping log; error = {exc}")
        dockertest.dump_logs_to_stdout(container_id)
        dumped = True
        raise

    finally:
        if not dumped:
            dockertest.dump_logs_to_stdout(container_id)
        dockertest.remove(container_id)


@pytest.fixture()
def passlayer_ingress_proxy_metrics(passlayer_ingress_proxy):
    ms = MetricsSupplier(
        passlayer_ingress_proxy.dockertester.base_url_for_container(
            passlayer_ingress_proxy.container_id, 8081
        )
    )
    ms._container_id = passlayer_ingress_proxy.container_id
    ms._dockertest = passlayer_ingress_proxy.dockertester
    return ms


def metricsgetter(baseurl, endpoint="/metrics"):
    def match_tags(real_tags, filter_tags):
        for k, v in filter_tags.items():
            if k not in real_tags or real_tags[k] != v:
                return False
        return True

    def get_metrics(name, **tags):
        resp = requests.get(f"{baseurl}{endpoint}")
        assert resp.status_code == 200
        for family in text_string_to_metric_families(resp.text):
            if family.name == name:
                return [s for s in family.samples if match_tags(s[1], tags)]

        return None

    return get_metrics
