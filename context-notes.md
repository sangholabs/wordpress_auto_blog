# 컨텍스트 노트 (결정 기록)

작업 중 내린 결정과 근거를 계속 누적한다. 다음 세션(사람/에이전트)이 재추론 없이 이어받기 위함이다.

## 2026-08-04 macOS 터미널 지원

- 결정: Windows 지원을 유지하면서 macOS를 동등한 실행 대상으로 추가한다. 핵심 파이프라인은 공용으로 두고 예약·프로세스 실행만 플랫폼별로 분기한다.
- macOS 예약 방식: 시스템 전역 권한이 필요한 LaunchDaemon이 아닌 사용자 LaunchAgent. `StartCalendarInterval`로 매일 실행하고 등록 즉시 실행하는 `RunAtLoad`는 사용하지 않는다.
- launchd는 터미널의 PATH를 자동 상속하지 않으므로 등록 시 현재 PATH를 plist에 기록한다. Node/Claude 설치 경로가 바뀌면 사용자가 다시 등록해야 한다.
- 공식 진입점: Windows `제어판.bat`/`run.bat`, macOS `control.sh`/`run.sh`. 예약 공통 API는 `python -m src.schedule_task on|off|status`다.
- 자동 테스트에서는 실제 WordPress 게시나 LLM 호출을 하지 않고, Windows 명령·macOS plist·launchctl 호출을 모킹해 검증한다.

## 2026-06-30 초기 설계

### 니치
- 결정: 메인 니치를 '생활/리빙·가전'으로 단일 집중.
- 근거: 신규 블로그는 토픽 권위 확보를 위해 한 주제 집중이 SEO에 유리하다. 1·2·3 동시 시작은 분산되어 초기 색인·유입에 불리. 생활/가전은 쿠팡 전환율이 가장 높고 검색량·키워드 다양성이 크다. IT/뷰티는 트래픽 안정화 후 확장.

### 산출물 형태
- 결정: 독립 프로젝트(Python) + cron. Skill/MCP 아님.
- 근거: 키워드 수집·게시 등 반복작업은 매 실행마다 LLM 토큰을 쓰면 낭비. 순수 스크립트로 돌리면 0토큰. Skill로 묶으면 매 실행에 Claude 토큰 소모(비효율). clone→실행 배포에도 독립 프로젝트가 가장 적합.

### LLM 비용 (중요)
- 사실: 2026-02 정책으로 Free/Pro/Max OAuth 토큰은 Agent SDK에 사용 불가(API 키 필요). 2026-06-15부터 `claude -p`(cron/헤드리스)는 구독 한도가 아닌 별도 크레딧 풀(API 요금)로 분리 예정이며 현재 일시 중단/유동적.
- 결론: 무인 cron 글 생성을 '구독 OAuth 무료'로 안정 운영하기 어렵다. → LLM provider 추상화 레이어를 두고 Gemini 무료 등급(대량) + Claude API(프리미엄 글) 하이브리드. 월 예산 가드레일(`MONTHLY_LLM_BUDGET_USD`)로 상한.
- 결정(2026-06-30): 사용자가 Claude 구독 인증 경로를 선택. 최근 다른 프로젝트에서 SDK로 직접 운용한 경험 있음(개인 사용). → 기본 provider = `claude_code`(로컬 Claude Code CLI `claude -p` 헤드리스, 구독 로그인 사용). 6/15 크레딧 분리는 현재 일시중단이라 구독 그대로 동작하나 재시행 대비해 provider 추상화로 Gemini/Anthropic-API 폴백을 설정 한 줄로 교체 가능하게 유지. 구독 rate limit(5h/주간) 대비 일 게시 상한·백오프 가드 둠.

### WordPress
- 확정(2026-06-30): 카페24에서 결제한 **설치형 WordPress.org**. (사용자가 처음 WP.com Personal 로 추측했으나, developer.wordpress.com 로그인 불가로 설치형임이 드러남.)
- 게시: 사이트 자체 REST API(`/wp-json/wp/v2/posts`) + **Application Password**(Basic 인증). WP.com OAuth 방식 폐기.
- wp_publish.py = 설치형용으로 재작성. 카테고리는 이름→ID 변환(없으면 생성). wp_auth.py = 자격증명 점검 도구로 전환.
- 장점: 설치형이라 unfiltered_html 권한이 있어 본문 <style>·표·카드가 그대로 살 가능성 높음(WP.com보다 유리).

### 환경 제약
- 사용자 PC 신규 환경(아무것도 미설치). 전역(Python/Node)은 PC 설치, 의존성은 .venv 격리.
- Cowork 리눅스 샌드박스는 현재 비활성(HYPERVISOR_VIRT_DISABLED) → 코드 작성은 가능하나 이 환경에서 실행 테스트 불가. 실행/테스트는 사용자 PC에서.

