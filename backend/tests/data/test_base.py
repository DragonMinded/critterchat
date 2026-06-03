import pytest
from typing import cast

from sqlalchemy.engine import Engine

from critterchat.data.base import BaseData, ConnectionLike

from ..mocks import MockConfig


@pytest.mark.integration
class TestBase:
    def test_base_serdes(self, tx: ConnectionLike) -> None:
        """
        Tests basic serialization and deserialization including bytes.
        """

        config = MockConfig()
        basedata = BaseData(config, tx)

        # First, test round-tripping including bytes which JSON cannot normally serialize.
        original = {
            'str': 'string',
            'list': ['a', 'b', 'c'],
            'int': 5,
            'float': 3.3,
            'bytes': b'12345',
        }
        serialized = basedata.serialize(original)
        deserialized = basedata.deserialize(serialized)
        assert original == deserialized

        # Ensure that if null values get into the DB, we deserialize it to an empty JSON object.
        assert {} == basedata.deserialize(None)

    def test_commit_basic(self, db: Engine) -> None:
        """
        Tests that we emulate auto-commit behavior with the base connection and no transactions.
        """

        config = MockConfig()

        # Create a table and add some rows to it.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_basic (column1 VARCHAR(32), column2 VARCHAR(32))")
        first.execute("INSERT INTO test_basic (column1, column2) VALUES ('test1', 'test2')")
        firstconn.close()

        # Now, create another connection and ensure those rows exist.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        entries = list(second.execute("SELECT * FROM test_basic").mappings())
        assert len(entries) == 1
        assert entries[0] == {"column1": "test1", "column2": "test2"}
        secondconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_basic")
        finalconn.close()

    def test_commit_txn_basic(self, db: Engine) -> None:
        """
        Tests that we commit inside transactions as expected.
        """

        config = MockConfig()

        # Create a test table to operate on.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_txn (column1 VARCHAR(32), column2 VARCHAR(32))")
        firstconn.close()

        # Now, operate on the table in the second connection.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        second.execute("INSERT INTO test_txn (column1, column2) VALUES ('always1', 'always2')")
        with second.transaction():
            second.execute("INSERT INTO test_txn (column1, column2) VALUES ('test1', 'test2')")
        second.execute("INSERT INTO test_txn (column1, column2) VALUES ('always3', 'always4')")
        secondconn.close()

        # Now, create another connection and ensure those rows exist.
        thirdconn = db.connect()
        third = BaseData(config, cast(ConnectionLike, thirdconn))
        entries = list(third.execute("SELECT * FROM test_txn").mappings())
        assert len(entries) == 3
        assert entries[0] == {"column1": "always1", "column2": "always2"}
        assert entries[1] == {"column1": "test1", "column2": "test2"}
        assert entries[2] == {"column1": "always3", "column2": "always4"}
        thirdconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_txn")
        finalconn.close()

    def test_commit_txn_rollback(self, db: Engine) -> None:
        """
        Tests that we rollback inside transactions as expected.
        """

        config = MockConfig()

        # Create a test table to operate on.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_rollback (column1 VARCHAR(32), column2 VARCHAR(32))")
        firstconn.close()

        # Now, operate on the table in the second connection.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        second.execute("INSERT INTO test_rollback (column1, column2) VALUES ('always1', 'always2')")
        try:
            with second.transaction():
                second.execute("INSERT INTO test_rollback (column1, column2) VALUES ('test1', 'test2')")
                raise Exception("Should cause rollback!")
        except Exception:
            pass
        second.execute("INSERT INTO test_rollback (column1, column2) VALUES ('always3', 'always4')")
        secondconn.close()

        # Now, create another connection and ensure those rows exist.
        thirdconn = db.connect()
        third = BaseData(config, cast(ConnectionLike, thirdconn))
        entries = list(third.execute("SELECT * FROM test_rollback").mappings())
        assert len(entries) == 2
        assert entries[0] == {"column1": "always1", "column2": "always2"}
        assert entries[1] == {"column1": "always3", "column2": "always4"}
        thirdconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_rollback")
        finalconn.close()

    def test_commit_txn_nested_commit(self, db: Engine) -> None:
        """
        Tests that we commit inside transactions as expected.
        """

        config = MockConfig()

        # Create a test table to operate on.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_nested_commit (column1 VARCHAR(32), column2 VARCHAR(32))")
        firstconn.close()

        # Now, operate on the table in the second connection.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        second.execute("INSERT INTO test_nested_commit (column1, column2) VALUES ('always1', 'always2')")
        with second.transaction():
            second.execute("INSERT INTO test_nested_commit (column1, column2) VALUES ('test1', 'test2')")
            with second.transaction():
                second.execute("INSERT INTO test_nested_commit (column1, column2) VALUES ('test3', 'test4')")
            second.execute("INSERT INTO test_nested_commit (column1, column2) VALUES ('test5', 'test6')")
        second.execute("INSERT INTO test_nested_commit (column1, column2) VALUES ('always3', 'always4')")
        secondconn.close()

        # Now, create another connection and ensure those rows exist.
        thirdconn = db.connect()
        third = BaseData(config, cast(ConnectionLike, thirdconn))
        entries = list(third.execute("SELECT * FROM test_nested_commit").mappings())
        assert len(entries) == 5
        assert entries[0] == {"column1": "always1", "column2": "always2"}
        assert entries[1] == {"column1": "test1", "column2": "test2"}
        assert entries[2] == {"column1": "test3", "column2": "test4"}
        assert entries[3] == {"column1": "test5", "column2": "test6"}
        assert entries[4] == {"column1": "always3", "column2": "always4"}
        thirdconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_nested_commit")
        finalconn.close()

    def test_commit_txn_nested_inner_rollback(self, db: Engine) -> None:
        """
        Tests that we roll back inside transactions as expected.
        """

        config = MockConfig()

        # Create a test table to operate on.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_nested_inner_rollback (column1 VARCHAR(32), column2 VARCHAR(32))")
        firstconn.close()

        # Now, operate on the table in the second connection.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        second.execute("INSERT INTO test_nested_inner_rollback (column1, column2) VALUES ('always1', 'always2')")
        with second.transaction():
            second.execute("INSERT INTO test_nested_inner_rollback (column1, column2) VALUES ('test1', 'test2')")
            try:
                with second.transaction():
                    second.execute("INSERT INTO test_nested_inner_rollback (column1, column2) VALUES ('test3', 'test4')")
                    raise Exception("Should cause rollback!")
            except Exception:
                pass
            second.execute("INSERT INTO test_nested_inner_rollback (column1, column2) VALUES ('test5', 'test6')")
        second.execute("INSERT INTO test_nested_inner_rollback (column1, column2) VALUES ('always3', 'always4')")
        secondconn.close()

        # Now, create another connection and ensure those rows exist.
        thirdconn = db.connect()
        third = BaseData(config, cast(ConnectionLike, thirdconn))
        entries = list(third.execute("SELECT * FROM test_nested_inner_rollback").mappings())
        assert len(entries) == 4
        assert entries[0] == {"column1": "always1", "column2": "always2"}
        assert entries[1] == {"column1": "test1", "column2": "test2"}
        assert entries[2] == {"column1": "test5", "column2": "test6"}
        assert entries[3] == {"column1": "always3", "column2": "always4"}
        thirdconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_nested_inner_rollback")
        finalconn.close()

    def test_commit_txn_nested_outer_rollback(self, db: Engine) -> None:
        """
        Tests that we roll back inside transactions as expected.
        """

        config = MockConfig()

        # Create a test table to operate on.
        firstconn = db.connect()
        first = BaseData(config, cast(ConnectionLike, firstconn))
        first.execute("CREATE TABLE IF NOT EXISTS test_nested_outer_rollback (column1 VARCHAR(32), column2 VARCHAR(32))")
        firstconn.close()

        # Now, operate on the table in the second connection.
        secondconn = db.connect()
        second = BaseData(config, cast(ConnectionLike, secondconn))
        second.execute("INSERT INTO test_nested_outer_rollback (column1, column2) VALUES ('always1', 'always2')")
        try:
            with second.transaction():
                second.execute("INSERT INTO test_nested_outer_rollback (column1, column2) VALUES ('test1', 'test2')")
                with second.transaction():
                    second.execute("INSERT INTO test_nested_outer_rollback (column1, column2) VALUES ('test3', 'test4')")
                second.execute("INSERT INTO test_nested_outer_rollback (column1, column2) VALUES ('test5', 'test6')")
                raise Exception("Should cause rollback!")
        except Exception:
            pass
        second.execute("INSERT INTO test_nested_outer_rollback (column1, column2) VALUES ('always3', 'always4')")
        secondconn.close()

        # Now, create another connection and ensure those rows exist.
        thirdconn = db.connect()
        third = BaseData(config, cast(ConnectionLike, thirdconn))
        entries = list(third.execute("SELECT * FROM test_nested_outer_rollback").mappings())
        assert len(entries) == 2
        assert entries[0] == {"column1": "always1", "column2": "always2"}
        assert entries[1] == {"column1": "always3", "column2": "always4"}
        thirdconn.close()

        # Finally, clean up.
        finalconn = db.connect()
        final = BaseData(config, cast(ConnectionLike, finalconn))
        final.execute("DROP TABLE IF EXISTS test_nested_outer_rollback")
        finalconn.close()
