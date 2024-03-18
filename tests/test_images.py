from pytest_docker_network_fixtures.images import docker_image, DockerImage


def test_plain_image():
    image = docker_image("mongo")
    assert isinstance(image, DockerImage)
    assert image.full_name == "mongo"
    assert image.image_name == "mongo"
    assert image.image_tag is None
    assert image.docker_registry is None


def test_tagged_image():
    image = docker_image("mongo:latest")
    assert isinstance(image, DockerImage)
    assert image.full_name == "mongo:latest"
    assert image.image_name == "mongo"
    assert image.image_tag == "latest"
    assert image.docker_registry is None


def test_image_with_registry():
    image = docker_image("superreg:9000/mongo")
    assert isinstance(image, DockerImage)
    assert image.full_name == "superreg:9000/mongo"
    assert image.image_name == "mongo"
    assert image.image_tag is None
    assert image.docker_registry == "superreg:9000"


def test_tagged_image_with_registry():
    image = docker_image("superreg:9000/mongo:latest")
    assert isinstance(image, DockerImage)
    assert image.full_name == "superreg:9000/mongo:latest"
    assert image.image_name == "mongo"
    assert image.image_tag == "latest"
    assert image.docker_registry == "superreg:9000"
