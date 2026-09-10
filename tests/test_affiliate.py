import pytest

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
    monkeypatch.setattr(affiliate, "products_for", lambda keyword, **kwargs: [{
        "name": "상품", "url": "https://example.com/product", "image": "", "price": 1000,
    }])
    post = {
        "keyword": "생활용품", "markdown": "# 제목\n\n> 메타설명: 설명\n\n## 선택 기준\n\n설명입니다.\n\n[[PRODUCTS]]"
    }
    rendered = formatter.to_html(post)
    assert "nofollow sponsored" in rendered
    assert "1,000원" in rendered


def test_tistory_rocket_filter_excludes_unverified_products(monkeypatch):
    monkeypatch.setattr(affiliate, "search_products", lambda keyword, **kwargs: [
        {"name": "로켓", "rocket": True}, {"name": "일반"},
    ])
    products = affiliate.products_for("생활용품", options={"rocket_only": True})
    assert [item["name"] for item in products] == ["로켓"]


def test_manual_coupang_product_link_is_validated_and_sponsored():
    url = "https://link.coupang.com/a/abc123?traceid=test&subid=one"
    block = affiliate.coupang_product_cta("임산부 방석 <추천>", url)
    assert "link.coupang.com/a/abc123?traceid=test&amp;subid=one" in block
    assert "임산부 방석 &lt;추천&gt;" in block
    assert 'rel="nofollow sponsored noopener"' in block
    assert 'data-policy-coupang-product-link="true"' in block
    assert affiliate.is_partners_tracking_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://link.coupang.com/a/no-https",
        "https://link.coupang.com.evil.example/a/fake",
        "https://example.com/product",
    ],
)
def test_manual_coupang_product_link_rejects_unsafe_domains(url):
    with pytest.raises(ValueError):
        affiliate.normalize_coupang_product_urls([url])


@pytest.mark.parametrize(
    ("source", "asset_type", "size"),
    [
        (
            '<a href="https://link.coupang.com/a/category" target="_blank"><img '
            'src="https://ads-partners.coupang.com/banners/1014203?w=728&h=90" alt=""></a>,',
            "category-banner", (728, 90),
        ),
        (
            '<iframe src="https://ads-partners.coupang.com/widgets.html?id=1014203&width=728&height=90" '
            'width="728" height="90" frameborder="0"></iframe>,',
            "category-banner-iframe", (728, 90),
        ),
        (
            '<script src="https://ads-partners.coupang.com/g.js"></script><script>'
            'new PartnersCoupang.G({"id":123456,"trackingCode":"AF0000000","subId":null,'
            '"template":"carousel","width":300,"height":250});</script>',
            "dynamic-banner", (300, 250),
        ),
        (
            '<iframe src="https://coupa.ng/example" width="120" height="240" frameborder="0"></iframe>,',
            "product-banner-iframe", (120, 240),
        ),
        (
            '<a href="https://link.coupang.com/a/product" target="_blank"><img '
            'src="https://image8.coupangcdn.com/image/affiliate/banner/product.jpg" '
            'alt="파워에이드 제로" width="120" height="240"></a>,',
            "product-banner", (120, 240),
        ),
    ],
)
def test_coupang_partner_asset_formats_are_parsed_and_responsive(source, asset_type, size):
    asset = affiliate.parse_coupang_asset(source)
    assert asset["type"] == asset_type
    assert (asset["width"], asset["height"]) == size
    rendered = affiliate.render_coupang_asset(asset, "추천 상품")
    assert f'data-policy-coupang-size="{size[0]}x{size[1]}"' in rendered
    assert "max-width:100%" in rendered or "width:100%" in rendered


def test_coupang_asset_rejects_arbitrary_script():
    with pytest.raises(ValueError):
        affiliate.parse_coupang_asset('<script src="https://evil.example/a.js"></script>')
