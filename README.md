# WordPress 자동발행·티스토리 정책 콘텐츠 작업실

하나의 터미널 제어판에서 서로 독립된 두 가지 블로그 작업을 운영하는 Python 프로젝트다.

| 구분 | WordPress | 티스토리 정책 작업실 |
|---|---|---|
| 주제 | 생활·리빙·가전 | 30~50대 주부·직장인을 위한 정부 혜택 |
| 결과 | WordPress REST API 자동 게시 | 제목·본문·대표/본문 이미지·SEO·출처 패키지 보관 |
| 자동화 | 매일 실제 게시 | 매일 패키지만 생성, 티스토리 게시자는 수동 게시 |
| 설정 | `publish`, `content`, `coupang` | `policy_workspace` |
| 예약 | `src.schedule_task` | `src.policy_schedule_task` |

메인 메뉴 1~16은 WordPress 전용이고 17번으로 들어간 뒤의 1~24는 티스토리 전용이다. API 키와 쿠팡 공용 배너는 공유하지만 하루 편수·시각·광고·이미지 설정은 섞이지 않는다.

## 빠른 시작

자세한 설치는 [SETUP.md](SETUP.md)를 따른다. Python 3.12가 공식 기준이다.

```zsh
# macOS
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
./control.sh
```

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.\제어판.bat
```

설치·설정 진단은 게시나 유료 API 호출 없이 실행된다.

```sh
python -m src.doctor
python -m src.doctor --live  # 보조금24·Supabase·WordPress 읽기 전용 확인
```

## 실제 저장 구조

```text
wordpress_auto_blog/
├─ config/
│  ├─ settings.yaml               # GitHub에 보관하는 공식 기본값
│  ├─ settings.local.yaml         # 이 PC의 운영값, 자동 생성·gitignore
│  └─ categories.yaml
├─ src/                           # WordPress·티스토리 공용 및 전용 모듈
├─ tests/                         # 외부 호출을 모킹하는 회귀 테스트
├─ data/                          # 큐·발행 이력·SQLite, gitignore
├─ output/                        # 초안·미리보기·티스토리 패키지, gitignore
├─ logs/                          # 예약·대시보드 로그, gitignore
├─ control.sh / run.sh            # macOS 진입점
├─ 제어판.bat / run.bat           # WordPress Windows 진입점
└─ policy_run.bat                 # 티스토리 Windows 예약 진입점
```

메뉴·대시보드에서 바꾼 값은 `config/settings.local.yaml`에만 기록된다. `config/settings.yaml`을 수정하지 않으므로 GitHub에 개인 운영 시각과 편수가 따라가지 않는다.

## WordPress

```sh
# 설정 하루 편수만큼 게시
python -m src.pipeline
# 키워드를 갱신한 뒤 설정 하루 편수만큼 게시
python -m src.pipeline --refresh
# 이번 실행만 정확히 1편 게시
python -m src.pipeline --count 1

python -m src.schedule_task on
python -m src.schedule_task status
python -m src.schedule_task off
```

파이프라인은 실행 잠금과 원자적 발행 기록을 사용한다. 동일 slug 글이 이미 있거나 게시 응답이 끊긴 뒤 서버에서 같은 글이 확인되면 중복 POST를 하지 않는다. 한 주제 실패 시 다음 주제를 계속 시도한다.

- Windows 예약 작업: `blog-auto`, 실행 파일 `run.bat`
- macOS LaunchAgent: `com.wordpress-auto-blog.pipeline`
- 로그: `logs/pipeline.log`
- 중복 방지 기록: `data/published.json`

## 국가정책·티스토리 작업실

공식 보조금24 자료와 사용자가 추가한 공식 URL만 근거로 정책 후보를 만든다. 자동 추천은 생활 밀착도·구체적 혜택·최신성·카테고리 다양성을 함께 반영한다.

```sh
python -m src.policy_cli collect
python -m src.policy_cli list
python -m src.policy_cli generate 후보ID
python -m src.policy_cli generate-recommended --count 5
python -m src.policy_cli auto-run
python -m src.policy_cli packages
python -m src.policy_cli seo-check 글ID
python -m src.policy_cli retry-images 글ID all --provider openai
python -m src.policy_cli rebuild --all
python -m src.policy_cli remove-featured-from-body --all

