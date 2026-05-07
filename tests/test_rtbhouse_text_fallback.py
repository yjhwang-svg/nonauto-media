import unittest

from crawlers.rtbhouse import _parse_visible_text_row


class RTBHouseVisibleTextFallbackTests(unittest.TestCase):
    def test_parses_row_from_visible_table_text(self):
        body_text = """
        Date (UTC±0:00)
        Imps
        Clicks
        CTR
        Cost (KRW)
        Convs.
        2026-05-06
        106 030
        19 832
        18.70 %
        313 730.44
        424
        2026-05-05
        109 362
        21 072
        19.27 %
        319 808.82
        409
        """

        self.assertEqual(
            _parse_visible_text_row(body_text, "2026-05-05"),
            {"imps": 109362, "clicks": 21072, "cost": 319809},
        )


if __name__ == "__main__":
    unittest.main()
