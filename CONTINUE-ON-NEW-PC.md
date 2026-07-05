# 다른 PC에서 이어받기

이 저장소를 다른 PC에서 clone 해 이어서 작업하는 방법. GitHub 에는 코드·문서만 있고 개인 시크릿(`.env`, `config/coupang_widget.html`)은 없으므로, 그 두 개만 따로 준비하면 된다.

## 1. clone

```powershell
git clone https://github.com/<본인계정>/<저장소이름>.git
cd <저장소이름>
```

## 2. 환경 설치 (SETUP.md 1~3단계)

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Git.Git
# 새 터미널을 연 뒤
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # 오류 시: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
pip install -r requirements.txt
playwright install chromium
npm install -g @anthropic-ai/claude-code
claude                              # 구독 로그인
```

## 3. 개인 시크릿 2개 준비 (git 에 없음)

- `.env` — `copy .env.example .env` 후 값 입력. 또는 기존 PC의 `.env` 를 USB/보안채널로 복사.
- `config\coupang_widget.html` — `config\coupang_widget.example.html` 복사 후 배너 iframe 입력. 또는 기존 파일 복사.

## 4. 본인 니치 확인

- `config\categories.yaml` 의 니치·카테고리·seed 키워드가 본인 주제인지 확인(다르면 수정).

## 5. 동작 확인 / 실행

```powershell
.\.venv\Scripts\python.exe -m pytest              # 테스트
.\.venv\Scripts\python.exe -m src.pipeline        # 전체 1회(키워드→주제→생성→포맷→배너→발행)
```

## 6. 작업 이어가기 (양방향 동기화)

- 이 PC에서 작업 후: `.\push.bat` (또는 `git add . && git commit -m "..." && git push`).
- 다른 PC로 돌아가면: `git pull` 로 최신 반영.
- 발행 이력(`data\published.json`)은 git 에 없으므로, 중복 발행을 막으려면 그 파일도 따로 복사해 둔다.

## 참고 문서

- `HANDOFF.md` — 현재 상태·모듈 지도·다음 할 일(코드와 함께 clone 됨).
- `context-notes.md` — 지금까지의 결정과 이유.
- `checklist.md` — 진행 체크리스트.
- `SETUP.md` — 설치 상세.
