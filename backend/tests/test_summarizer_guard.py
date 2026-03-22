"""摘要套话检测单元测试。"""

from app.services.ingestion.summarizer import is_junk_summary


def test_junk_summary_detects_prompt_reply() -> None:
    assert is_junk_summary("好的，请提供您需要摘要的具体场景描述。")


def test_junk_summary_accepts_normal() -> None:
    assert not is_junk_summary("和纱在深夜回家，发现英语书不见了。")


def test_junk_summary_empty() -> None:
    assert is_junk_summary("")
    assert is_junk_summary("   ")
