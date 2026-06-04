import os
import pytest
import tomllib
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text
from typing import Any, Generator

from critterchat.config import Config
from critterchat.data import Data, ConnectionLike

from .mocks import MockConfig


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


__mysql_config: Config | None = None


def mysql_config() -> Config:
    # Return cached config if needed.
    global __mysql_config
    if __mysql_config is not None:
        return __mysql_config

    # First, try to open any testdb.ini file in our directory.
    ini = os.path.join(TESTS_PATH, ".testdb.toml")
    if os.path.isfile(ini):
        with open(ini, "rb") as bfp:
            tomldata = tomllib.load(bfp)

        configdict: dict[str, object] = {**MockConfig()}
        if 'database' in tomldata:
            configdict['database'] = {'backend': 'mysql'}

            for key in ['address', 'database', 'user', 'password']:
                if key in tomldata['database']:
                    configdict['database'][key] = tomldata['database'][key]  # type: ignore

        # Create a config and use that to create the engine and a scoped session.
        config = Config(configdict)
        config["database"]["engine"] = Data.create_engine(config)

        __mysql_config = config

        return config

    else:
        # No config, so skip this test.
        pytest.skip(f'No .testdb.toml found in {TESTS_PATH}, cannot manage test DB!')


__sqlite_config: Config | None = None


def sqlite_config() -> Config:
    # Return cached config if needed.
    global __sqlite_config
    if __sqlite_config is not None:
        return __sqlite_config

    db = os.path.join(TESTS_PATH, ".testdb.db")
    os.remove(db)
    configdict: dict[str, object] = {
        **MockConfig(),
        **{
            "database": {
                'backend': 'sqlite',
                'file': db,
            },
        },
    }

    # Create a config and use that to create the engine and a scoped session.
    config = Config(configdict)
    config["database"]["engine"] = Data.create_engine(config)

    __sqlite_config = config

    return config


@pytest.fixture(scope="session", params=["mysql", "sqlite"])
def db(request: Any) -> Engine:
    if request.param == "mysql":
        config = mysql_config()
    elif request.param == "sqlite":
        config = sqlite_config()
    else:
        raise NotImplementedError(f"No support for db fixture of type {request.param}")

    with config.database.engine.connect() as conn:
        if request.param == "mysql":
            # Now, need to drop all existing tables and recreate so we ensure the test DB is in a known state.
            cursor = conn.execute(
                text("""
                    SELECT concat('DROP TABLE IF EXISTS `', table_name, '`;') AS cmd
                    FROM information_schema.tables
                    WHERE table_schema = :schema;
                """),
                {'schema': config.database.database},
            )
            cmds = "SET FOREIGN_KEY_CHECKS = 0;"
            for result in cursor.mappings():
                cmd = result['cmd']
                cmds += cmd
            conn.execute(text(cmds))
            conn.commit()
        elif request.param == "sqlite":
            # Don't need to drop for sqlite because we delete the DB at the beginning of the run and recreate.
            pass

        data = Data(config, conn)
        data.create()

        conn.commit()
        conn.close()

    return config.database.engine


@pytest.fixture(scope="function")
def config(db: Engine) -> Config:
    dialect = db.name
    if dialect == "mysql":
        config = mysql_config()
    elif dialect == "sqlite":
        config = sqlite_config()
    else:
        raise NotImplementedError(f"No support for db fixture of type {dialect}")

    return config


@pytest.fixture(scope="function")
def tx(config: Config, db: Engine) -> Generator[ConnectionLike, None, None]:
    with db.connect() as conn:
        # Create a transaction for this test, make sure lock bugs don't take forever to time out.
        if config.database.backend == "mysql":
            conn.execute(text("SET SESSION innodb_lock_wait_timeout = 1;"))

        try:
            # Yield it for use.
            yield conn

        finally:
            # Nuke all test data so we don't pollute other tests.
            if config.database.backend == "mysql":
                cursor = conn.execute(
                    text("""
                        SELECT concat('`', table_name, '`') AS table_name
                        FROM information_schema.tables
                        WHERE table_schema = :schema;
                    """),
                    {'schema': config.database.database},
                )
                cmds = ["SET FOREIGN_KEY_CHECKS = 0;"]
                for result in cursor.mappings():
                    cmds.append(f"DELETE FROM {result['table_name']};")

            elif config.database.backend == "sqlite":
                cursor = conn.execute(
                    text("""
                        SELECT concat('`', name, '`') AS table_name
                        FROM sqlite_master WHERE type = 'table';
                    """),
                )
                cmds = ["PRAGMA foreign_keys = OFF;"]
                for result in cursor.mappings():
                    cmds.append(f"DELETE FROM {result['table_name']};")

            else:
                raise NotImplementedError(f"Unsupported database backend {config.database.backend}")

            for cmd in cmds:
                conn.execute(text(cmd))
                conn.commit()
