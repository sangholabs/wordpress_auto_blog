# 핸드오프 (2026-06-30 기준)

다음 세션(사람/에이전트)이 바로 이어받기 위한 요약. 상세 결정 근거는 `context-notes.md`, 할 일은 `checklist.md` 참고.

## 1. 프로젝트 한 줄 요약

WordPress(설치형, 카페24) 블로그에 쿠팡 파트너스 + 애드센스 수익형 콘텐츠를 자동으로 기획·생성·발행하는 독립 파이썬 프로젝트. 토큰은 글 생성 단계에서만 쓰고 나머지는 0토큰.

## 2. 현재 상태 — 완성·GitHub 배포 완료

전 과정이 end-to-end로 동작 확인됨(테스트 발행 p=56~58, draft). GitHub 푸시 완료(시크릿 누출 없음 검증).
키워드 수집 → 주제 선정 → 글 생성(Claude Code) → 가독성 HTML 포맷 → 쿠팡 배너 삽입 → WordPress 발행.

- LLM: `claude_code`(로컬 Claude Code CLI, 구독 인증). 동작 확인.
- WordPress: 설치형 REST API + Application Password. 발행 확인.
- 쿠팡: 다이나믹 배너(iframe) 3개를 `config/coupang_widget.html`에 등록. NinjaFirewall은 iframe이라 통과.
- 배너 레이아웃: **per_h2 고정**(앞쪽 소제목 3개 아래 서로 다른 배너 1개씩, 중복 없음). `settings.yaml`의 `banner_layout`으로 grouped/grouped_h2 전환 가능.
- 발행 상태: 기본 `draft`(검수 후 `publish`로 전환 예정).

## 3. 환경 / 자격증명 (사용자 PC에 설정됨, 저장소엔 미포함)

- Python 3.12 + `.venv`(프로젝트 로컬), Node.js, Git, Claude Code(전역) 설치됨.
- `.env`: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD, LLM_PROVIDER=claude_code. (실제 값은 각자 `.env`에, gitignore 처리)
- `config/coupang_widget.html`: 다이나믹 배너 iframe(각자 파트너스 추적코드). `.gitignore` 처리됨.
- 모두 `.gitignore`로 제외 → GitHub 배포 시 개인정보 안 나감.

## 4. 모듈 지도 (src/)

- config.py — .env/yaml 로더.
- keyword_research.py — 구글/네이버 자동완성으로 키워드 수집(0토큰).
- topic_queue.py — 구매의도·롱테일 점수화, 중복 제거(0토큰).
- llm_provider.py — claude_code/gemini/anthropic 추상화.
- prompts.py — SEO·한국어 문체 프롬프트([[PRODUCTS]] 토큰 사용).
- generate_post.py — 주제 → 마크다운 글 생성.
- formatter.py — 마크다운 → 가독성 HTML(목차·고지문구·배너/상품카드). 배너 레이아웃 grouped/per_h2/grouped_h2.
- coupang.py — 파트너스 Open API(승인 후 사용, 현재 미사용).
- coupang_scraper.py — Playwright로 직링크 추출(보너스, anti-bot로 보류).
- wp_auth.py — WP 자격증명 점검.
- wp_publish.py — 설치형 WP REST 발행.
- pipeline.py — 전체 오케스트레이션(run.bat + 작업 스케줄러).

## 5. 실행

```powershell
.\.venv\Scripts\python.exe -m src.pipeline            # 전체 1회(키워드→주제→생성→발행)
.\.venv\Scripts\python.exe -m src.generate_post       # 글 1편 생성+미리보기
.\.venv\Scripts\python.exe -m src.formatter output\draft_*.md   # 토큰없이 재렌더
.\.venv\Scripts\python.exe -m src.wp_publish output\draft_*.md  # 발행
```
자동화: `schtasks /create /tn "blog-auto" /tr "...\blog\run.bat" /sc daily /st 09:00`

## 6. 수익화 현황 / 단계 전략

- 쿠팡 API는 **최종 승인(누적 판매금액 15만원)** 후 발급. 현재 미달 → **다이나믹 배너**로 수익화 중.
- 배너 클릭→구매는 추적코드로 수수료 인정(검색링크 CTA는 수익 없음, 폴백용).
- 15만원 달성 후 `.env`에 COUPANG_ACCESS_KEY/SECRET_KEY 넣으면 **키워드 매칭 실상품 카드로 자동 전환**(코드 변경 0). 폴백 우선순위: API카드 > 스크래퍼 캐시 > 배너 > 검색CTA.
- 애드센스: 글 30편 이상 축적 후 신청 권장.

## 7. 알려진 이슈 / 제약

- Cowork 리눅스 샌드박스 비활성 → 코드 실행/테스트는 사용자 PC에서.
- 쿠팡 스크래퍼: 동작하나 빠른 반복 시 쿠팡이 링크생성 throttle. 저속으로만. 주 경로는 배너.
- 배너 광고 과다 주의: 애드센스 심사 중에는 배너 수를 줄이는 게 안전(현재 per_h2, max_banners로 조절).
- 글 생성은 claude_code 구독 사용 → 무인 cron 시 6/15 크레딧 정책 변동 가능성(현재 일시중단).

## 8. 다음 할 일 (우선순위)

1. 며칠 draft 검수 → `settings.yaml` publish.status=publish 로 전환.
2. 작업 스케줄러 등록(완전 자동): `schtasks /create /tn "blog-auto" /tr "C:\Users\agent\Desktop\blog\run.bat" /sc daily /st 09:00`.
3. 글 30편 이상 축적 후 애드센스 신청. 판매금액 15만원 달성 시 .env 에 쿠팡 API 키 입력 → 실상품 카드 자동 전환.
4. 고도화(선택): 게시 후 구글 색인 요청, 내부링크 자동 연결, 대표 이미지 자동 생성, 제목 A/B 성과 피드백.

## 9. 배포 정보

- GitHub: `git push` 완료. 시크릿(.env, coupang_widget.html, data/, context-notes.md, HANDOFF.md)은 모두 `.gitignore` 처리.
- 다른 PC: `git clone` → `SETUP.md` 0~8단계대로 본인 값만 채우면 동작.
