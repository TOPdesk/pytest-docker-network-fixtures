from __future__ import annotations

import os
import re
from dataclasses import dataclass

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


class DockerImageManager:
    def get_docker_registry(self) -> str | None:
        return os.getenv("DOCKER_REGISTRY")

    def get_image(self, image: str, extend_image_name):
        if not extend_image_name or self.get_docker_registry() is None:
            return image

        return f"{self.get_docker_registry()}/{image}"

    def get_image_tag(self, image_tag: str, change_image_tag: bool) -> str:
        if not change_image_tag:
            return image_tag

        ci_commit_ref_name = os.getenv("CI_COMMIT_REF_NAME", None)
        if ci_commit_ref_name == "master" or ci_commit_ref_name == "main":
            commit_short_sha = os.getenv("CI_COMMIT_SHORT_SHA", None)
            return commit_short_sha if commit_short_sha else image_tag
        else:
            ci_commit_ref_no_underscores = os.getenv(
                "CI_COMMIT_REF_NO_UNDERSCORES", None
            )
            return (
                f"{ci_commit_ref_no_underscores}-snapshot"
                if ci_commit_ref_no_underscores
                else image_tag
            )
