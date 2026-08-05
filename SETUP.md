# 설치 가이드 (Windows / macOS)

전역 도구는 PC에 설치하고 Python 의존성은 프로젝트 `.venv`에 격리한다. Windows와 macOS 모두 같은 Python 모듈을 사용하고, 실행·자동발행 방식만 운영체제에 맞게 선택한다.

## 0. 빠른 시작

1. Python 3.12, Node.js LTS, Git을 설치한다.
2. `.venv`를 만들고 `requirements.txt`와 Playwright Chromium을 설치한다.
3. Claude Code를 설치·로그인하거나 다른 LLM provider를 설정한다.
4. `.env.example`을 `.env`로 복사하고 WordPress 등 필요한 값을 채운다.
5. `config/categories.yaml`의 니치와 seed 키워드를 확인한다.
6. 쿠팡 배너/API와 WordPress Application Password를 준비한다.
7. Windows는 `제어판.bat`, macOS는 `./control.sh`를 실행한다.

## 1. 전역 도구 설치

### Windows PowerShell

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Git.Git
```

설치 후 새 터미널에서 확인한다.

```powershell
python --version
node -v
git --version
```

### macOS 터미널

[Homebrew](https://brew.sh/)를 먼저 설치한 뒤 다음을 실행한다. Apple Silicon과 Intel Mac 모두 `brew`가 제공하는 명령 검색 경로를 사용하므로 저장소 코드에는 Homebrew 경로를 고정하지 않는다.

```zsh
brew install python@3.12 node git
python3.12 --version
node -v
git --version
```

## 2. 프로젝트 가상환경과 의존성

### Windows PowerShell

```powershell
cd C:\Users\<사용자>\Desktop\blog
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

`Activate.ps1` 실행이 차단되면 한 번만 실행한다.

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS zsh

