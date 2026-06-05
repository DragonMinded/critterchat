import pytest
from typing import Final

from critterchat.config import Config
from critterchat.data.data import Data, DBCreateException
from critterchat.data.base import ConnectionLike


@pytest.mark.integration
class TestAlembic:
    # Number of rollbacks we will try to perform. Needs to be high enough to possibly
    # grab a few DB migrations for a single user that hasn't run tests in awhile, but
    # also not so high as to take forever.
    NUM_ROLLBACKS: Final[int] = 5

    def test_rollback_rollforward(self, config: Config, tx: ConnectionLike) -> None:
        """
        Tests that the last couple of database migrations can be rolled back and forward on
        all DB drivers we support. Helps to prevent migrations that only work on a subset
        of backends.
        """

        data = Data(config, tx)

        # Roll back individual tags up until the number of rollbacks. If one of these
        # fails then that means your migration rollback isn't compatible with the database
        # backkend that is being run through the test and you'll need to adjust it to be
        # compatible.
        for _ in range(self.NUM_ROLLBACKS):
            data.downgrade("-1")

        # Roll forward again and ensure we have no changes to the DB. If this fails that
        # means that one of your migrations is not compatible with the database backend
        # that is being run through the test and you'll need to adjust it to be compatible.
        data.upgrade()

        # If this fails to throw an exception that means that the process of rolling back
        # and forward was not idempotent and alembic thinks there's a change that needs to
        # happen. You should ensure that your migrations are fully reversible.
        with pytest.raises(DBCreateException) as e:
            data.generate("This should not succeed", False)

        assert str(e.value) == "There is nothing different between code and the DB, refusing to create migration!"
