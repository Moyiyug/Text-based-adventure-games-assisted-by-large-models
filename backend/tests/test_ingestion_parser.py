"""入库解析与切块单测（参照 IMPLEMENTATION_PLAN Phase 2.3-2.4）。"""

import tempfile
import unittest
from pathlib import Path

from app.services.ingestion.chunker import chunk_text, detect_chapters, detect_scenes
from app.services.ingestion.parser import parse_txt


class TestIngestionParser(unittest.TestCase):
    def test_parse_txt_utf8(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write("第一章 试读\n\n正文内容。")
            path = f.name
        try:
            text, warnings = parse_txt(path)
            self.assertIn("第一章", text)
            self.assertIn("正文", text)
            self.assertEqual(warnings, [])
        finally:
            Path(path).unlink(missing_ok=True)

    def test_detect_chapters(self) -> None:
        body = "第一章 开端\n\n段落A\n\n第二章 发展\n\n段落B"
        chapters = detect_chapters(body)
        self.assertGreaterEqual(len(chapters), 2)
        self.assertEqual(chapters[0].chapter_number, 1)

    def test_detect_scenes(self) -> None:
        text = "场景一\n\n场景二"
        scenes = detect_scenes(text)
        self.assertGreaterEqual(len(scenes), 1)

    def test_chunk_text_non_empty(self) -> None:
        chunks = chunk_text("段落一\n\n段落二\n\n段落三", max_tokens=50, overlap=5)
        self.assertTrue(all(c.strip() for c in chunks))


if __name__ == "__main__":
    unittest.main()
