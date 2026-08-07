# 설치 가이드 (Windows / macOS)

이 프로젝트는 Python 3.12를 기준으로 한다. WordPress 자동 게시와 티스토리 정책 패키지 생성은 같은 가상환경을 사용하지만 예약 작업과 운영 설정은 서로 독립적이다.

## 1. 필수 도구

항상 필요한 것은 Python 3.12와 Git이다. Node.js·Claude Code는 `LLM_PROVIDER=claude_code`일 때만 필요하고, Playwright·Chrome은 선택 기능인 쿠팡 도우미를 사용할 때만 필요하다.

### Windows PowerShell

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
python --version
git --version
```

### macOS zsh

[Homebrew](https://brew.sh/) 설치 후 실행한다. Apple Silicon과 Intel 모두 `brew`가 제공하는 검색 경로를 사용하며 저장소 코드는 `/opt/homebrew` 같은 경로를 고정하지 않는다.

```zsh
brew install python@3.12 git
python3.12 --version
git --version
```

## 2. 저장소와 가상환경

### Windows

```powershell
git clone https://github.com/sangholabs/wordpress_auto_blog.git
cd wordpress_auto_blog
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
copy config\settings.local.example.yaml config\settings.local.yaml
```

### macOS

```zsh
git clone https://github.com/sangholabs/wordpress_auto_blog.git
cd wordpress_auto_blog
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cp config/settings.local.example.yaml config/settings.local.yaml
chmod +x control.sh run.sh
```

`config/settings.yaml`은 GitHub에 보관하는 공식 기본값이다. 메뉴·대시보드에서 바꾼 실제 편수·시각·광고 설정은 gitignore된 `config/settings.local.yaml`에 기록되고 기본 설정에 깊은 병합된다.

## 3. 글 생성 엔진 선택

`.env`의 `LLM_PROVIDER`에 하나를 선택한다.

| 값 | 필요한 인증 | 추가 설치 |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | 없음. Claude Code 로그인 불필요 |
| `gemini` | `GEMINI_API_KEY` | `requirements.txt`의 `google-genai`; 기본 모델 `gemini-3.6-flash` |
| `claude_code` | 이 PC의 Claude Code 로그인 | Node.js와 Claude Code CLI |

Anthropic API를 쓰는 현재 권장 예시는 다음과 같다.

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=본인의_API_키
```

`claude_code`를 선택한 경우에만 설치·로그인한다.

```sh
npm install -g @anthropic-ai/claude-code
claude
claude -p "로그인 확인"
```

Windows에서는 필요하면 `winget install -e --id OpenJS.NodeJS.LTS`, macOS에서는 `brew install node`를 먼저 실행한다. Node나 Claude 설치 위치가 바뀌면 macOS 예약 작업을 다시 등록해 현재 PATH를 plist에 반영한다.

## 4. WordPress 설정

설치형 WordPress 5.6+와 HTTPS를 사용한다. 관리자 → 사용자 → 프로필 → Application Passwords에서 비밀번호를 발급하고 `.env`에 입력한다. 게시 인증은 이 방식으로 통일한다.

```dotenv
WP_SITE_URL=https://본인블로그주소
WP_USERNAME=관리자아이디
WP_APP_PASSWORD=발급한_Application_Password
```

읽기 전용 인증 확인:

```powershell
.\.venv\Scripts\python.exe -m src.wp_auth
```

```zsh
./.venv/bin/python -m src.wp_auth
```

새 설치 기본값은 공개 발행, 하루 3편, 09:00이다. 운영 전 초안 검수가 필요하면 제어판의 WordPress 설정에서 발행모드를 `draft`로 바꾼다.

## 5. 정책·티스토리 작업실 설정

### 보조금24와 이미지 API

1. [공공데이터포털 대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do)에서 활용신청한다.
2. 인증키 발급현황의 일반 인증키를 `DATA_GO_KR_API_KEY`에 입력한다.
3. OpenAI 이미지 생성이 필요하면 별도 결제 계정의 `OPENAI_API_KEY`를 입력한다. ChatGPT/Codex 구독과 API 결제는 별개다.

