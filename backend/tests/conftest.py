import os
import pytest
import tomllib
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from typing import Generator

from critterchat.config import Config
from critterchat.data import Data


TESTS_PATH = os.path.dirname(os.path.realpath(__file__))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Function]) -> None:
    TYPES: list[str] = ["unit", "integration"]

    for item in items:
        if any(item.get_closest_marker(m) for m in TYPES):
            continue

        # This test doesn't have a unit or integration marker!
        insns = ", ".join(f"@pytest.mark.{t}" for t in TYPES)
        raise Exception(
            f"{item.location[0]}:{item.location[1]}: {item.location[2]} is missing a marker for test type! Please decorate your function or class with one of the following: {insns}"
        )


@pytest.fixture(scope="session")
def db() -> Engine:
    # First, try to open any testdb.ini file in our directory.
    ini = os.path.join(TESTS_PATH, ".testdb.toml")
    if os.path.isfile(ini):
        with open(ini, "rb") as bfp:
            tomldata = tomllib.load(bfp)

        configdict: dict[str, object] = {}
        if 'database' in tomldata:
            configdict['database'] = {}

            for key in ['address', 'database', 'user', 'password']:
                if key in tomldata['database']:
                    configdict['database'][key] = tomldata['database'][key]  # type: ignore

        # Create a config and use that to create the engine and a scoped session.
        config = Config(configdict)
        config["database"]["engine"] = Data.create_engine(config)

        session = Session(config.database.engine)

        # Now, need to drop all existing tables and recreate so we ensure the test DB is in a known state.
        cursor = session.execute(
            text("""
                SELECT concat('DROP TABLE IF EXISTS `', table_name, '`;') AS cmd
                FROM information_schema.tables
                WHERE table_schema = :schema;
            """),
            {'schema': config.database.database},
        )
        for result in cursor.mappings():
            cmd = result['cmd']
            session.execute(
                text(f"""
                    SET FOREIGN_KEY_CHECKS = 0;
                    {cmd}
                """)
            )

        data = Data(config, session)
        data.create()

        session.commit()
        session.close()

        return config.database.engine

    else:
        # No config, so skip this test.
        pytest.skip(f'No .testdb.toml found in {TESTS_PATH}, cannot manage test DB!')


@pytest.fixture(scope="function")
def tx(db: Engine) -> Generator[Session, None, None]:
    session = Session(db, autoflush=True)

    # Create a transaction for this test.
    session.begin()
    try:
        # Yield it for use.
        yield session

    finally:
        # Roll it back so we don't pollute tests.
        session.rollback()
        session.close()
