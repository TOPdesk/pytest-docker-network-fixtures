from __future__ import annotations

import os
import uuid
import ipaddress
import weakref
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple, Union, List, Set
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
import time
import struct
from collections import defaultdict
import tarfile
import tempfile
from pathlib import Path

import docker
from docker.models.containers import Container

_docker_registry: str | None = os.getenv("DOCKER_REGISTRY")


def set_docker_registry(registry: str):
    """
    Set the default docker registry to the value of `registry`.

    :param registry:
    """
    global _docker_registry

    _docker_registry = registry


def get_docker_registry() -> str | None:
    """get the default docker registry"""
    return _docker_registry


def prepare_mount_data(source: Path, target: Path) -> Tuple[bytes, Path]:
    with tempfile.NamedTemporaryFile() as tf:
        tar = tarfile.open(tf.name, "w")
        tar.add(source, target.name)
        tar.close()

        with open(tf.name, "rb") as inp:
            bytes_data = inp.read()

    return bytes_data, target.parent


class DockerStartTimeoutException(Exception):
    pass


@dataclass(frozen=True)
class RoutingTableEntry:
    destination: Union[IPv4Address, IPv6Address]
    gateway: Union[IPv4Address, IPv6Address, None]
    mask: Union[IPv4Address, IPv6Address, None]
    network: Union[IPv4Network, IPv6Network, None]
    metric: str
    interface: str

    @property
    def is_default_gateway(self):
        return self.gateway is not None

    @property
    def is_loopback(self):
        return self.destination.is_loopback

    def in_network(self, addr: Union[str, IPv4Address, IPv6Address]):
        if self.network is None:
            return

        addr = ipaddress.ip_address(addr)

        # Don't consider loopback devices as proper networks
        if addr.is_loopback or self.is_loopback:
            return False

        return addr in self.network


def parse_routing_table() -> Optional[List[RoutingTableEntry]]:
    try:
        with open("/proc/net/route") as inp:
            next(inp)
            route_list = []
            for line in inp:
                routes = line.strip().split()
                destination = ipaddress.ip_address(
                    struct.pack("<L", int(routes[1], 16))
                )
                if destination == IPv4Address("0.0.0.0"):
                    gateway = ipaddress.ip_address(
                        struct.pack("<L", int(routes[2], 16))
                    )
                    mask = None
                    network = None
                else:
                    gateway = None
                    mask = ipaddress.ip_address(struct.pack("<L", int(routes[7], 16)))
                    network = ipaddress.IPv4Network(f"{destination}/{mask}")

                route_list.append(
                    RoutingTableEntry(
                        destination=destination,
                        gateway=gateway,
                        mask=mask,
                        network=network,
                        metric=routes[6],
                        interface=routes[0],
                    )
                )

        return route_list

    except Exception as e:
        print(f"Failed to obtain routing table: {e}")
        return None


@dataclass(frozen=True)
class ManagedContainer:
    weak_docker_tester: weakref.ref
    container_id: str

    @property
    def docker_tester(self) -> DockerTester:
        tester = self.weak_docker_tester()
        assert tester is not None, "Dockertester reference has been garbage collected"
        return tester

    def get_service_name(self) -> str:
        return self.docker_tester.get_service_name(self.container_id)

    def get_connectable_host_and_port(self, internal_port: int) -> Tuple[str, int]:
        return self.docker_tester.get_connectable_host_and_port(
            self.container_id, internal_port
        )

    def base_url_for_container(self, internal_port: int, protocol: str = "http"):
        return self.docker_tester.base_url_for_container(
            self.container_id, internal_port, protocol=protocol
        )

    def get_logs(self) -> str:
        return self.docker_tester.get_logs(self.container_id)

    def dump_logs_to_stdout(
        self, only_once: bool = True, suppress_empty_lines: bool = False
    ):
        self.docker_tester.dump_logs_to_stdout(
            self.container_id,
            only_once=only_once,
            suppress_empty_lines=suppress_empty_lines,
        )

    def stop_container(self, timeout: int = 10):
        self.docker_tester.stop_container(self.container_id, timeout=timeout)

    def start_container(self):
        self.docker_tester.start_container(self.container_id)

    def inspect_container(self) -> Dict[str, Any]:
        return self.docker_tester.inspect_container(self.container_id)


