# 다른 PC에서 이어받기

GitHub 에는 코드·문서만 있고 개인 시크릿(`.env`, `config/coupang_widget.html`)은 없다. 그 둘만 준비하면 그대로 동작한다.

## 1. clone

```powershell
git clone https://github.com/<본인계정>/<저장소이름>.git
cd <저장소이름>
```

## 2. 환경 설치

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

## 3. 개인 파일 2개 준비 (git 에 없음)

- `.env` — `copy .env.example .env` 후 값 입력. 최소 **WordPress 자격증명(WP_*)** 과 **사이트 정보(SITE_*)** 를 채운다. 또는 기존 PC 의 `.env` 를 USB/보안채널로 복사.
- `config\coupang_widget.html` — `config\coupang_widget.example.html` 복사 후 쿠팡 **다이나믹 배너 iframe** 을 붙여넣는다(여러 개는 `---` 로 구분). 또는 기존 파일 복사.

## 4. 본인 니치 확인

- `config\categories.yaml` 의 니치·카테고리·seed 키워드가 본인 주제인지 확인(다르면 수정).

## 5. 실행 — 제어판 하나로

`제어판.bat` 을 더블클릭하면 콘솔 메뉴가 뜬다. 여기서 모든 걸 한다.

```
1 지금 1편 발행      2 키워드 새로 수집 후 발행
3 자동발행 켜기      4 끄기      5 시각 변경
6 발행모드   7 하루 편수   8 배너 레이아웃   9 배너 개수   10 로켓 전용
11 대시보드 열기(브라우저)   12 GitHub 올리기(push)
13 애드센스 필수 페이지 생성(소개/개인정보/문의)
```

- **3번(자동발행 켜기)** 을 누르면 매일 정해진 시각에 자동 발행된다(PC 가 그 시각에 켜져 있어야 함). 창은 닫아도 된다 — 예약은 Windows 작업 스케줄러에 저장된다.
- 브라우저로 조작하려면 **11번(대시보드)**.

## 6. 동기화

- 변경 올리기: 제어판 **12번(push)**.
- 다른 PC 로 돌아가면: `git pull`.
- 발행 이력(`data\published.json`)은 git 에 없으므로, 중복 발행을 막으려면 그 파일도 따로 복사한다.

## 7. 애드센스 필수 페이지 (최초 1회)

`.env` 의 `SITE_NAME`/`SITE_OWNER`/`SITE_EMAIL` 을 채운 뒤 제어판 **13번** → 소개·개인정보처리방침·문의 페이지가 자동 생성된다. 그 뒤 워드프레스 관리자 → 외모 → 메뉴에서 세 페이지를 메뉴에 추가한다.

## 참고 문서

- `SETUP.md` — 설치 상세.
- `HANDOFF.md` — 현재 상태·모듈 지도·다음 할 일.
- `README.md` — 개요·설정 항목·보안.
