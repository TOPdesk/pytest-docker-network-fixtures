# Fixtures
# noinspection PyUnresolvedReferences
from pytest_docker_network_fixtures.core_fixtures import (
    dockertester,
    dockertester_config,
    docker_image_manager,
)
from pytest_docker_network_fixtures.databases import mongodb, postgres, mssql_2019


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
