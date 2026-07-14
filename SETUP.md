# 설치 가이드 (Windows, 신규 PC 기준)

전역 도구는 PC에 설치하고, 프로젝트 의존성은 `.venv`에 격리한다. 그래야 GitHub에 올렸을 때 다른 PC에서 clone→설치만으로 동일하게 동작한다. 각 단계에서 빠뜨린 설정이 있으면 실행 시 터미널이 무엇을 채워야 하는지 안내한다.

## 0. clone 후 빠른 시작 (순서 요약)

1. 전역 설치 — Python 3.11+, Node.js LTS, Git (1단계).
2. 프로젝트 의존성 — venv 생성 + 설치 (2단계).
3. 글 생성 엔진 — Claude Code 설치 + 로그인, 또는 다른 LLM 선택 (3단계).
4. 환경변수 — `copy .env.example .env` 후 값 입력 (4단계).
4-1. 본인 니치 — `config/categories.yaml`의 니치·카테고리·seed 키워드를 본인 주제로 수정.
5. 쿠팡 — 계정 상태에 맞게 배너(iframe) 또는 API (5단계).
6. WordPress — Application Password 입력 (6단계).
7. 애드센스 필수 페이지 — SITE_* 채우고 제어판 13번 (7단계).
8. 실행 / 자동화 — `제어판.bat` 하나로 발행·자동발행·설정 (8단계).

## 1. 전역 설치 (PC에 1회)

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Git.Git
```
설치 후 **새 터미널**을 열어야 PATH가 반영된다. 확인.
```powershell
python --version
node -v
git --version
```

## 2. 프로젝트 의존성 (이 폴더 안에 격리)

```powershell
cd C:\Users\<사용자>\Desktop\blog
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```
`Activate.ps1` 에서 "스크립트 실행 불가" 오류가 나면 한 번만.
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 3. 글 생성 엔진 (LLM)

기본값은 구독 인증을 쓰는 Claude Code다(키 불필요).
```powershell
npm install -g @anthropic-ai/claude-code
claude            # 처음 실행 시 브라우저로 구독 로그인
claude -p "안녕"  # 답변이 나오면 정상
```
구독 대신 다른 LLM을 쓰려면 `.env` 의 `LLM_PROVIDER` 를 `gemini` 또는 `anthropic` 으로 바꾸고 해당 키를 넣는다.

## 4. 환경변수

```powershell
copy .env.example .env
```
`.env` 를 열어 필요한 블록만 채운다. 각 항목의 [필수]/[선택] 설명은 `.env.example` 주석 참고. `.env` 는 커밋되지 않는다.

## 5. 쿠팡 파트너스 설정 (계정 상태에 따라 둘 중 하나)

쿠팡 파트너스 Open API 는 **최종 승인(누적 판매금액 15만 원) 이후에만** 발급된다. 코드는 자동으로 알맞은 방식을 쓴다(API 키 있으면 상품카드, 없으면 배너, 둘 다 없으면 검색 링크).

### A. 아직 최종 승인 전 (대부분의 신규 계정) → 다이나믹 배너
1. 쿠팡 파트너스 → "링크 생성" → "다이나믹 배너" → 배너 생성 → **iframe 코드** 복사. (script 버전은 NinjaFirewall 등 보안 플러그인에 막힐 수 있어 iframe 권장)
2. `config\coupang_widget.example.html` 을 같은 폴더에 `coupang_widget.html` 로 복사.
3. 그 파일 맨 아래에 iframe 을 붙여넣고 저장. 여러 개는 `---` 한 줄로 구분하면 소제목마다 다른 배너가 들어간다. (개인 추적ID 포함이라 `.gitignore` 처리됨)
4. 준회원도 링크·수익이 가능하므로, 이렇게 운영하며 판매금액 15만 원을 채운다.

### B. 최종 승인 완료 → Open API 상품카드 (자동 전환)
1. 쿠팡 파트너스 → 상단 "Tools" → "파트너스 API" → Access/Secret Key 발급.
2. `.env` 에 `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`, `COUPANG_PARTNERS_TAG` 입력.
3. 코드 수정 없이 다음 글 생성부터 실상품 카드로 자동 전환된다.

## 6. WordPress 게시 자격증명 (설치형 WordPress.org, 카페24 등)

설치형 워드프레스는 WordPress.com 계정이 아니라 **사이트 자체의 Application Password** 로 인증한다(WordPress 5.6+, https 필요).

1. 워드프레스 관리자 로그인 → 좌측 "사용자(Users)" → 본인 "프로필(Profile)".
2. 아래로 스크롤 → "Application Passwords(애플리케이션 비밀번호)" 섹션 → 이름(예: blog-bot) 입력 → "Add New Application Password".
3. 생성된 비밀번호(`xxxx xxxx xxxx xxxx` 형식)를 복사한다. **이 화면을 벗어나면 다시 못 보니 즉시 복사.**
4. `.env` 에 입력한다.
   ```
   WP_SITE_URL=https://본인블로그주소
   WP_USERNAME=관리자아이디
   WP_APP_PASSWORD=복사한 비밀번호
   ```
5. 자격증명이 맞는지 점검한다.
   ```powershell
   .\.venv\Scripts\python.exe -m src.wp_auth
   ```
   "인증 성공" 이 뜨면 OK.

> "Application Passwords" 섹션이 안 보이면 사이트가 https 가 아니거나 보안 플러그인이 막은 것이다. 알려달라.

발행 테스트(초안 상태로 안전하게).
```powershell
.\.venv\Scripts\python.exe -m src.wp_publish output\draft_에어프라이어-추천-순위.md
```
`config\settings.yaml` 의 `publish.status` 가 기본 `draft` 라, 워드프레스 관리자에서 검수 후 직접 발행한다. 익숙해지면 `publish` 로 바꿔 완전 자동 발행한다.

## 7. 애드센스 필수 페이지 (최초 1회)

`.env` 의 `SITE_NAME`/`SITE_OWNER`/`SITE_EMAIL` 을 채운 뒤 제어판(8단계) **13번** 을 실행하면 소개·개인정보처리방침·문의 페이지가 자동 생성된다. 그 뒤 워드프레스 관리자 → 외모 → 메뉴에서 세 페이지를 메뉴에 추가한다(애드센스 필수).

## 8. 실행 / 자동화 — 제어판 하나로

일상 조작은 **`제어판.bat` 더블클릭** → 콘솔 메뉴로 한다.

```
1 지금 1편 발행   2 키워드 새로 수집 후 발행
3 자동발행 켜기   4 끄기   5 시각 변경
6 발행모드  7 하루 편수  8 배너 레이아웃  9 배너 개수  10 로켓 전용
11 대시보드(브라우저)  12 push  13 애드센스 필수 페이지  14 Claude 로그인
```

- **3번(자동발행 켜기)** = `run.bat` 을 매일 `schedule_time`(기본 09:00)에 실행하도록 Windows 작업 스케줄러에 등록. 창을 닫아도 유지되며, PC 가 그 시각에 켜져 있어야 발행된다.
- 브라우저 UI 로 조작하려면 **11번(대시보드)** → http://localhost:5000.
- 명령줄도 가능: `.\.venv\Scripts\python.exe -m src.pipeline` (또는 `--refresh`).
- 실행 로그 `logs\pipeline.log`, 발행 이력 `data\published.json`(중복 발행 방지).
- 루트 .bat 은 `제어판.bat`(메인)·`run.bat`(스케줄러 전용) 둘뿐.
