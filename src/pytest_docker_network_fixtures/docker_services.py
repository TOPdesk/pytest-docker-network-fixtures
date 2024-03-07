import time
from typing import Optional

import requests
from requests_toolbelt.adapters import host_header_ssl

from pytest_docker_network_fixtures import TestContainerMixin, DockerTester


class UrlRequester(str, TestContainerMixin):
    @property
    def baseurl(self):
        return self

    def get(self, url: str, **kwargs):
        return requests.get(f"{self.baseurl}/{url}", **kwargs)

    def post(self, url: str, **kwargs):
        return requests.post(f"{self.baseurl}/{url}", **kwargs)

    def patch(self, url: str, **kwargs):
        return requests.patch(f"{self.baseurl}/{url}", **kwargs)

    def put(self, url: str, **kwargs):
        return requests.put(f"{self.baseurl}/{url}", **kwargs)

    def delete(self, url: str, **kwargs):
        return requests.delete(f"{self.baseurl}/{url}", **kwargs)

    def wait_for_log_check(self, check_func, timeout=10.0):
        fail_after = time.time() + timeout
        while time.time() < fail_after:
            logs = self.get_logs()
            if check_func(logs):
                return

            time.sleep(1.0)

        raise TimeoutError(f"Log check failed after {timeout}s")

    def wait_for_get_request_check(self, url: str, check_func, timeout=10.0, **kwargs):
        """Waits until an expected result is received from an HTTP GET request.

        The get request is performed multiple times, until either the expected result is received
        or a timeout occurs. Connection errors are not handled. Arguments:
        url -- the URL to make the GET request to
        check_func -- function that checks the expected conditions in the response for the request
        timeout -- timeout, in seconds
        kwargs -- arguments that are passed to the GET request
        """
        fail_after = time.time() + timeout
        while True:
            resp = None
            try:
                resp = requests.get(f"{self.baseurl}/{url}", **kwargs)
                check_func(resp)

            except AssertionError:
                if time.time() >= fail_after:
                    if resp is not None:
                        print(
                            f"GET request failed after {timeout}s, last response contents is: {resp.text}"
                        )
                    raise
                else:
                    time.sleep(1.0)
            else:
                return


class HttpsUrlRequester(str):
    """A utility class that allows you to do proper HTTPS requests to an
    endpoint that supports it. Note that you **must** supply the `root_ca` in order
    for this to work, and you **must** set a Host-header in your request.
    """

    container_id: Optional[str] = None
    dockertest: Optional[DockerTester] = None
    root_ca: Optional[str] = None

    @property
    def baseurl(self):
        return self

    def make_session(self):
        session = requests.Session()
        session.mount("https://", host_header_ssl.HostHeaderSSLAdapter())
        return session

    def get(self, url: str, **kwargs):
        session = self.make_session()
        verify = kwargs.pop("verify", None)
        if verify is None:
            verify = self.root_ca

        return session.get(f"{self.baseurl}/{url}", verify=verify, **kwargs)

    def post(self, url: str, **kwargs):
        session = self.make_session()
        return session.post(f"{self.baseurl}/{url}", verify=self.root_ca, **kwargs)

    def patch(self, url: str, **kwargs):
        session = self.make_session()
        return session.patch(f"{self.baseurl}/{url}", verify=self.root_ca, **kwargs)

    def put(self, url: str, **kwargs):
        session = self.make_session()
        return session.put(f"{self.baseurl}/{url}", verify=self.root_ca, **kwargs)

    def delete(self, url: str, **kwargs):
        session = self.make_session()
        return session.delete(f"{self.baseurl}/{url}", verify=self.root_ca, **kwargs)

    def get_container_logs(self):
        if self.dockertest is None:
            raise Exception("No 'dockertester' set")

        if self.container_id is None:
            raise Exception("No 'container_id' set")

        return self.dockertest.get_logs(self.container_id)

    def wait_for_log_check(self, check_func, timeout=10.0):
        fail_after = time.time() + timeout
        while time.time() < fail_after:
            logs = self.get_container_logs()
            if check_func(logs):
                return

            time.sleep(1.0)

        raise TimeoutError(f"Log check failed after {timeout}s")

    def wait_for_get_request_check(self, url: str, check_func, timeout=10.0, **kwargs):
        """Waits until an expected result is received from an HTTP GET request.

        The get request is performed multiple times, until either the expected result is received
        or a timeout occurs. Connection errors are not handled. Arguments:
        url -- the URL to make the GET request to
        check_func -- function that checks the expected conditions in the response for the request
        timeout -- timeout, in seconds
        kwargs -- arguments that are passed to the GET request
        """
        session = self.make_session()
        fail_after = time.time() + timeout
        while True:
            resp = None
            try:
                resp = session.get(
                    f"{self.baseurl}/{url}", verify=self.root_ca, **kwargs
                )
                check_func(resp)
            except AssertionError:
                if time.time() >= fail_after:
                    if resp is not None:
                        print(
                            f"GET request failed after {timeout}s, last response contents is: {resp.text}"
                        )
                    raise
                else:
                    time.sleep(1.0)
            else:
                return


try:
    from prometheus_client.parser import text_string_to_metric_families

    class MetricsSupplier(UrlRequester):
        metrics_url = None

        def get_metrics_url(self):
            return self.metrics_url if self.metrics_url else self.baseurl

        def get_raw_metrics(self):
            resp = requests.get(f"{self.get_metrics_url()}/metrics")
            assert resp.status_code == 200
            return resp.content.decode("utf-8")

        def get_metric_names(self):
            return {
                family.name
                for family in text_string_to_metric_families(self.get_raw_metrics())
            }

        def get_metrics(self, name, **tags):
            def match_tags(real_tags, filter_tags):
                for k, v in filter_tags.items():
                    if k not in real_tags or real_tags[k] != v:
                        return False
                return True

            for family in text_string_to_metric_families(self.get_raw_metrics()):
                if family.name == name:
                    return [s for s in family.samples if match_tags(s[1], tags)]

            return None

        def get_single_metric(self, name, **tags):
            metrics = self.get_metrics(name, **tags)
            assert metrics is not None
            assert len(metrics) == 1
            sample = metrics[0]

            for tag_name, v in tags.items():
                assert tag_name in sample[1], f"tag {tag_name} not in {sample[1]}"
                assert (
                    sample[1][tag_name] == v
                ), f"value of tag {tag_name} is not {v} but {sample[1][tag_name]}"

            return sample[2]

except ImportError:
    pass
