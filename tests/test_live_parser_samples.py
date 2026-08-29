import json
from pathlib import Path
import unittest

from configs.general_constants import DOMAIN_TO_NAME


SAMPLES_PATH = Path(__file__).with_name("live_parser_samples.json")


class LiveParserSamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))["cases"]

    def test_every_configured_platform_has_sample_entries(self):
        configured_platforms = set(DOMAIN_TO_NAME.values())
        sample_platforms = [case["platform"] for case in self.cases]
        self.assertEqual(set(sample_platforms), configured_platforms)
        self.assertGreaterEqual(len(sample_platforms), len(configured_platforms))

    def test_sample_entries_follow_the_schema(self):
        valid_fields = {"video", "audio", "cover", "title", "author", "images", "live_media"}
        for case in self.cases:
            with self.subTest(platform=case["platform"]):
                self.assertIsInstance(case.get("url"), (str, type(None)))
                self.assertTrue(case.get("media_types"))
                self.assertTrue(case.get("expected_fields"))
                self.assertTrue(set(case["expected_fields"]).issubset(valid_fields))


if __name__ == "__main__":
    unittest.main()