class DockerImageManager(ABC):
    @abstractmethod
    def get_image(self, image: str, extend_image_name: bool) -> str:
        ...

    @abstractmethod
    def get_image_tag(self, image_tag: str, change_image_tag: bool) -> str:
        ...

    @abstractmethod
    def get_docker_registry(self) -> str:
        ...


class DockerTester:
    def __init__(
        self,
        image_manager: DockerImageManager,
        basename: str,
        docker_host: str,
        docker_port: int = 2375,
        virtual_domain: str = "test.loc",
        version: str | None = None,
    ):
        self.image_manager = image_manager
        self.basename = basename
        self._docker_host = docker_host
        self._docker_port = docker_port
        self._virtual_domain = virtual_domain
        self.runid = str(uuid.uuid4())
        self.client = docker.from_env(version=version)
        self._owned_containers: Dict[str, Container] = {}
        self._updated_images = defaultdict(set)
        self.update_images = False
        self._services: Dict[str, str] = {}
        self._container_log_dumped: Set[str] = set()
        self._default_network = self.client.networks.create(
            f"{self.basename}-defaultnet-{self.runid}", driver="bridge"
        )

    def login(self, username, password, registry=None):
        self.client.login(username, password, registry=registry)

    def _generate_container_name(self, service_name: str | Tuple[str]):
        real_service_name = (
            service_name[1] if isinstance(service_name, tuple) else service_name
        )
        return f"{self.basename}_{real_service_name}_{self.runid}"

    def launch_container(
        self,
        image,
        service_name,
        additional_dns_names=(),
        image_tag=None,
        ports=None,
        environment=None,
        force_pull=False,
        extend_image_name=False,
        change_image_tag=False,
        mounts=None,
    ):
        assert ":" not in image, "Image may not contain a tag"

        image = self.image_manager.get_image(image, extend_image_name)
        image_tag = self.image_manager.get_image_tag(image_tag, change_image_tag)

        container_name = self._generate_container_name(service_name)

        for container in self.client.containers.list(
            all=True, filters={"name": container_name}
        ):
            print("removing container ", container.id)
            container.remove(force=True)

        if (self.update_images or force_pull) and image_tag not in self._updated_images[
            image
        ]:
            print(f"Attempting to update docker image {image}:{image_tag}")
            image_obj = self.client.images.pull(image, tag=image_tag)
            print(image_obj)
            self._updated_images[image].add(image_tag)

        print(self._default_network.name)

        config = {
            "name": container_name,
            "hostname": service_name,
            "image": f"{image}:{image_tag}" if image_tag else image,
            "network": None,  # Will be connected after creation
            "publish_all_ports": True,
            "detach": True,
        }

        if isinstance(ports, dict):
            config["ports"] = ports

        elif isinstance(ports, list):
            config["ports"] = {port: None for port in ports}

        else:
            raise ValueError("Expected either a dict or list for ports")

        if environment:
            config["environment"] = environment

        # if mounts:
        #     config["mounts"] = [docker.types.Mount(str(target), str(source), type="bind", read_only=False) for source, target in mounts]

        container = self.client.containers.create(**config)
        self._owned_containers[container.id] = container
        self._services[container.id] = service_name

        if mounts:
            for source, target in mounts:
                data, target_path = prepare_mount_data(Path(source), Path(target))
                container.put_archive(target_path, data)

        aliases = []
        for alias in {service_name} | set(additional_dns_names):
            aliases.append(alias)
            if self._virtual_domain is not None:
                aliases.append(f"{alias}.{self._virtual_domain}")

        print(f"Service name: {service_name} with aliases: {aliases}")
        self._default_network.connect(container, aliases=aliases)
        container.start()

        return ManagedContainer(weakref.ref(self), container.id)

    def get_service_name(self, container_id: str) -> str:
        try:
            return self._services[container_id]
        except KeyError as e:
            raise Exception(
                f"Unknown service with container id = {container_id}"
            ) from e

    def find_id(self, container_designation: str | ManagedContainer) -> str | None:
        if isinstance(container_designation, ManagedContainer):
            return container_designation.container_id

        for container_id, name in self._services.items():
            if container_id == container_designation or name == container_designation:
                return container_id

        return None

    def get_image(self, image, extend_image_name):
        if not extend_image_name:
            return image

        return f"{get_docker_registry()}/{image}"

    def _assert_container(self, container_id) -> Container:
        assert (
            container_id in self._owned_containers
        ), f"Unknown container {container_id}"
        return self._owned_containers[container_id]

    def remove(self, container_id):
        container = self._assert_container(container_id)
        container.remove(force=True)
        del self._owned_containers[container_id]
        del self._services[container_id]

    def remove_all(self):
        for container_id in list(self._owned_containers):
            try:
                self.remove(container_id)

            except Exception as e:
                print(f"Failed to remove container {container_id}: {e}")

            else:
                print(f"Removed container {container_id}")

        print(
            f"Removing network {self._default_network.name} ({self._default_network.id})"
        )
        self._default_network.remove()

    def resolve_host_and_port(self, container_id, port):
        return self.resolve_internal_ip(container_id), port

    def get_port_bindings(self, container_id: str, port: int):
        """This resolves the exposed and bridged local address and port

        :param container_id: id of running container
        :param port: for which exposed to get the mapped port
        :return: address, port
        """
        self._assert_container(container_id)
        bound_ports = self.get_bound_ports(container_id, port)
        if bound_ports is None:
            return None, None
        first_binding = bound_ports[0]
        host_ip = first_binding["HostIp"]
        if not host_ip or host_ip == "0.0.0.0":
            host_ip = self._docker_host

        elif host_ip == "localhost" and self._docker_host != "localhost":
            raise Exception(
                f"Host is bound to localhost, which isn't accessible from '{self._docker_host}'"
            )

        return host_ip, int(first_binding["HostPort"])

    def get_bound_ports(self, container_id: str, port: int):
        key = f"{port}/tcp"
        bound_ports = []

        # In case the API is not ready all_ports will result in an empty array
        start_time = time.time()
        while len(bound_ports) == 0:
            all_ports = self.client.api.inspect_container(container_id)[
                "NetworkSettings"
            ]["Ports"]
            bound_ports = all_ports.get(key)

            if bound_ports is None:
                return None

            if time.time() >= start_time + 15:
                raise Exception(
                    "Timeout obtaining bound ports for container '{}'".format(
                        container_id
                    )
                )

        return bound_ports

    def get_first_bound_ipv4_port(self, container_id, port):
        ports = self.get_bound_ports(container_id, port)
        if ports is None:
            return None

        for obj in ports:
            host_ip = obj["HostIp"]
            if host_ip in ("127.0.0.1", "0.0.0.0"):
                return int(obj["HostPort"])

        return None

    def get_connectable_host_and_port(
        self, container_id: str, internal_port: int
    ) -> Tuple[str, int]:
        """Find host & port that can be used to connect to a container and port
        from the test code. It will use the internal ip and port if the code can
        determine these connections can be routed that way, but falls back
        on the bridged host/port if not. Note that the latter will never work
        from a system like Gitlab, that runs this code from within other Docker
        containers and will not share the same localhost (127.0.0.1) with the
        host, even though the IP-addresses are the same.

        :param container_id: id of container
        :param internal_port: internal port number
        :return: tuple of host and port
        """
        print(
            "Look at the magic",
            Path(__file__).absolute().parent / "bypass_docker_internal_connection",
        )
        if (
            Path(__file__).absolute().parent / "bypass_docker_internal_connection"
        ).exists():
            print(f"No internal routing, using external routing")
            return self.get_port_bindings(container_id, internal_port)

        internal_host = self.resolve_internal_ip(container_id)

        routing_table = parse_routing_table()
        if routing_table is None:
            print(
                f"Cannot determine routing table, assuming internal route ({internal_host}:{internal_port} is OK"
            )
            return internal_host, internal_port

        for entry in routing_table:
            if entry.in_network(internal_host):
                print(
                    f"Routing entry {entry.network} on '{entry.interface}' can route to {internal_host} via default bridging network"
                )
                return internal_host, internal_port

        internal_host_custom = self.resolve_custom_bridge_network_ip(container_id)
        for entry in routing_table:
            if entry.in_network(internal_host_custom):
                print(
                    f"Routing entry  {entry.network} on '{entry.interface}' can route to {internal_host_custom} via custom bridging network"
                )
                return internal_host_custom, internal_port

        external_host, external_port = self.get_port_bindings(
            container_id, internal_port
        )
        print(
            f"No internal routing, using external {external_host}:{external_port} for routing to {internal_host}:{internal_port}"
        )
        return external_host, external_port

    def get_logs(self, container_id) -> str:
        container = self._assert_container(container_id)
        return container.logs().decode("UTF-8").strip()

    def dump_logs_to_stdout(
        self,
        container_id: str,
        only_once: bool = True,
        suppress_empty_lines: bool = False,
    ):
        """Dump the container logs to stdout in a format that makes it easier to
        ascertain the source of the logs.

        :param container_id: the container to dump logs from
        :param only_once: don't dump logs if logs already have been dumped for this container
        :param suppress_empty_lines: don't include empty lines in output
        """
        container = self._assert_container(container_id)
        name = self._services[container_id]

        if only_once and container_id in self._container_log_dumped:
            return

        logs = container.logs().strip()

        print()
        print("=" * 30, "Started", name, "=" * 30)
        for line in logs.splitlines():
            line = line.rstrip()
            if not line and suppress_empty_lines:
                continue
            print("[dockerlog:{}] {}".format(name, line.decode("UTF-8")))

        print("=" * 30, "Closed", name, "=" * 30)

        self._container_log_dumped.add(container_id)

    def base_url_for_container(
        self, container_id: str, internal_port: int, protocol="http"
    ):
        self._assert_container(container_id)
        host, port = self.get_connectable_host_and_port(container_id, internal_port)
        return f"{protocol}://{host}:{port}"

    def inspect_container(self, name_or_id) -> Dict[str, Any]:
        """Return the internal inspect data for a container

        :param name_or_id: the name of the service, or the container id
        :return: inspection data, as a dict
        """
        container_id = self.find_id(name_or_id)
        return self.client.api.inspect_container(container_id)

    def resolve_internal_ip(self, name_or_id):
        """Return the internal IP-address of a container as exposed to the default internal bridging
        network in Docker.
        Do not use this to find a way to connect to a container from test code, use
        `get_connectable_host_and_port()` instead, even though this _might_ work.

        :param name_or_id: the name of the service, or the container id
        :return: the IP-address
        """
        container_id = self.find_id(name_or_id)
        return self.client.api.inspect_container(container_id)["NetworkSettings"][
            "IPAddress"
        ]

    def resolve_custom_bridge_network_ip(self, name_or_id):
        """Return the internal IP-address of a container as exposed to the custom internal
        bridging network in Docker.
        Do not use this to find a way to connect to a container from test code, use
        `get_connectable_host_and_port()` instead, even though this _might_ work.

        :param name_or_id: the name of the service, or the container id
        :return: the IP-address
        """
        container_id = self.find_id(name_or_id)
        network_settings = self.client.api.inspect_container(container_id)[
            "NetworkSettings"
        ]
        custom_bridge_network = network_settings["Networks"][self._default_network.name]
        return custom_bridge_network["IPAddress"]

    def stop_container(self, name_or_id: str, timeout: int = 10):
        container_id = self.find_id(name_or_id)
        container = self._assert_container(container_id)
        container.stop(timeout=timeout)

    def start_container(self, name_or_id: str):
        container_id = self.find_id(name_or_id)
        container = self._assert_container(container_id)
        container.start()


