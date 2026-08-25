from __future__ import annotations

import unittest
from pathlib import Path

from prism_cli import build_parser


class PrismCliContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = build_parser()
        self.fixture = str(Path(__file__).resolve())

    def test_mature_platform_image_post_contracts(self) -> None:
        for platform in ("douyin", "kuaishou", "xiaohongshu"):
            args = self.parser.parse_args(
                [platform, "upload-note", "--account", "creator", "--images", self.fixture, "--title", "title"]
            )
            self.assertEqual(args.platform, platform)
            self.assertEqual(args.action, "upload-note")

    def test_youtube_accepts_only_its_special_fields(self) -> None:
        args = self.parser.parse_args(
            [
                "youtube", "upload-video", "--account", "creator", "--file", self.fixture,
                "--title", "title", "--playlist", "series", "--visibility", "unlisted",
            ]
        )
        self.assertEqual(args.playlist, "series")
        self.assertEqual(args.visibility, "unlisted")
        self.assertFalse(hasattr(args, "schedule"))

    def test_qr_probe_is_a_login_only_contract(self) -> None:
        args = self.parser.parse_args(["douyin", "login", "--account", "qr_probe", "--qr-only"])
        self.assertTrue(args.qr_only)

    def test_all_platforms_have_video_cli(self) -> None:
        extra = {"bilibili": ["--tid", "249"]}
        for platform in (
            "douyin", "kuaishou", "xiaohongshu", "bilibili",
            "channels", "baijiahao", "tiktok", "youtube",
        ):
            args = self.parser.parse_args(
                [platform, "upload-video", "--account", "creator", "--file", self.fixture, "--title", "title", *extra.get(platform, [])]
            )
            self.assertEqual(args.action, "upload-video")


if __name__ == "__main__":
    unittest.main()
