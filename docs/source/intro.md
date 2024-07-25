# Intro

The `pytest-docker-network-fixtures` (yes, it's quite a mouthful) is intended to make 
it easy to wire-up one or more Docker containers in their own Docker network, expose 
these as Pytest fixtures to your test code, and run your (integration) tests against 
these.

The Docker containers that the fixtures can spin up can be anything: they can be local 
images, either true, functional ones or purpose-built fakes. Or they can be standard 
docker images, available from DockerHub of any other Docker registry.

These tests can run locally, or from a CI whenever Docker is available. We've had very 
good results from running it from the Gitlab CI. Locally, you can run your tests (or 
single test) from IDEs like Vscode/Vscodium or IntellIJ, as well as the command line.

The Pytest fixture teardown will make sure all containers it spins up are properly 
terminated at the end of the run, including the custom Docker bridge network it sets 
up, leaving a clean slate.

Part of the container teardown is to get its logs, and dump that, clearly delineated, 
to stdout. It's hard to overstate how helpful this has proved to be, even though at 
times it feels like a lot of text to wade through.

