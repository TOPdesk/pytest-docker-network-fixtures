# Pre-built fixtures

This project contains a number of pre-built fixtures that you can either use in your
tests, or look at the code for inspiration.


## Databases

### MongoDB

The MongoDB fixture can be used to spin up an empty MongoDB database server.
If you installed the `python-docker-network-fixtures` library with the  `mongodb`
feature enabled, the `pymongo` library (version 4.0.0 or higher) should have already
been installed along with it. Otherwise, you'll need to install `pymongo` yourself.

The code below is taken verbatim from this project's tests, and should give you an
idea how to use it:

```python
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)
from pytest_docker_network_fixtures.databases import mongodb


def test_mongodb(mongodb):
    print(mongodb)
    db = mongodb["test"]
    first = db["first"]
    print(first.insert_one({"name": "henk"}))
    doc = first.find_one({"name": "henk"})
    assert doc.pop("_id") is not None
    assert doc == {"name": "henk"}
```

While the fixture starts a MongoDB instance in the virtual network under the
DNS-names 'mongodb' and 'mongodb.test.loc', the object you actually get as
the fixture is a `MongoContainer`, which is a very shallow wrapper around a 
`MongoClient`, allowing you to use the server from outside that network.


### Postgres

The `postgres` fixture can be used to spin up an empty Postgres database server.
If you installed the `python-docker-network-fixtures` library with the  `postgres`
feature enabled, the `psycopg` library (version 3.0 or higher, with pre-built
binary extension) should have already been installed along with it. Otherwise,
you'll need to install `psycopg` yourself.

The code below is taken verbatim from this project's tests, and should give you an
idea how to use it:

```python
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)
from pytest_docker_network_fixtures.databases import postgres


def test_postgres(postgres):
    print(postgres)

    with postgres.connection.cursor() as cur:
        # Execute a command: this creates a new table
        cur.execute(
            """
              CREATE TABLE first (
                  id serial PRIMARY KEY,
                  name text)
              """
        )

        # Pass data to fill a query placeholders and let Psycopg perform
        # the correct conversion (no SQL injections!)
        cur.execute("INSERT INTO first (name) VALUES (%s)", ("henk",))

        # Query the database and obtain data as Python objects.
        cur.execute("SELECT id, name FROM first")
        data = cur.fetchone()
        assert isinstance(data[0], int)
        assert data[1] == "henk"

        postgres.connection.commit()
```

While the fixture starts a Postgres instance in the virtual network under the
DNS-names 'postgres' and 'postgres.test.loc', the object you actually get as
the fixture is a `PostgresContainer`, allowing you to use the server from
outside that network.

You can override one or more special Postgres environment variables to get a bit
more control over user, password and database to connect to. Below I repeated a tiny
portion of the test code with these overrides added. The values I've overridden
also happen to be the defaults.

```python
@pytest.mark.environment_postgres(
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="admin",
        POSTGRES_DB="postgres")
def test_postgres(postgres):
    ...
```


### MS-Sql version 2019

The `mssql_2019` fixture can be used to spin up an empty MS-Sql database server.
If you installed the `python-docker-network-fixtures` library with the  `mssql`
feature enabled, the `pymssql` library (version 2.2.0 or higher), should have 
already been installed along with it. Otherwise, you'll need to install `pymssql`
yourself.

The code below is taken verbatim from this project's tests, and should give you an
idea how to use it:

```python
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)
from pytest_docker_network_fixtures.databases import mssql_2019


def test_mssql_2019(mssql_2019):
    print(mssql_2019)
    conn = mssql_2019.connect("master")
    conn.autocommit(True)
    with conn.cursor(as_dict=False) as cursor:
        cursor.execute("""CREATE DATABASE test;""")

        cursor.execute(
            """CREATE TABLE [test].[dbo].[first] (
            id INT NOT NULL IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100));"""
        )

    conn.close()

    conn = mssql_2019.connect("test")
    conn.autocommit(False)
    with conn.cursor(as_dict=False) as cursor:
        cursor.executemany("INSERT INTO first (name) VALUES (%s)", [("Henk",)])

        conn.commit()
        cursor.execute("SELECT * FROM first WHERE name = %s", "Henk")
        row = cursor.fetchone()
        print(row)
        assert row[1] == "Henk"
        assert isinstance(row[0], int)
        conn.commit()
```

While the fixture starts a SQL-server instance in the virtual network under the
DNS-names 'mssql_2019' and 'mssql_2019.test.loc', the object you actually get as
the fixture is an `MssqlTestContainer`, allowing you to use the server from
outside that network.

You can meaningfully override just one special MS-Sql environment variable, and
that is the administrator password. (Note that the administrator account is always
"sa".) Below I repeated a tiny portion of the test code with that override added.
The value I've overridden also happens to be the default.

```python
@pytest.mark.environment_mssql_2019(
            MSSQL_SA_PASSWORD="yourStrong(!)Password"
)
def test_mssql_2019(mssql_2019):
    ...
```

## Messaging

### RabbitMQ server

The `rabbitmq` fixture can be used to spin up a RabbitMQ server.
If you installed the `python-docker-network-fixtures` library with the  `rabbitmq`
feature enabled, the `amqp` library (version 5.2.0 or higher), should have 
already been installed along with it. Otherwise, you'll need to install `amqp`
yourself.

The code below is taken verbatim from this project's tests, and should give you an
idea how to use it:

```python
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_registry_manager,
)

from pytest_docker_network_fixtures.rabbitmq import rabbitmq


def test_rabbitmq(rabbitmq):
    rabbitmq.basic_publish("some.key", "some message")
```

While the fixture starts a RabbitMQ instance in the virtual network under the
DNS-names 'rabbitmq' and 'rabbitmq.test.loc', the object you actually get as
the fixture is an `RabbitMqBroadcaster`, allowing you to use the server from
outside that network. That `RabbitMqBroadcaster` is a very simple client to do
broadcasts to a pre-defined exchange (by default "default") and exchange type
(by default "topic"). You can override that by using an environment override,
like this:

```python
@pytest.mark.environment_rabbitmq(
            RABBITMQ_EXCHANGE_NAME="default",
            RABBITMQ_EXCHANGE_TYPE="topic"
    
)
def test_rabbitmq(rabbitmq):
    ...
```

## Telemetry

### Victoriametrics

The `victoria_metrics` fixture can be used to spin up a Victoriametrics server.
That fixture depends on a `scrape_config` fixture, that you must provide. The
code below is taken verbatim from this project's tests, and should give you an
idea how to do this:

```python
import time

import pytest

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
```

While the fixture starts a Victoriametrics instance in the virtual network under
the DNS-names 'victoria_metrics' and 'victoria_metrics.test.loc', the object you
actually get as the fixture is an `UrlRequester`, allowing you to easily do
requests to the server from outside that network.