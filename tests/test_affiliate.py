from src import affiliate, formatter


def test_shared_affiliate_renderer_is_safe_and_sponsored():
    block = affiliate.cards_html([{
        "name": "정리함 <특가>", "url": "https://example.com/?a=1&b=2",
        "image": "https://example.com/image.jpg?a=1&b=2", "price": 12300,
    }])
    assert "정리함 &lt;특가&gt;" in block
    assert "nofollow sponsored" in block
    assert "12,300원" in block


def test_wordpress_formatter_uses_shared_product_renderer(monkeypatch):
    monkeypatch.setattr(affiliate, "products_for", lambda keyword: [{
        "name": "상품", "url": "https://example.com/product", "image": "", "price": 1000,
    }])
    post = {
        "keyword": "생활용품", "markdown": "# 제목\n\n> 메타설명: 설명\n\n## 선택 기준\n\n설명입니다.\n\n[[PRODUCTS]]"
    }
    rendered = formatter.to_html(post)
    assert "nofollow sponsored" in rendered
    assert "1,000원" in rendered