python -m src.policy_schedule_task on
python -m src.policy_schedule_task status
python -m src.policy_schedule_task off
```

자동 생성 기본값은 꺼짐, 09:30, 하루 1편이다. 현재 PC에서 바꾼 값은 로컬 설정에 보관된다.

작업실 번호는 후보 준비 1~4, 수동 생성 5~6, 패키지 관리 7~13, 자동 생성 14~15, 이미지 16~18, SEO 19, 쿠팡 20~21, 기타 22~24로 묶여 있다. 패키지 관리와 이미지·SEO 기능은 수동/자동으로 만든 글에 공통 적용된다.

- Windows 예약 작업: `blog-policy-tistory-auto`, 실행 파일 `policy_run.bat`
- macOS LaunchAgent: `com.wordpress-auto-blog.policy-tistory`
- 로그: `logs/policy_pipeline.log`
- 후보·패키지·게시 상태: `data/policy_workspace.sqlite3`

### 티스토리 패키지

```text
output/tistory/YYYY/MM/DD/정책ID_제목/
├─ 00_게시가이드.txt
├─ 01_제목.txt
├─ 02_본문_티스토리.html
├─ 02_본문_HTML블록용.txt
├─ 03_본문_일반텍스트.txt
├─ 04_태그.txt
├─ 05_출처_검증.md
├─ 06_manifest.json
├─ 07_SEO_게시정보.txt
├─ images/
├─ segments/
└─ seo/
```

`02_본문_HTML블록용.txt`는 티스토리의 HTML 블록 또는 HTML 모드에 붙여넣는다. 코드블록은 HTML 소스를 화면에 보여주는 기능이므로 사용하지 않는다. 파일은 UTF-8 BOM으로 저장돼 macOS 텍스트 편집기에서도 한글이 깨지지 않는다.

대표 이미지는 `images/01_대표_*.jpg`와 Supabase에 보관하지만 게시용 본문에는 넣지 않는다. 티스토리에서 별도로 업로드해 대표 이미지로 지정한다. 본문 이미지 2장만 `blog_image` 공개 버킷 URL로 본문 HTML에 들어간다.

### 쿠팡 소재 입력

상품 URL, 링크+이미지 HTML, iframe, 공식 `PartnersCoupang.G` script를 지원한다.

- `1`: URL을 다음 입력창에 붙여넣기
- `2`: 미리 복사한 전체 코드를 macOS `pbpaste`/Windows 클립보드에서 읽기
- `3`: UTF-8 코드 파일 경로 입력
- `0`: 해당 글의 입력 완료

빈 줄은 완료로 처리하지 않는다. 수동 일괄 5편이면 각 글마다 설정 개수만큼 따로 묻는다. 예약 자동 생성은 사용자 입력을 받을 수 없어 쿠팡 API → 공용 배너 → 검색 링크 순으로 처리한다. 검색 링크는 파트너스 수익 추적이 보장되지 않는다는 경고를 남긴다.

## LLM·이미지 엔진

- `LLM_PROVIDER=anthropic`: `ANTHROPIC_API_KEY`, Claude API 사용. Claude Code 설치·로그인 불필요.
- `LLM_PROVIDER=gemini`: `GEMINI_API_KEY`, `google-genai`와 `gemini-3.6-flash` 사용.
- `LLM_PROVIDER=claude_code`: 로컬 `claude -p` 사용. Node.js·Claude Code 설치와 PC별 로그인이 필요.
- 티스토리 기본 이미지: OpenAI API `gpt-image-2`. ChatGPT/Codex 구독과 별도 과금.
- Pollinations: 사용자가 명시적으로 선택한 수동 대체 경로.

LLM은 600초, OpenAI 이미지는 장당 360초로 제한하며 15초마다 경과시간을 표시한다. OpenAI 이미지 SDK 자동 재시도는 꺼져 있어 한 장이 장시간 중복 호출되지 않는다.

## 보안·GitHub

다음은 GitHub에 올라가지 않는다.

- `.env`, `config/settings.local.yaml`, `config/coupang_widget.html`
- `data/`, `output/`, `logs/`, `.venv/`

메뉴 12의 GitHub push는 변경 목록 표시 → 전체 테스트 → 비밀값 검사 → 사용자 확인 → commit → 현재 브랜치 push 순서로 동작한다. PR이나 Codex GitHub 작업에 `gh`가 필요하면 `gh auth login` 후 `gh auth status`로 확인한다. 일반 `git push`는 Git 자격증명 관리자를 사용하며 `gh`에 의존하지 않는다.

```sh
python -m pytest -q
python -m compileall -q src tests
python -m src.secret_scan
python -m src.secret_scan --history
zsh -n control.sh run.sh
```

GitHub Actions는 Windows·macOS·Ubuntu의 Python 3.12에서 외부 API·실제 게시 없이 같은 회귀 검사를 수행한다.

다른 PC 이전 절차는 [CONTINUE-ON-NEW-PC.md](CONTINUE-ON-NEW-PC.md), 현재 운영 인수인계는 [HANDOFF.md](HANDOFF.md)를 참고한다.
