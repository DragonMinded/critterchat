import pytest
from sqlalchemy.orm import Session

from critterchat.data import MastodonInstance, NewMastodonInstanceID
from critterchat.data.mastodon import MastodonData

from ..mocks import MockConfig


@pytest.mark.integration
class TestMastodonData:
    def test_instance_crud(self, tx: Session) -> None:
        """
        Tests basic create, retrieve, update and delete of mastodon OAuth data tracking.
        """

        config = MockConfig()
        mastodondata = MastodonData(config, tx)

        # First, ensure that an empty DB returns an empty list of instances.
        assert [] == mastodondata.get_instances()

        # Now, store a new instance and retrieve it.
        newinstance = MastodonInstance(
            NewMastodonInstanceID,
            "https://example.com/",
            "client_id",
            "client_secret",
        )
        mastodondata.store_instance(newinstance)
        assert NewMastodonInstanceID != newinstance.id
        iid = newinstance.id

        instance = mastodondata.lookup_instance("https://example.com/")
        assert instance is not None
        assert instance.id == iid
        assert instance.base_url == "https://example.com/"
        assert instance.client_id == "client_id"
        assert instance.client_secret == "client_secret"

        instances = mastodondata.get_instances()
        assert len(instances) == 1
        assert instances[0].id == iid
        assert instances[0].base_url == "https://example.com/"
        assert instances[0].client_id == "client_id"
        assert instances[0].client_secret == "client_secret"

        # Also try looking up an invalid instance.
        instance = mastodondata.lookup_instance("https://example.com/invalid/")
        assert instance is None

        # Attempt to modify an instance.
        instance = mastodondata.lookup_instance("https://example.com/")
        assert instance is not None
        instance.client_secret = "another_secret"
        mastodondata.store_instance(instance)

        instance = mastodondata.lookup_instance("https://example.com/")
        assert instance is not None
        assert instance.id == iid
        assert instance.base_url == "https://example.com/"
        assert instance.client_id == "client_id"
        assert instance.client_secret == "another_secret"

        instances = mastodondata.get_instances()
        assert len(instances) == 1
        assert instances[0].id == iid
        assert instances[0].base_url == "https://example.com/"
        assert instances[0].client_id == "client_id"
        assert instances[0].client_secret == "another_secret"

        # Now, deactivate an instance and ensure we don't find it.
        instance = mastodondata.lookup_instance("https://example.com/")
        assert instance is not None
        mastodondata.deactivate_instance(instance)

        assert [] == mastodondata.get_instances()
        instance = mastodondata.lookup_instance("https://example.com/")
        assert instance is None
