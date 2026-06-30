<?php
// 쿠팡 다이나믹 배너를 [coupang_dynamic_banner] 숏코드로 출력한다.
// 본문엔 숏코드만 들어가므로 보안 방화벽(NinjaFirewall 등)에 막히지 않는다.
//
// 설치 방법(둘 중 하나).
//  1) "Code Snippets" 플러그인 설치 → 새 스니펫에 아래 전체를 붙여넣고 활성화(추천, 안전).
//  2) 자식 테마 functions.php 맨 아래에 add_shortcode(...) 부분을 붙여넣기.
//
// 아래 <script> 두 줄을 본인 쿠팡 파트너스 다이나믹 배너 코드로 교체한다(id, trackingCode).

add_shortcode('coupang_dynamic_banner', function () {
    ob_start(); ?>
<div style="text-align:center;margin:24px 0;">
<script src="https://ads-partners.coupang.com/g.js"></script>
<script>
new PartnersCoupang.G({"id":0,"template":"carousel","trackingCode":"YOUR_TAG","width":"300","height":"250","tsource":""});
</script>
</div>
<?php
    return ob_get_clean();
});
