from pathlib import Path

from src import policy_pages


def test_tistory_required_pages_are_copy_ready_utf8(monkeypatch, tmp_path):
    output = tmp_path / "pages"
    monkeypatch.setattr(policy_pages, "OUTPUT_ROOT", output)
    values = {
        "TISTORY_SITE_NAME": "생활정책 안내소",
        "TISTORY_SITE_OWNER": "홍길동",
        "TISTORY_SITE_EMAIL": "owner@example.com",
    }
    monkeypatch.setattr(policy_pages, "env", lambda key, default="": values.get(key, default))

    result = policy_pages.create_required_pages_package()

    assert result == output
    assert (output / "00_게시가이드.txt").read_bytes().startswith(b"\xef\xbb\xbf")
    for folder in ("01_소개", "02_개인정보처리방침", "03_문의"):
        html_file = output / folder / "02_HTML블록용.txt"
        assert html_file.exists()
        assert html_file.read_bytes().startswith(b"\xef\xbb\xbf")
        assert "<article" in html_file.read_text(encoding="utf-8-sig")
    assert "생활정책 안내소" in (output / "01_소개" / "02_HTML블록용.txt").read_text(encoding="utf-8-sig")
    assert "owner@example.com" in (output / "03_문의" / "02_HTML블록용.txt").read_text(encoding="utf-8-sig")
