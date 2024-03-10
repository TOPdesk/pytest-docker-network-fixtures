
# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import dockertester, dockertester_config, docker_image_manager
from pytest_docker_network_fixtures.databases import mongodb, postgres


def test_mongodb(mongodb):
    print(mongodb)
    db = mongodb["test"]
    first = db["first"]
    print(first.insert_one({"name": "henk"}))
    doc = first.find_one({"name": "henk"})
    assert doc.pop("_id") is not None
    assert doc == {"name": "henk"}


def test_postgres(postgres):
    print(postgres)

    with postgres.connection.cursor() as cur:
        # Execute a command: this creates a new table
        cur.execute("""
              CREATE TABLE first (
                  id serial PRIMARY KEY,
                  name text)
              """)

        # Pass data to fill a query placeholders and let Psycopg perform
        # the correct conversion (no SQL injections!)
        cur.execute(
            "INSERT INTO first (name) VALUES (%s)",
            ("henk",))

        # Query the database and obtain data as Python objects.
        cur.execute("SELECT id, name FROM first")
        data = cur.fetchone()
        assert isinstance(data[0], int)
        assert data[1] == "henk"

        postgres.connection.commit()