class TestContainerMixin:
    """This class is intended to be used as a mixin for more specialized subclasses.
    As such it doesn't have a __init__(), but relies on calling initialize_container_manager()
    in a timely fashion."""

    _managed_container: ManagedContainer

    def initialize_container_manager(self, managed_container: ManagedContainer):
        assert isinstance(managed_container, ManagedContainer)
        self._managed_container = managed_container

    @property
    def managed_container(self):
        managed_container = self._managed_container
        if managed_container is None:
            raise Exception("initialize_container_manager() was not called")
        return managed_container

    @property
    def docker_tester(self) -> DockerTester:
        return self.managed_container.docker_tester

    @property
    def container_id(self):
        return self.managed_container.container_id

    def stop_container(self, timeout: int = 10):
        self.managed_container.stop_container(timeout=timeout)

    def start_container(self):
        self.managed_container.start_container()

    def inspect_container(self) -> Dict[str, Any]:
        return self.managed_container.inspect_container()

    def get_logs(self) -> str:
        return self.managed_container.get_logs()

    def dump_logs_to_stdout(
        self, only_once: bool = True, suppress_empty_lines: bool = False
    ):
        self.managed_container.dump_logs_to_stdout(
            only_once=only_once, suppress_empty_lines=suppress_empty_lines
        )