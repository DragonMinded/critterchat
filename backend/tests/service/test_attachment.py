import pytest

from critterchat.config import Config
from critterchat.data import (
    ConnectionLike,
    Data,
)
from critterchat.service.attachment import AttachmentService


@pytest.mark.integration
class TestAttachmentService:
    def test_filename_sanitization(self, config: Config, tx: ConnectionLike) -> None:
        """
        Tests that we properly sanitize user filenames before using them as part of attachments.
        """

        data = Data(config, tx)
        ats = AttachmentService(config, data)

        assert ats._sanitize_filename("") is None
        assert ats._sanitize_filename(None) is None
        assert ats._sanitize_filename(".") is None
        assert ats._sanitize_filename("..") is None
        assert ats._sanitize_filename(" ") is None
        assert ats._sanitize_filename(" test ") == "test"
        assert ats._sanitize_filename("test.") == "test"
        assert ats._sanitize_filename("test..") == "test"
        assert ats._sanitize_filename("test.mp3") == "test.mp3"
        assert ats._sanitize_filename("<test>.mp3") == "test.mp3"
        assert ats._sanitize_filename("[test].mp3") == "[test].mp3"
        assert ats._sanitize_filename("test\0file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test\\file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test/file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test:file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test*file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test?file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test\"file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test|file.mp3") == "testfile.mp3"
        assert ats._sanitize_filename("test file.mp3") == "test_file.mp3"
        assert ats._sanitize_filename("TestFile.MP3") == "TestFile.mp3"
