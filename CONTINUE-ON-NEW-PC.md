# 다른 Windows 또는 Mac에서 이어받기

GitHub에는 코드와 문서만 있고 개인 시크릿인 `.env`, `config/coupang_widget.html`, 발행 이력은 없다. 새 PC에서 아래 순서로 준비한다.

## 1. 저장소 받기

```sh
git clone https://github.com/<본인계정>/<저장소이름>.git
cd <저장소이름>
```

## 2. 환경 설치

Windows는 Python 3.12, Node.js LTS, Git을 `winget`으로 설치한다. macOS는 Homebrew 설치 후 다음을 실행한다.

```zsh
brew install python@3.12 node git
```

가상환경:

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

```zsh
# macOS zsh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Claude Code를 쓸 경우 설치하고 이 PC에서 한 번 로그인한다.

```sh
npm install -g @anthropic-ai/claude-code
claude
```

## 3. 개인 파일 준비

- Windows: `copy .env.example .env`
- macOS: `cp .env.example .env`

정책·티스토리 작업실도 사용할 경우 새 `.env`에 `DATA_GO_KR_API_KEY`와 `OPENAI_API_KEY`를 다시 입력한다. `output/tistory/`와 `data/policy_workspace.sqlite3`는 Git에 포함되지 않으므로 기존 PC에서 보관한 글 패키지를 별도로 복사한다. SQLite 색인이 없으면 `python -m src.policy_cli reindex`로 각 `06_manifest.json`에서 복원할 수 있다.
- 최소 WordPress 자격증명과 사이트 정보를 입력한다.
- 배너를 쓰면 `config/coupang_widget.example.html`을 `config/coupang_widget.html`로 복사하고 개인 iframe을 넣는다.
- `config/categories.yaml`의 니치와 seed 키워드를 확인한다.
- 중복 발행 방지를 이어가려면 이전 PC의 `data/published.json`을 보안 채널로 복사한다.

## 4. 실행

- Windows: `제어판.bat`
- macOS: `./control.sh`

제어판 3번은 Windows 작업 스케줄러 또는 macOS launchd에 매일 자동발행을 등록한다. 새 PC에서는 기존 예약이 복사되지 않으므로 반드시 다시 등록한다. macOS에서 Node/Claude 경로가 바뀐 경우에도 3번으로 재등록한다.

직접 실행은 Windows에서 `.\.venv\Scripts\python.exe -m src.pipeline`, macOS에서 `./run.sh`를 사용한다. 자세한 설치·문제 해결과 쿠팡 Chrome/CDP 명령은 `SETUP.md`를 참고한다.

## 5. 동기화 주의사항

- 코드 변경은 `git pull`/`git push`로 동기화한다.
- `.env`, 쿠팡 배너, `data/`, `logs/`, `output/`은 Git에 포함되지 않는다.
- 발행 이력을 옮기지 않으면 같은 키워드가 새 PC에서 다시 선택될 수 있다.
