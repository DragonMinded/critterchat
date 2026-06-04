import pytest

from critterchat.config import Config
from critterchat.data import ConnectionLike, Migration
from critterchat.data.migration import MigrationData


@pytest.mark.integration
class TestMigrationData:
    def test_migration_mark_and_retrieve(self, config: Config, tx: ConnectionLike) -> None:
        """
        Tests basic marking and retrieval of previously marked migrations.
        """

        migrationdata = MigrationData(config, tx)

        # First, ensure that an empty DB returns an empty list of migrations.
        assert set() == migrationdata.get_migrations()

        # Now, flag a migration, ensure we get that in the list.
        migrationdata.flag_migrated(Migration.ATTACHMENT_EXTENSIONS)
        assert {Migration.ATTACHMENT_EXTENSIONS} == migrationdata.get_migrations()

        # Now, flag the same migration, ensure it doesn't crash.
        migrationdata.flag_migrated(Migration.ATTACHMENT_EXTENSIONS)
        assert {Migration.ATTACHMENT_EXTENSIONS} == migrationdata.get_migrations()

        # Finally, flag another migration and make sure we get both back.
        migrationdata.flag_migrated(Migration.IMAGE_DIMENSIONS)
        assert {Migration.ATTACHMENT_EXTENSIONS, Migration.IMAGE_DIMENSIONS} == migrationdata.get_migrations()
