# 운영·설치 체크리스트

## 공통 설치

- [ ] Python 3.12 확인: `python --version` 또는 `python3.12 --version`
- [ ] `.venv` 생성 후 `python -m pip install -r requirements.txt`
- [ ] `.env.example`을 `.env`로 복사하고 실제 값 입력
- [ ] `config/settings.local.example.yaml`을 `config/settings.local.yaml`로 복사
- [ ] `python -m src.doctor` 통과
- [ ] 선택한 LLM provider 확인
  - [ ] `anthropic`: `ANTHROPIC_API_KEY`; Claude Code 설치·로그인 불필요
  - [ ] `gemini`: `GEMINI_API_KEY`; `google-genai`·`gemini-3.6-flash`
  - [ ] `claude_code`: Node.js·Claude Code 설치 후 이 PC 로그인

## WordPress 자동 게시

- [ ] 설치형 WordPress HTTPS 주소 확인
- [ ] WordPress 사용자 프로필에서 Application Password 발급
- [ ] `.env`의 `WP_SITE_URL`, `WP_USERNAME`, `WP_APP_PASSWORD` 입력
- [ ] `python -m src.wp_auth` 읽기 전용 인증 확인
- [ ] 발행모드·하루 편수·시각을 제어판에서 확인
- [ ] 초안 상태에서 `python -m src.pipeline --count 1` 시험
- [ ] `data/published.json`이 Git에서 제외되고 백업되는지 확인
- [ ] 자동 게시 필요 시 `python -m src.schedule_task on` 후 `status` 확인
- [ ] Windows `logs/pipeline.log` 또는 macOS LaunchAgent 로그 확인

## 정책·티스토리 작업실

- [ ] 공공데이터포털 일반 인증키를 `DATA_GO_KR_API_KEY`에 입력
- [ ] 이미지 생성 사용 시 별도 결제의 `OPENAI_API_KEY` 입력
- [ ] Supabase Public bucket 이름이 `blog_image`인지 확인
- [ ] `.env`의 Supabase URL·서버용 키·버킷명 입력
- [ ] `python -m src.policy_cli collect`와 `list` 확인
- [ ] 대상 지역을 바꿨다면 후보를 다시 수집
- [ ] 수동 시험 패키지 1건 생성 후 `00_게시가이드.txt` 확인
- [ ] 대표 파일은 별도 업로드·대표 지정, 본문 이미지 2장만 HTML에 있는지 확인
- [ ] `02_본문_HTML블록용.txt`를 코드블록이 아닌 HTML 블록/HTML 모드에 붙여넣기
- [ ] 표·한글 줄바꿈·체크박스 `☐`·ALT·캡션 확인
- [ ] `07_SEO_게시정보.txt`와 `seo/게시전_검사.json` 확인
- [ ] 쿠팡 iframe/script 사용 시 티스토리 비공개 글에서 유지 여부 확인
- [ ] 게시 후 글 ID와 공개 HTTPS URL을 게시 완료로 기록
- [ ] 자동 패키지 생성 필요 시 `python -m src.policy_schedule_task on` 후 `status` 확인

## 쿠팡 파트너스

- [ ] 공용 소재를 쓸 경우 `config/coupang_widget.html` 준비
- [ ] 수동 소재 입력: `1` URL, `2` 클립보드, `3` UTF-8 파일, `0` 완료
- [ ] 빈 입력이 완료로 처리되지 않는지 확인
- [ ] 일괄 생성 시 각 글마다 필요한 소재를 따로 입력
- [ ] 광고 고지문구가 첫 광고 앞에 있는지 확인
- [ ] 제휴 링크에 `nofollow sponsored`가 유지되는지 확인
- [ ] API 승인 후에만 `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`, 태그 입력
- [ ] 검색 링크 폴백은 수익 추적이 보장되지 않음을 인지

## 자동화·복구

- [ ] WordPress와 티스토리 작업 이름·시각·로그가 독립적인지 확인
- [ ] 새 PC에서는 두 예약 중 필요한 것을 각각 다시 등록
- [ ] `config/settings.local.yaml`, `.env`, `data/published.json` 백업
- [ ] 티스토리 사용 시 SQLite와 `output/tistory/`도 함께 백업
- [ ] SQLite 분실 시 `python -m src.policy_cli reindex`
- [ ] 누락 이미지가 있으면 `retry-images 글ID all`
- [ ] 구형 패키지는 `remove-featured-from-body --all` 또는 필요한 재빌드 실행

## 코드 검증·GitHub

- [ ] `python -m pytest -q`
- [ ] `python -m compileall -q src tests`
- [ ] `zsh -n control.sh run.sh` (macOS)
- [ ] 설정·CI YAML 파싱
- [ ] `python -m src.secret_scan`
- [ ] `python -m src.secret_scan --history`
- [ ] `.env`, `settings.local.yaml`, SQLite, output, logs가 추적되지 않는지 확인
- [ ] 변경 목록·브랜치·원격 확인
- [ ] 테스트와 비밀값 검사 성공 후에만 commit/push 확인
- [ ] PR 등 `gh` 작업은 `gh auth login` 후 `gh auth status` 성공 확인

## 자동 테스트에서 하지 않는 작업

- [x] 실제 WordPress 게시를 호출하지 않음
- [x] 유료 LLM·OpenAI 이미지 생성을 호출하지 않음
- [x] 실제 스케줄러를 등록·해제하지 않음
- [x] GitHub push를 자동 실행하지 않음
- [x] 외부 API 키를 CI에 주입하지 않음
