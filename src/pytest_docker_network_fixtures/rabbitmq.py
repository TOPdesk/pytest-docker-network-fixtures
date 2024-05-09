import time
import datetime

import pytest
import requests

from pytest_docker_network_fixtures import (
    DockerStartTimeoutException,
    DockerTester,
    TestContainerMixin,
)
from pytest_docker_network_fixtures.core_fixtures import get_environment_with_overrides

try:
    import amqp

    def log(message: str):
        timestamp = datetime.datetime.now().isoformat()
        print(f"{timestamp}  {message}")

    class RabbitMqBroadcaster(TestContainerMixin):
        def __init__(
            self, hostname, port, exchange_name: str, exchange_type: str = "topic"
        ):
            self.hostname: str = hostname
            self.port: int = port
            self.exchange_name: str = exchange_name
            self.exchange_type: str = exchange_type
            self._connection = None
            self._amqp_channel = None

        def _ensure_channel(self):
            if self._amqp_channel is None:
                self._close_connection()
                print(
                    f"RabbitMqBroadcaster: Trying to connect to {self.hostname}:{self.port}"
                )
                self._connection = amqp.Connection(host=f"{self.hostname}:{self.port}")
                if hasattr(self._connection, "connect"):
                    self._connection.connect()

                self._amqp_channel = self._connection.channel()
                self._amqp_channel.exchange_declare(
                    exchange=self.exchange_name,
                    type=self.exchange_type,
                    auto_delete=False,
                )

        def basic_publish(self, routing_key: str, message_body: str):
            self._ensure_channel()
            content = amqp.basic_message.Message(message_body)
            self._amqp_channel.basic_publish(
                exchange=self.exchange_name, routing_key=routing_key, msg=content
            )

        def _close_connection(self):
            try:
                if self._connection is not None:
                    self._connection.close()

            finally:
                self._connection = None
                self._amqp_channel = None

        def reconnect(self, timeout: float = 10.0):
            try:
                self._close_connection()

            except Exception as e:
                log(f"Error closing connection {e}")

            timeout_time = time.time() + timeout

            while time.time() <= timeout_time:
                try:
                    self._ensure_channel()
                    return

                except Exception as e:
                    log(f"Could not re-connect yet: {e}")

                time.sleep(0.5)

    @pytest.fixture()
    def rabbitmq(dockertester: DockerTester, request):
        environment = get_environment_with_overrides(request, "rabbitmq")

        exchange_name = environment.pop("RABBITMQ_EXCHANGE_NAME", "default")
        exchange_type = environment.pop("RABBITMQ_EXCHANGE_TYPE", "topic")

        managed_container = dockertester.launch_container(
            "rabbitmq:3.11.5-management-alpine",
            "rabbitmq",
            environment=environment,
            ports=[5672, 15672],
        )

        print(f"CONTAINER {managed_container}")

        def make_connection() -> RabbitMqBroadcaster:
            last_exception = None
            start_time = time.time()
            while time.time() < (start_time + 20):
                # noinspection PyBroadException
                try:
                    (
                        management_ip,
                        management_port,
                    ) = managed_container.get_connectable_host_and_port(15672)
                    if management_ip is None:
                        raise Exception("No bound port for 15672")

                    resp = requests.get(f"http://{management_ip}:{management_port}")
                    print("RabbitMQ management available, status:", resp.status_code)

                    (
                        amqp_ip,
                        amqp_port,
                    ) = managed_container.get_connectable_host_and_port(5672)
                    if amqp_ip is None:
                        raise Exception("No bound port for 5672")

                    broadcaster = RabbitMqBroadcaster(
                        hostname=amqp_ip,
                        port=amqp_port,
                        exchange_name=exchange_name,
                        exchange_type=exchange_type,
                    )
                    broadcaster._ensure_channel()
                    print(
                        f"Service 'rabbitmq' started in {time.time() - start_time:2.2f} seconds with on port {amqp_port}"
                    )
                    broadcaster.initialize_container_manager(managed_container)
                    return broadcaster

                except Exception as exc:
                    last_exception = exc

                time.sleep(0.1)

            raise DockerStartTimeoutException(
                f"Timeout starting service 'rabbitmq': {last_exception}"
            )

        try:
            connection = make_connection()
            yield connection

        except Exception as exc:
            print(f"Problem starting service, dumping log; error = {exc}")
            managed_container.dump_logs_to_stdout()
            raise

        finally:
            managed_container.dump_logs_to_stdout()
            managed_container.remove_container()

except ImportError:
    pass
