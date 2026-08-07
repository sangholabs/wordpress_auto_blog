# 다른 Windows 또는 Mac에서 이어받기

GitHub에는 코드와 공식 기본 설정만 있다. API 키, 이 PC의 운영값, 발행 이력, 티스토리 패키지와 이미지는 별도로 안전하게 옮겨야 한다.

## 1. 새 PC에 설치

```sh
git clone https://github.com/sangholabs/wordpress_auto_blog.git
cd wordpress_auto_blog
```

Windows:

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
copy config\settings.local.example.yaml config\settings.local.yaml
```

macOS:

```zsh
brew install python@3.12 git
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cp config/settings.local.example.yaml config/settings.local.yaml
chmod +x control.sh run.sh
```

`LLM_PROVIDER=anthropic`이면 `ANTHROPIC_API_KEY`만 필요하고 Claude Code 설치·로그인은 필요 없다. `claude_code`를 계속 쓸 때만 Node.js, `npm install -g @anthropic-ai/claude-code`, 이 PC에서의 `claude` 로그인을 추가한다. Playwright와 Chrome도 쿠팡 도우미를 쓸 때만 설치한다.

## 2. 기존 PC에서 옮길 개인 파일

다음 항목은 Git에서 제외된다. 필요한 것만 암호화된 저장소나 안전한 이동 수단으로 복사한다.

| 항목 | 용도 | 권장 |
|---|---|---|
| `.env` | WordPress·LLM·보조금24·Supabase·쿠팡 키 | 필수 |
| `config/settings.local.yaml` | 실제 편수·시각·광고·이미지 설정 | 권장 |
| `config/coupang_widget.html` | 개인 쿠팡 공용 소재 | 사용할 때 |
| `data/published.json` | WordPress 중복 발행 방지 | 반드시 권장 |
| `data/policy_workspace.sqlite3` | 정책 후보·패키지·SEO·게시 상태 | 티스토리 작업 시 권장 |
| `output/tistory/` | 티스토리 제목·본문·이미지·manifest | 보관 필수 |

`logs/`, 임시 캐시, `.venv/`는 복사하지 않아도 된다. 가상환경은 새 PC에서 다시 만든다.

Supabase의 `blog_image` 객체는 원격 프로젝트에 이미 있으므로 같은 프로젝트 키를 쓰는 새 PC로 파일 자체를 다시 복사할 필요는 없다. 다만 `output/tistory/`의 manifest와 SQLite를 같이 옮겨야 기존 공개 URL과 로컬 패키지를 추적하기 쉽다.

SQLite를 잃었지만 티스토리 패키지와 `06_manifest.json`이 남아 있으면 다음으로 다시 색인한다.

```sh
python -m src.policy_cli reindex
```

## 3. 첫 진단

```sh
python -m src.doctor
python -m src.doctor --live
```

`--live`는 보조금24·Supabase·WordPress를 읽기 전용으로 확인한다. WordPress 게시, 유료 LLM, OpenAI 이미지 생성은 실행하지 않는다.

## 4. 실행 확인

Windows는 `제어판.bat`, macOS는 `./control.sh`를 실행한다. 메인 1~16은 WordPress, 17번 내부는 티스토리 작업실이다.

WordPress를 실제 공개하기 전에 초안 모드에서 정확히 1편만 시험하려면 제어판에서 발행모드를 초안으로 바꾼 뒤 실행한다.

```sh
python -m src.pipeline --count 1
```

티스토리는 게시하지 않고 패키지만 확인할 수 있다.

```sh
python -m src.policy_cli packages
python -m src.policy_cli preview 글ID
python -m src.policy_cli seo-check 글ID
```

대표 이미지는 티스토리에서 따로 업로드하고 대표로 지정한다. 본문은 `02_본문_HTML블록용.txt`를 HTML 블록/HTML 모드에 붙여넣는다.

## 5. 예약 작업 다시 등록

Windows 작업 스케줄러와 macOS LaunchAgent 상태는 파일 복사나 Git clone으로 이전되지 않는다. 필요한 자동화만 새 PC에서 각각 등록한다.

WordPress:

```sh
python -m src.schedule_task on
python -m src.schedule_task status
```

티스토리 패키지 자동 생성:

```sh
python -m src.policy_schedule_task on
python -m src.policy_schedule_task status
```

WordPress 예약은 `run.bat`/`run.sh`와 `logs/pipeline.log`, 티스토리는 `policy_run.bat`/`src.policy_runner`와 `logs/policy_pipeline.log`를 사용한다. 둘은 독립적이다.

## 6. GitHub 주의사항

- 코드 업데이트는 `git pull`로 받고 개인 파일 충돌을 만들지 않는다.
- `.env`, `settings.local.yaml`, 쿠팡 소재, `data/`, `output/`, `logs/`를 강제로 add하지 않는다.
- 제어판 push는 전체 테스트와 비밀값 검사를 통과한 뒤 사용자 확인을 받아 실행한다.
- GitHub CLI가 필요한 작업은 `gh auth login` 후 `gh auth status`가 성공하는지 확인한다. 일반 `git push`는 `gh`와 별개다.

세부 설치와 문제 해결은 [SETUP.md](SETUP.md)를 따른다.