```zsh
cd /path/to/wordpress_auto_blog
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

실행 권한이 유실된 경우에만 `chmod +x control.sh run.sh`를 한 번 실행한다.

## 3. 글 생성 엔진 (LLM)

기본값은 로컬 Claude Code CLI의 구독 인증을 사용한다.

```sh
npm install -g @anthropic-ai/claude-code
claude
claude -p "안녕"
```

macOS에서 `claude`를 찾지 못하면 새 터미널을 열고 `command -v claude`로 설치 경로가 PATH에 포함됐는지 확인한다. 자동발행 등록 시 현재 터미널의 PATH가 launchd 설정에 저장되므로 Node/Claude 설치 경로를 바꾼 뒤에는 제어판 3번으로 다시 등록한다.

구독 대신 다른 LLM을 사용하려면 `.env`의 `LLM_PROVIDER`를 `gemini` 또는 `anthropic`으로 바꾸고 해당 API 키를 입력한다.

## 4. 환경변수

Windows:

```powershell
copy .env.example .env
```

macOS:

```zsh
cp .env.example .env
```

`.env`에서 필요한 블록만 채운다. 이 파일은 gitignore 대상이다.

### 4-A. 국가정책·티스토리 작업실 키

정책 작업실을 사용할 때만 다음 두 키를 추가한다.

1. [공공데이터포털의 대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do)에서 활용신청한다.
2. `인증키 발급현황`에 표시되는 **일반 인증키**를 `.env`의 `DATA_GO_KR_API_KEY`에 그대로 입력한다. 현재 포털의 단일 키와 기존 Encoding/Decoding 키 형식을 모두 지원한다.
3. OpenAI API 대시보드에서 유료 API 키를 발급해 `OPENAI_API_KEY`에 입력한다. ChatGPT/Codex 구독과 API 결제는 별도다.

```dotenv
DATA_GO_KR_API_KEY=공공데이터포털_일반_인증키
OPENAI_API_KEY=OpenAI_API_키
```

키를 채운 뒤 터미널 제어판의 `17. 정책·티스토리 작업실` 또는 웹 대시보드의 정책 작업실을 연다. 첫 사용 순서는 다음과 같다.

```sh
python -m src.policy_cli regions 서울 성남
python -m src.policy_cli collect
python -m src.policy_cli list
python -m src.policy_cli generate 후보ID
python -m src.policy_cli generate-recommended --count 1
python -m src.policy_cli auto-run
python -m src.policy_cli settings show
python -m src.policy_cli dashboard
python -m src.policy_cli required-pages
```

후보 수집은 보조금24 첫 페이지를 그대로 보여주지 않는다. 여러 페이지와 근로자·가구·연령·업종 지원조건을 함께 검사하고, 30~50대 주부·직장인 생활과 무관한 전문업종 정책은 자동으로 숨긴다. `list`는 추천 후보만 보여주며 `generate-recommended`를 실행하면 상위 후보를 자동 선택해 생성한다. 이 생성 명령부터 LLM과 이미지 API가 호출될 수 있다.

정책 글은 자동 게시되지 않는다. `output/tistory/YYYY/MM/DD/` 아래의 `00_게시가이드.txt`를 따른다. 티스토리 기본모드의 **HTML 블록**에 `02_본문_HTML블록용.txt` 전체를 붙여넣거나, 본문 이미지를 사이에 넣으려면 `segments/*_HTML블록용.txt` 세 파일을 순서대로 붙여넣는다. 코드블록은 HTML을 렌더링하지 않고 소스로 표시하므로 사용하지 않는다. `.html`과 복사용 `.txt`는 모두 UTF-8 BOM으로 저장되어 macOS 텍스트 편집기에서도 한글을 올바르게 인식한다.

글별 쿠팡 광고는 상품 URL뿐 아니라 쿠팡 파트너스가 발급한 링크+이미지 HTML, iframe, 카테고리/다이나믹 배너 `PartnersCoupang.G` 스크립트를 받을 수 있다. 터미널에서는 코드를 클립보드에 복사하고 **클립보드 코드** 입력을 선택한다. 파일로 적용하려면 `python -m src.policy_cli coupang-assets 글ID --file 배너코드.html`을 사용한다. iframe/script는 티스토리에서 제거될 수 있으므로 비공개 게시 후 확인한다.

OpenAI 이미지 생성이 일부 실패하면 글 패키지는 `needs_image_retry` 상태로 남는다. 다음 명령 또는 작업실 메뉴에서 누락 이미지만 재시도할 수 있으며 Pollinations 전환은 사용자가 직접 선택한 경우에만 실행된다.

```sh
python -m src.policy_cli retry-images 글ID all --provider openai
python -m src.policy_cli seo-check 글ID
python -m src.policy_cli seo-check 글ID --url https://내블로그.tistory.com/글주소
```

티스토리 패키지 자동생성은 WordPress 자동발행과 별도다. 초기값은 꺼짐, 매일 09:30, 하루 1편이며 글 패키지만 만들고 게시하지 않는다.

```sh
python -m src.policy_schedule_task on
python -m src.policy_schedule_task status
python -m src.policy_schedule_task off
```

macOS plist는 `~/Library/LaunchAgents/com.wordpress-auto-blog.policy-tistory.plist`, 로그는 `logs/policy_pipeline.log`를 사용한다. Windows 작업 이름은 `blog-policy-tistory-auto`다. `src.schedule_task`는 WordPress 전용, `src.policy_schedule_task`는 티스토리 전용이므로 서로 등록·해제되지 않는다.

## 5. 쿠팡 파트너스 설정

쿠팡 파트너스 Open API는 누적 판매금액 15만 원 기준의 최종 승인 후 사용할 수 있다. 코드는 API 키가 있으면 상품카드, 없으면 배너, 둘 다 없으면 검색 링크를 사용한다.

### 승인 전: 다이나믹 배너

1. 쿠팡 파트너스에서 다이나믹 배너의 iframe 코드를 만든다. script 버전은 WordPress 보안 플러그인에 차단될 수 있으므로 iframe을 권장한다.
2. `config/coupang_widget.example.html`을 `config/coupang_widget.html`로 복사한다.
3. iframe을 붙여넣는다. 여러 배너는 `---` 한 줄로 구분한다.

복사 명령:

```powershell
# Windows
copy config\coupang_widget.example.html config\coupang_widget.html
```

```zsh
# macOS
cp config/coupang_widget.example.html config/coupang_widget.html
```

### 최종 승인 후: Open API

`.env`에 `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`, `COUPANG_PARTNERS_TAG`를 입력하면 다음 글부터 API 상품카드로 전환된다.

## 6. WordPress 게시 자격증명

설치형 WordPress 5.6+ 사이트에서 HTTPS를 사용해야 한다. WordPress 관리자 → 사용자 → 프로필 → Application Passwords에서 비밀번호를 만들고, 다시 표시되지 않으므로 즉시 복사해 `.env`에 입력한다.

```dotenv
WP_SITE_URL=https://본인블로그주소
WP_USERNAME=관리자아이디
WP_APP_PASSWORD=복사한비밀번호
```

Application Passwords 섹션이 보이지 않으면 HTTPS 적용 여부와 보안 플러그인의 REST/Application Password 차단 설정을 확인한다.

인증 점검:

```powershell
# Windows
.\.venv\Scripts\python.exe -m src.wp_auth
```

```zsh
# macOS
./.venv/bin/python -m src.wp_auth
```

발행 테스트는 `config/settings.yaml`의 `publish.status`를 `draft`로 둔 뒤 실행한다.

```powershell
# Windows
.\.venv\Scripts\python.exe -m src.wp_publish output\draft_파일명.md
```

```zsh
# macOS
./.venv/bin/python -m src.wp_publish output/draft_파일명.md
```

## 7. 애드센스 필수 페이지

`.env`의 `SITE_NAME`, `SITE_OWNER`, `SITE_EMAIL`을 채운 뒤 제어판 13번을 실행한다. 생성 후 WordPress 관리자에서 소개·개인정보처리방침·문의 페이지를 메뉴에 추가한다.

티스토리는 17번 작업실의 `티스토리 애드센스 필수 페이지 패키지`를 실행한다. `output/tistory/pages/`에 복사용 HTML 블록 파일을 만들며 WordPress에는 게시하지 않는다. 티스토리의 이름·운영자·문의 이메일이 다르면 `.env`의 `TISTORY_SITE_NAME`, `TISTORY_SITE_OWNER`, `TISTORY_SITE_EMAIL`을 별도로 채운다.

## 8. 실행과 자동발행

### 터미널 제어판

```powershell
# Windows
.\제어판.bat
```

```zsh
# macOS
./control.sh
```

메인 메뉴 1~16은 WordPress 전용이다. 17번으로 들어간 뒤에는 티스토리 정책 패키지의 수집·자동생성·SEO·쿠팡·이미지·대시보드·Claude 로그인·필수 페이지 기능만 표시된다.

```text
1 지금 발행  2 키워드 갱신 후 발행
3 자동발행 켜기  4 끄기  5 시각 변경
6 발행모드  7 하루 편수  8 배너 레이아웃  9 배너 개수
10 로켓 전용  11 대시보드  12 GitHub push
13 애드센스 필수 페이지  14 Claude 로그인
15 쿠팡 배너 도우미  16 대표 이미지 켜기/끄기
17 정책·티스토리 작업실
```

직접 실행:

```powershell
# Windows
.\.venv\Scripts\python.exe -m src.pipeline
.\.venv\Scripts\python.exe -m src.pipeline --refresh
```

```zsh
# macOS
./run.sh
./run.sh --refresh
```

자동발행은 제어판 3번으로 켜고 4번으로 끈다. Windows는 작업 스케줄러의 `blog-auto`, macOS는 사용자 LaunchAgent의 `com.wordpress-auto-blog.pipeline`을 사용한다. macOS 작업은 사용자가 로그인한 세션에서 동작하며 등록 즉시 발행하지 않는다.

브라우저 UI는 제어판 11번에서 열며 기본 주소는 `http://localhost:5000`이다.

상태 확인과 직접 제어:

```sh
python -m src.schedule_task status
python -m src.schedule_task on
python -m src.schedule_task off
```

macOS plist는 `~/Library/LaunchAgents/com.wordpress-auto-blog.pipeline.plist`에 생성된다. 실행 로그는 `logs/pipeline.log`, 대시보드 로그는 `logs/dashboard.log`, 발행 이력은 `data/published.json`에 저장된다.

## 9. 선택 기능: 쿠팡 Playwright/CDP

일반 배너/API 운영에는 필요하지 않다. 승인 전 직링크 스크래퍼를 사용할 때만 실제 Google Chrome을 설치한다.

```powershell
# Windows
winget install -e --id Google.Chrome
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PWD\data\chrome-profile"
```

```zsh
# macOS
brew install --cask google-chrome
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$PWD/data/chrome-profile"
```

Chrome에서 쿠팡 파트너스에 로그인한 뒤 별도 터미널에서 실행한다.

```sh
python -m src.coupang_scraper --run --cdp
```

빠른 반복은 쿠팡 anti-bot 제한을 유발할 수 있으므로 이 기능은 보조 경로로만 사용한다.
