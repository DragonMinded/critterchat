import pytest
from sqlalchemy.orm import Session

from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestUserData:
    def test_user_crud(self, tx: Session) -> None:
        config = MockConfig()
        userdata = UserData(config, tx)

        # First, create the user
        user = userdata.create_account('test_user_crud', 'some_arbitrary_password')
        assert user is not None

        # Now, attempt to look up the user by both ID and username.
        by_id = userdata.get_user(user.id)
        by_username = userdata.from_username('test_user_crud')

        assert by_id is not None
        assert user.id == by_id.id
        assert by_username is not None
        assert user.id == by_username.id

        # Now, verify user modifications.
        assert user.nickname == "test_user_crud"
        user.nickname = "updated_nickname"
        userdata.update_user(user)

        # Make sure that it reflects in the data.
        by_id = userdata.get_user(user.id)
        assert by_id is not None
        assert by_id.nickname == "updated_nickname"

        assert user.nickname == "updated_nickname"
        user.nickname = ""
        userdata.update_user(user)
        assert user.nickname == "test_user_crud"

        by_id = userdata.get_user(user.id)
        assert by_id is not None
        assert by_id.nickname == "test_user_crud"

        # No delete because we don't support user deletion since that would screw history.