### 쿠팡 파트너스 연동 (2026-06-30)
- 제약: 검색 API 시간당 10회·최대 10상품. LLM이 모델명 지어내면 죽은 링크/허위 위험.
- 결정: 글당 검색 1회로 실상품(이름·이미지·가격·추적URL) 수집 → `[[PRODUCTS]]` 토큰 자리에 카드 렌더. LLM은 브랜드/모델 특정 없이 선택기준·장단점·FAQ만 작성. API키 없으면 검색 링크 CTA로 폴백.
- 선행: 사용자 쿠팡 파트너스 Open API 키(ACCESS/SECRET) 발급 → .env. (Partners → Tools → 파트너스 API)
- 막힘 확인(2026-06-30): API 발급은 "최종 승인"(누적 판매금액 15만원) 후에만 가능. 사용자 계정은 미달이라 비활성. 준회원도 링크 생성·수익은 가능.
- 중간 전략 결정: 다이나믹 배너 위젯. config/coupang_widget.html(gitignore)에 스니펫 1회 등록 → 포맷터가 [[PRODUCTS]] 자리/말미에 자동 삽입. 폴백 순서 = API카드 > 위젯 > 검색CTA. 15만원 달성 후 .env에 키 넣으면 API 상품카드로 자동 전환(코드 변경 0).

### 쿠팡 스크래퍼 (승인 전 직링크 자동화, 2026-06-30)
- 사용자 요청. API 승인(15만원) 전까지 Playwright로 파트너스 로그인 세션 유지하며 상품 직링크 추출 → cron.
- 방식: persistent profile(data/.pw_profile, gitignore)로 1회 수동 로그인 후 세션 재사용(재부팅에도 유지). 풀리면 헤드로 띄워 수동 로그인 대기.
- 리스크 고지함: 파트너스 약관상 대시보드 자동화 제재 소지, UI 변경 시 셀렉터 깨짐. 사용자 계정 책임 동의.
- 진행: coupang_scraper.py = 로그인 + inspect(HTML/스크린샷 덤프) 하네스까지 완성. 실제 추출 셀렉터는 inspect 결과(data/inspect.html) 분석 후 작성 예정(추측 금지).
- formatter 연동 완료: 우선순위 API > data/product_links.json 캐시 > 배너 > 검색CTA. 스크래퍼는 캐시(product_links.json)만 채우면 됨.
- 결과(2026-06-30): 스크래퍼는 동작하나(검색·필터·직링크 추출·중복제거·로켓필터·SEO어 정제까지) 쿠팡이 자동 링크생성을 빠르게 반복하면 throttle(링크 미생성). 손으로는 정상 → 코드 문제 아닌 쿠팡 anti-bot. 결정: 스크래퍼는 보너스로 보류, 저속(상품수↓, 딜레이↑)으로만 가끔 사용. 주 수익경로는 다이나믹 배너로 전환.
- 활성 경로: 다이나믹 배너(자동·수익O, config/coupang_widget.html). 15만원 달성 후 공식 API로 전환(코드 변경 0).

### WordPress 방화벽(2026-06-30)
- 사이트에 NinjaFirewall 설치됨. 본문에 <script> 포함 시 REST 발행이 403 차단.
- 해결: 쿠팡 배너를 script가 아닌 **iframe** 버전으로 사용 → 방화벽 통과, 직접 삽입(p=58 발행 성공).
- 폴백 준비: script만 가능한 경우를 위해 숏코드 방식도 구현(settings.coupang.wp_banner_shortcode + wordpress/coupang-banner-shortcode.php). 현재는 빈 값(iframe 직접).
- 상태: 전 과정(생성→배너→발행) 동작 확인. publish.status 는 기본 draft.

### 배너 레이아웃(2026-06-30)
- 다이나믹 배너 여러 개를 config/coupang_widget.html 에 '---' 로 구분해 넣음(현재 3개, 모두 300x250, 추적코드는 각자 파트너스 코드 사용). 실제 값은 gitignore 된 coupang_widget.html 에만 있음.
- formatter 레이아웃 모드(settings.coupang.banner_layout).
  - grouped: 한 자리(토큰)에 배너 그룹 1개.
  - per_h2: 소제목마다 서로 다른 배너 1개씩(중복 방지).
  - grouped_h2: 한 자리 + 앞쪽 h2_groups(3)개 소제목 아래에 각각 배너 그룹.
  - 사용자 최종 선택(2026-06-30): **per_h2** — 앞쪽 소제목 3개 아래 서로 다른 배너 1개씩(중복 없음).
- 그룹은 .coupang-group(flex-wrap)로 데스크톱 가로·모바일 세로 정렬. max_banners=그룹당 배너 수.
- 주의: grouped_h2 는 배너가 많아 광고 과다·애드센스 심사 리스크 있음. 트래픽/심사 보고 조절 권장.

## 보완·고도화 제안 (검토 대기)
- 게시 직후 자동 색인 요청(구글 Indexing API / 서치콘솔 sitemap ping).
- 이미지 자동 생성(무료 소스 or 생성형) + alt 텍스트 자동화.
- 내부링크 자동 추천(같은 카테고리 글 연결) — 체류시간↑ 애드센스 수익↑.
- 중복/저품질 방지: 생성 글 표절·유사도 체크.
- A/B 제목 테스트 및 성과 로깅으로 주제 스코어링 피드백 루프.
