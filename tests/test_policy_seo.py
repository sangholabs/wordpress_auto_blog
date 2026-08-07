import socket

import pytest

from src import policy_package, policy_seo


def _manifest():
    keyword = "직장인 돌봄 지원"
    headings = [
        "내가 대상인지 빠른 체크", "받을 수 있는 혜택", "제외 조건과 중복 지원 주의사항",
        "신청기간과 놓치면 안 되는 날짜", "온라인·오프라인 신청 순서", "구비서류와 문의처",
        "30~50대 주부·직장인이 자주 놓치는 경우", "자주 묻는 질문", "신청 전 최종 체크리스트",
    ]
    markdown = keyword + " 대상과 혜택, 신청방법을 기준일 현재 공식 자료로 확인합니다.\n\n"
    markdown += "\n\n".join(
        f"## {heading}\n\n" + ("공식 자료를 확인하고 본인 조건에 맞는지 차근차근 점검합니다. " * 8)
        for heading in headings
    )
    draft = {
        "primary_keyword": keyword, "secondary_keywords": ["돌봄", "맞벌이", "정부혜택"],
        "search_intent": "신청방법", "suggested_slug": "직장인-돌봄-지원",
        "markdown": markdown,
        "tags": ["돌봄", "직장인", "정부지원", "맞벌이", "자녀돌봄", "생활혜택", "신청방법", "복지정책"],
        "image_briefs": [
            {"slot": "featured", "alt": "가족이 지원을 확인하는 모습", "caption": "지원 확인"},
            {"slot": "body1", "alt": "대상을 확인하는 직장인", "caption": "대상 확인"},
            {"slot": "body2", "alt": "온라인으로 신청하는 모습", "caption": "온라인 신청"},
        ],
    }
    return {
        "title": "직장인 돌봄 지원 대상과 신청방법, 놓치기 쉬운 혜택 총정리",
        "meta_description": "직장인 돌봄 지원 대상과 받을 수 있는 혜택, 신청기간, 온라인·오프라인 신청방법과 구비서류를 공식 자료 기준으로 한눈에 정리했습니다.",
        "category": "자녀·교육·돌봄", "draft": draft,
        "current_images": {"featured": "a.jpg", "body1": "b.jpg", "body2": "c.jpg"},
        "source": {
            "official_title": keyword, "source_url": "https://www.gov.kr/test",
            "checked_at": "2026-08-05T09:00:00+09:00", "agency": "고용노동부",
        },
    }


def test_local_seo_audit_scores_complete_package():
    manifest = _manifest()
    body = policy_package._portable_html(manifest["draft"]["markdown"])
    full = f'<article style="{policy_package.ARTICLE_STYLE}">{body}{policy_package._source_footer(manifest)}</article>'
    result = policy_seo.audit_local(manifest, full)
    assert result["status"] == "pass"
    assert result["score"] >= 80
    assert result["h1_in_body"] is False
    assert len(result["heading_outline"]) == 9


def test_local_seo_accepts_separate_featured_and_two_supabase_body_images():
    manifest = _manifest()
    manifest["supabase"] = {
        "enabled": True,
        "configured": True,
        "images": {
            "featured": {"local_path": "a.jpg", "public_url": "https://x.test/featured.jpg"},
            "body1": {"local_path": "b.jpg", "public_url": "https://x.test/body1.jpg"},
            "body2": {"local_path": "c.jpg", "public_url": "https://x.test/body2.jpg"},
        },
    }
    body = policy_package._image_placeholders(
        policy_package._portable_html(manifest["draft"]["markdown"]), manifest,
    )
    full = f'<article style="{policy_package.ARTICLE_STYLE}">{body}{policy_package._source_footer(manifest)}</article>'
    assert "https://x.test/featured.jpg" not in full
    assert "https://x.test/body1.jpg" in full
    assert "https://x.test/body2.jpg" in full
    result = policy_seo.audit_local(manifest, full)
    check = next(item for item in result["checks"] if item["code"] == "supabase_images")
    assert check["passed"] is True


def test_published_seo_audit_checks_meta_and_placeholders():
    good = """<!doctype html><html><head><title>정책 제목</title>
    <meta name="description" content="설명"><meta name="viewport" content="width=device-width">
    <meta property="og:title" content="정책"><meta property="og:description" content="설명"><meta property="og:image" content="https://x.test/a.jpg">
    <link rel="canonical" href="https://blog.tistory.com/1"></head><body><h1>정책 제목</h1><img src="https://x.test/a.jpg" alt="대표"></body></html>"""
    result = policy_seo.audit_published_html(good, "https://blog.tistory.com/1", 200)
    assert result["status"] == "pass"

    bad = '<html><head><meta name="robots" content="noindex"></head><body><div data-policy-image-slot="body1"></div></body></html>'
    failed = policy_seo.audit_published_html(bad, "https://blog.tistory.com/1", 200)
    assert failed["status"] == "fail"
    assert "게시 본문에 이미지 업로드 자리 표시가 남아 있습니다." in failed["issues"]


def test_published_supabase_figure_is_not_treated_as_placeholder():
    page = """<!doctype html><html><head><title>정책 제목</title>
    <meta name="description" content="설명"><meta name="viewport" content="width=device-width">
    <meta property="og:title" content="정책"><meta property="og:description" content="설명"><meta property="og:image" content="https://x.test/a.jpg">
    <link rel="canonical" href="https://blog.tistory.com/1"></head><body><h1>정책 제목</h1>
    <figure data-policy-image-slot="body1" data-policy-image-source="supabase"><img src="https://x.test/a.jpg" alt="본문"></figure>
    </body></html>"""
    result = policy_seo.audit_published_html(page, "https://blog.tistory.com/1", 200)
    check = next(item for item in result["checks"] if item["code"] == "image_placeholders")
    assert check["passed"] is True


def test_local_affiliate_disclosure_uses_dom_order_not_serialized_html():
    manifest = _manifest()
    body = policy_package._portable_html(manifest["draft"]["markdown"])
    disclosure = '<div>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 받습니다.</div>'
    ad = '<a href="https://link.coupang.com/a/test" rel="nofollow sponsored">상품</a>'
    full = f'<article>{disclosure}{body}{ad}{policy_package._source_footer(manifest)}</article>'
    result = policy_seo.audit_local(manifest, full)
    check = next(item for item in result["checks"] if item["code"] == "affiliate_disclosure")
    assert check["passed"] is True


def test_published_url_blocks_private_network(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="내부·로컬"):
        policy_seo._public_https_url("https://example.com/post")