```dotenv
DATA_GO_KR_API_KEY=일반_인증키
OPENAI_API_KEY=OpenAI_API_키
```

### Supabase Storage

1. Supabase Storage에 `blog_image`라는 **Public bucket**을 만든다.
2. `.env`에 프로젝트 URL, 서버용 secret 또는 레거시 service-role 키, 버킷명을 입력한다.
3. 키는 `.env`에만 보관하고 티스토리 HTML이나 GitHub에 넣지 않는다.

```dotenv
SUPABASE_URL=https://프로젝트.supabase.co
SUPABASE_SECRET_KEY=서버용_secret_키
SUPABASE_STORAGE_BUCKET=blog_image
SUPABASE_STORAGE_PREFIX=policy-tistory
```

공개 URL이 필요한 이미지 업로드 시점에만 버킷을 확인한다. 같은 패키지에 유효한 공개 URL이 이미 있으면 불필요한 상태 조회를 하지 않는다.

첫 사용 예시:

```sh
python -m src.policy_cli collect
python -m src.policy_cli list
python -m src.policy_cli generate 후보ID
python -m src.policy_cli generate-recommended --count 5
python -m src.policy_cli packages
```

티스토리는 자동 게시하지 않는다. 새 설치 기본값은 자동 생성 꺼짐, 09:30, 하루 1편이다. 자동 생성은 설정된 수만큼 패키지만 차례로 만들며 로그인·게시·공개 전환을 하지 않는다.

## 6. 티스토리 게시 순서

패키지는 `output/tistory/YYYY/MM/DD/정책ID_제목/`에 저장된다.

1. `01_제목.txt`의 제목을 복사한다.
2. `images/01_대표_*.jpg`를 티스토리에 따로 업로드하고 대표 이미지로 지정한다.
3. 티스토리의 HTML 블록 또는 HTML 모드에 `02_본문_HTML블록용.txt` 전체를 붙여넣는다.
4. 나눠 붙일 때는 `segments/*_HTML블록용.txt`를 안내 순서대로 사용한다.
5. `04_태그.txt`, `05_출처_검증.md`, `07_SEO_게시정보.txt`를 확인한다.
6. 비공개 상태로 표·이미지·쿠팡 소재가 유지되는지 확인한 뒤 공개한다.

코드블록은 HTML 소스를 화면에 표시할 뿐 렌더링하지 않으므로 사용하지 않는다. HTML과 복사용 텍스트는 UTF-8 BOM으로 저장된다. 대표 이미지는 파일·Supabase·manifest에는 남지만 본문 HTML에는 들어가지 않으며, 본문 이미지 2장만 공개 URL로 삽입된다.

기존 패키지에서 대표 이미지를 본문에서 제거하려면 외부 업로드 없이 실행한다.

```sh
python -m src.policy_cli remove-featured-from-body --all
```

## 7. 쿠팡 파트너스

API 키가 있으면 공식 상품카드, 없으면 `config/coupang_widget.html`의 공용 소재, 둘 다 없으면 수익 추적이 보장되지 않는 검색 링크를 사용한다.

```powershell
copy config\coupang_widget.example.html config\coupang_widget.html
```

```zsh
cp config/coupang_widget.example.html config/coupang_widget.html
```

티스토리 수동 생성 중 입력 방식은 다음과 같다.

- `1`: 다음 입력창에 쿠팡 HTTPS URL 붙여넣기
- `2`: 미리 복사한 링크+이미지 HTML, iframe 또는 공식 `PartnersCoupang.G` script 자동 읽기
- `3`: 해당 코드가 든 UTF-8 파일 경로 입력
- `0`: 이 글의 소재 입력 완료

빈 줄은 완료가 아니다. 5편 일괄 생성이면 글마다 설정된 최대 개수(기본 2개)를 따로 입력한다. 예약 자동 생성은 입력을 받을 수 없으므로 저장된 공용 소재/API/검색 링크만 사용한다. iframe/script는 티스토리에서 제거될 수 있으므로 비공개 미리보기에서 확인한다.

