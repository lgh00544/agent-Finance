import pytest

from app.services import paper_web


def test_ssrf_private_and_non_http_urls_are_rejected(monkeypatch):
    monkeypatch.setattr(paper_web.socket, "getaddrinfo",
                        lambda *args, **kwargs: [(0, 0, 0, "", ("10.0.0.1", 80))])
    with pytest.raises(ValueError, match="禁止访问"):
        paper_web._public_host("http://example.com/")
    with pytest.raises(ValueError, match="http/https"):
        paper_web._public_host("file:///etc/passwd")


def test_fetch_marks_external_evidence_and_bounds_content(monkeypatch):
    created = {}
    monkeypatch.setattr(paper_web, "_download",
                        lambda url: ("example.com", "https://example.com/", b"<title>X</title>safe text", "utf-8", []))
    monkeypatch.setattr(paper_web.repo, "create_paper_web_evidence",
                        lambda account, day, code, values: (created.update(values) or 4))
    result = paper_web.fetch(1, paper_web._today(), "https://example.com/")
    assert result["status"] == "ok"
    assert result["trust"] == "external_evidence_only"
    assert result["is_instruction"] is False
    assert result["content_hash"]
    assert created["title"] == "X"


def test_fetch_rejects_historical_web_date():
    with pytest.raises(ValueError, match="当天"):
        paper_web.fetch(1, "2026-09-08", "https://example.com/")

