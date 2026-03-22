import pytest
from sqlalchemy.orm import Session

from critterchat.data.base import BaseData

from ..mocks import MockConfig


@pytest.mark.integration
class TestBase:
    def test_base_serdes(self, tx: Session) -> None:
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
