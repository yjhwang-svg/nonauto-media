import unittest

from utils.upload_policy import should_upload


class UploadPolicyTests(unittest.TestCase):
    def test_uploads_when_no_errors_exist(self):
        self.assertTrue(should_upload([]))

    def test_skips_upload_when_errors_exist_by_default(self):
        self.assertFalse(should_upload(["RTB House 오류: login failed"]))

    def test_allows_partial_upload_when_explicitly_enabled(self):
        self.assertTrue(should_upload(["Buzzvil 데이터 없음"], allow_partial=True))


if __name__ == "__main__":
    unittest.main()