최종 승인 후 다음을 `.env`에 추가하면 공식 API 경로를 사용한다.

```dotenv
COUPANG_ACCESS_KEY=
COUPANG_SECRET_KEY=
COUPANG_PARTNERS_TAG=
```

## 8. 제어판과 직접 실행

```powershell
# Windows
.\제어판.bat
```

```zsh
# macOS
./control.sh
```

메인 1~16은 WordPress이고 17번 안의 1~24는 티스토리 전용이다.

WordPress 직접 실행:

```sh
python -m src.pipeline                 # 설정 하루 편수
python -m src.pipeline --refresh       # 키워드 갱신 후 설정 하루 편수
python -m src.pipeline --count 1       # 이번 실행만 정확히 1편
python -m src.pipeline --count 2 --refresh
```

macOS에서는 같은 인자를 `./run.sh --count 1`처럼 전달할 수 있다.

티스토리 직접 실행:

```sh
python -m src.policy_runner
python -m src.policy_runner --count 2 --force-refresh
python -m src.policy_cli auto-run
python -m src.policy_cli seo-check 글ID
python -m src.policy_cli retry-images 글ID all --provider openai
```

LLM 제한은 600초, OpenAI 이미지 제한은 장당 360초이고 15초마다 경과 상태를 출력한다. 이미지 일부 실패는 글 패키지를 보존하고 `needs_image_retry`로 기록한다.

## 9. 서로 독립된 예약 작업

WordPress:

```sh
python -m src.schedule_task on
python -m src.schedule_task status
python -m src.schedule_task off
```

- Windows 작업: `blog-auto`, `run.bat`, 로그 `logs/pipeline.log`
- macOS LaunchAgent: `com.wordpress-auto-blog.pipeline`

티스토리 패키지 자동 생성:

```sh
python -m src.policy_schedule_task on
python -m src.policy_schedule_task status
python -m src.policy_schedule_task off
```

- Windows 작업: `blog-policy-tistory-auto`, `policy_run.bat`, 로그 `logs/policy_pipeline.log`
- macOS LaunchAgent: `com.wordpress-auto-blog.policy-tistory`

한쪽 등록·해제·시각 변경은 다른 쪽에 영향을 주지 않는다. 새 PC로 복사한 파일만으로 예약은 복구되지 않으므로 필요한 작업을 각각 다시 등록한다.

## 10. 진단과 검증

기본 진단은 게시나 외부 유료 호출 없이 Python·가상환경·의존성·설정·스크립트·예약 상태를 확인한다. `--live`도 보조금24, Supabase, WordPress 인증을 읽기 전용으로만 조회한다.

```sh
python -m src.doctor
python -m src.doctor --live
python -m pytest -q
python -m compileall -q src tests
python -m src.secret_scan
python -m src.secret_scan --history
zsh -n control.sh run.sh
```

## 11. 선택 기능: Playwright·Chrome 쿠팡 도우미

일반 API/배너 운영에는 필요하지 않다.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
winget install -e --id Google.Chrome
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$PWD\data\chrome-profile"
```

```zsh
./.venv/bin/python -m playwright install chromium
brew install --cask google-chrome
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$PWD/data/chrome-profile"
```

쿠팡 파트너스에 로그인한 뒤 별도 터미널에서 `python -m src.coupang_scraper --run --cdp`를 실행한다. 자동화 제한과 UI 변경 가능성이 있으므로 보조 경로로만 사용한다.

## 12. GitHub 인증과 push

제어판의 GitHub 기능은 상태 확인 → 전체 테스트 → 비밀값 검사 → 사용자 확인 → 커밋 → 현재 브랜치 push 순서다. 일반 `git push`는 Git 자격증명 관리자를 사용하고 `gh`에 의존하지 않는다.

PR 등 GitHub CLI 기능에 로그인이 필요하면 다음을 실행하고 두 번째 명령이 성공한 것을 확인한다.

```sh
gh auth login
gh auth status
```

`.env`, `config/settings.local.yaml`, 쿠팡 개인 소재, SQLite, 생성 글·이미지·로그는 커밋하지 않는다.
