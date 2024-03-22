from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Final

_image_re = re.compile(
    r"^((?P<docker_registry>.*)/)?(?P<image_name>[a-z0-9-_.]+)(:(?P<image_tag>[a-z0-9-_.]+))?$"
)


@dataclass(frozen=True)
class DockerImage:
    """Simple abstraction representing a docker image."""

    image_name: str
    image_tag: str | None
    docker_registry: str | None = None
    use_local: bool = False

    @property
    def tagless_name(self) -> str:
        """The full canonical name of this image without the image_tag."""
        return (
            f"{self.docker_registry}/{self.image_name}"
            if self.docker_registry
            else self.image_name
        )

    @property
    def full_name(self) -> str:
        """The full canonical name of this image."""

        return (
            f"{self.tagless_name}:{self.image_tag}"
            if self.image_tag
            else self.tagless_name
        )

    def with_image_tag(self, image_tag: str | None) -> DockerImage:
        """Return a new DockerImage with the `image_tag` field set to the given `image_tag`.

        :param image_tag: the new tag. `None` means 'no tag'
        :type image_tag: str | None

        :return: a new DockerImage
        :rtype: DockerImage
        """
        return DockerImage(
            self.image_name, image_tag, self.docker_registry, self.use_local
        )

    def with_docker_registry(self, docker_registry: str | None) -> DockerImage:
        """Return a new DockerImage with the `docker_registry` field set to the given `docker_registry`.

        :param docker_registry: the new name of the Docker registry. `None` means 'no registry'
        :type docker_registry: str | None

        :return: a new DockerImage
        :rtype: DockerImage
        """
        return DockerImage(
            self.image_name, self.image_tag, docker_registry, self.use_local
        )

    def with_use_local(self, use_local: bool) -> DockerImage:
        """Return a new DockerImage with the `use_local` field set to the given `use_local`.

        :param use_local: the new use_local
        :type use_local: str | None

        :return: a new DockerImage
        :rtype: DockerImage
        """
        return DockerImage(
            self.image_name, self.image_tag, self.docker_registry, use_local
        )

    @staticmethod
    def from_name(full_name: str, use_local=False) -> DockerImage:
        """Return a DockerImage from a docker image name

        :param full_name: The docker image name
        :type full_name str

        :param use_local: flag to indicate whether you want a locally
          present docker image, or a remote one. Defaults to `False`
        :type use_local: bool

        :returns: a DockerImage
        :rtype: DockerImage

        :raises ValueError: if the full_name is an invalid docker image name
        """
        mobj = _image_re.match(full_name)
        if mobj is None:
            raise ValueError(f"Malformed docker image name: '{full_name}'")

        return DockerImage(use_local=use_local, **mobj.groupdict())


def docker_image(full_name: str, use_local=False) -> DockerImage:
    """Return a DockerImage from a docker image name

    :param full_name: The docker image name
    :type full_name str

    :param use_local: flag to indicate whether you want a locally
          present docker image, or a remote one. Defaults to `False`
    :type use_local: bool

    :returns: a DockerImage
    :rtype: DockerImage

    :raises ValueError: if the full_name is an invalid docker image name
    """
    return DockerImage.from_name(full_name, use_local=use_local)


@dataclass
class DockerRegistry:
    name: str
    registry: str | None
    default_tag: str | None = None
    username: str | None = None
    password: str | None = None

    def image(self, image_name: str, use_local: bool = False) -> DockerImage:
        image = docker_image(image_name, use_local)
        if image.docker_registry is None:
            image = image.with_docker_registry(self.registry)

        elif image.docker_registry != self.registry:
            raise ValueError(
                f"Mismatched docker registries: {image.docker_registry} != {self.registry}"
            )

        if self.default_tag is not None and image.image_tag is None:
            image = image.with_image_tag(self.default_tag)

        return image

    @staticmethod
    def from_env(name: str) -> DockerRegistry | None:
        registry = os.getenv("DOCKERREGISTRY", None)
        if registry is None:
            return None

        username = os.getenv("DOCKERLOGINUSER", None)
        password = None

        if username is not None:
            password = os.getenv("DOCKERLOGINPASS", None)
            if password is None:
                raise ValueError("Can't login without password")

        return DockerRegistry(name, registry, username, password)


PUBLIC_DOCKER_REGISTRY_NAME: Final[str] = "public"
BUILD_DOCKER_REGISTRY_NAME: Final[str] = "build"


class DockerImageManager:
    registries_by_name: Dict[str, DockerRegistry]
    registries_by_registry: Dict[str, DockerRegistry]

    def __init__(self):
        self.registries_by_name = {}
        self.registries_by_registry = {}

    def registries(self):
        for registry in self.registries_by_registry.values():
            yield registry

    def add_registry(self, registry: DockerRegistry):
        if registry.name in self.registries_by_name:
            raise ValueError(f"A registry with name '{registry.name}' already exists")

        if registry.registry in self.registries_by_registry:
            raise ValueError(
                f"A registry with registry '{registry.registry}' already exists"
            )

        self.registries_by_name[registry.name] = registry
        self.registries_by_registry[registry.registry] = registry

    def __getitem__(self, item):
        return self.registries_by_name[item]

    @property
    def public(self) -> DockerRegistry:
        registry = self.registries_by_name.get(PUBLIC_DOCKER_REGISTRY_NAME)
        if registry is None:
            raise Exception(f"Public registry not present")

        return registry

    @property
    def build(self) -> DockerRegistry:
        registry = self.registries_by_name.get(BUILD_DOCKER_REGISTRY_NAME)
        if registry is None:
            raise Exception(f"Build registry not present")

        return registry

    # def get_image_tag(self, image_tag: str, change_image_tag: bool) -> str:
    #     if not change_image_tag:
    #         return image_tag

    # ci_commit_ref_name = os.getenv("CI_COMMIT_REF_NAME", None)
    # if ci_commit_ref_name == "master" or ci_commit_ref_name == "main":
    #     commit_short_sha = os.getenv("CI_COMMIT_SHORT_SHA", None)
    #     return commit_short_sha if commit_short_sha else image_tag
    # else:
    #     ci_commit_ref_no_underscores = os.getenv(
    #         "CI_COMMIT_REF_NO_UNDERSCORES", None
    #     )
    #     return (
    #         f"{ci_commit_ref_no_underscores}-snapshot"
    #         if ci_commit_ref_no_underscores
    #         else image_tag
    #     )
