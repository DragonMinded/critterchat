import pytest

from critterchat.data import ConnectionLike, MastodonInstance, NewMastodonInstanceID
from critterchat.data.mastodon import MastodonData
from critterchat.data.user import UserData

from ..mocks import MockConfig


@pytest.mark.integration
class TestMastodonData:
    def test_instance_crud(self, tx: ConnectionLike) -> None:
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

    def test_instance_user_linking(self, tx: ConnectionLike) -> None:
        """
        Tests setting and retrieving user links for remote OAuth accounts.
        """

        config = MockConfig()
        mastodondata = MastodonData(config, tx)
        userdata = UserData(config, tx)

        # We need some users for this.
        user1 = userdata.create_account('instance_linking_test_1', 'best_password')
        assert user1 is not None
        user2 = userdata.create_account('instance_linking_test_2', 'best_password')
        assert user2 is not None

        # We also need an instance for this.
        newinstance = MastodonInstance(
            NewMastodonInstanceID,
            "https://example.com/linking/",
            "client_id",
            "client_secret",
        )
        mastodondata.store_instance(newinstance)
        assert NewMastodonInstanceID != newinstance.id

        # First, verify that we don't have any links.
        userid = mastodondata.lookup_account_link("https://example.com/linking/", "username")
        assert userid is None
        userid = mastodondata.lookup_account_link("https://example.com/invalid/", "username")
        assert userid is None

        # Now, link to the instance, verify we can grab it.
        mastodondata.store_account_link("https://example.com/linking/", "username", user1.id)
        mastodondata.store_account_link("https://example.com/linking/", "another", user2.id)
        userid = mastodondata.lookup_account_link("https://example.com/linking/", "username")
        assert userid == user1.id
        userid = mastodondata.lookup_account_link("https://example.com/linking/", "another")
        assert userid == user2.id
        userid = mastodondata.lookup_account_link("https://example.com/invalid/", "username")
        assert userid is None

        # Also try linking to an invalid instance, make sure it doesn't work.
        mastodondata.store_account_link("https://example.com/invalid/", "username", user1.id)
        userid = mastodondata.lookup_account_link("https://example.com/linking/", "username")
        assert userid == user1.id
        userid = mastodondata.lookup_account_link("https://example.com/invalid/", "username")
        assert userid is None
