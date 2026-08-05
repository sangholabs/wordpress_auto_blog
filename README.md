# 수익형 블로그 자동화 파이프라인

WordPress 블로그에 쿠팡 파트너스 + 구글 애드센스 수익형 콘텐츠를 자동으로 기획·생성·게시하는 독립 프로젝트다. clone 후 `.env`만 채우면 다른 PC에서도 바로 동작하도록 설계한다.

기존 WordPress 자동발행과 별도로 **국가정책·티스토리 작업실**을 제공한다. 30~50대 주부·직장인이 놓치기 쉬운 정부 혜택을 공식 출처에서 수집하고, 검토한 정책만 글·대표 이미지·본문 이미지·출처 검증 파일로 묶어 티스토리에 수동 게시할 수 있다.

## 핵심 원칙

- 반복적이고 일관된 작업(키워드 수집, 포맷팅, 게시)은 순수 Python/JS로 처리해 **토큰을 쓰지 않는다.**
- LLM 토큰은 **글 생성 단계에서만** 사용하며, provider 추상화로 Gemini/Claude를 교체할 수 있다.
- 비밀정보·수집데이터·임시파일은 모두 `.gitignore` 처리해 GitHub에 개인정보가 딸려가지 않는다.

## 파이프라인 (7단계)

1. 카테고리 설계 — `config/categories.yaml` (반자동, 1회).
2. 키워드/주제 발굴 — 검색 자동완성·연관검색어 스크래핑 (cron, 0토큰).
3. 주제 큐 선별 — 검색량·경쟁도 스코어링, 중복 제거 (0토큰).
4. 글 생성 — SEO 구조 템플릿 기반 LLM 호출 (토큰 사용).
5. 가독성 포맷팅 — 목차·이미지·쿠팡 링크·고지문구 자동 삽입 (0토큰).
6. WordPress 게시 — REST API 예약발행 (0토큰).
7. 모니터링 — 게시 결과·비용 리포트.

## 폴더 구조 (예정)

```
blog/
├─ config/        # 카테고리·운영 설정 (yaml)
├─ src/           # 파이프라인 단계별 모듈
├─ data/          # 수집·생성 데이터 (gitignore)
├─ logs/          # 실행 로그 (gitignore)
├─ .env           # 비밀정보 (gitignore)
└─ requirements.txt
```

## 설치·실행 (Windows / macOS)

`SETUP.md` 참고. 전역 Python 3.12/Node/Git은 PC에 설치하고, Python 의존성은 프로젝트 `.venv`에 격리한다.

- Windows 터미널 제어판: `제어판.bat`
- macOS 터미널 제어판: `./control.sh`
- Windows 예약 실행: 작업 스케줄러(`schtasks`)
- macOS 예약 실행: 사용자 LaunchAgent(`launchd`)
- 공통 직접 실행: 가상환경 Python으로 `python -m src.pipeline`

## 진행 상황

`checklist.md`(할 일)와 `context-notes.md`(결정 기록)에서 관리한다.

## 보안 / 배포

이 저장소에는 어떤 개인정보·시크릿도 포함되지 않는다. 다음 항목은 모두 `.gitignore`로 제외된다.

- `.env` (WordPress·API 키 등) — `.env.example`을 복사해 직접 채운다.
- `config/coupang_widget.html` (쿠팡 추적코드 포함) — `config/coupang_widget.example.html` 참고해 직접 만든다.
- `data/`, `logs/`, `output/`, 로그인 세션 프로필 — 실행 중 생성되는 로컬 데이터.

clone 후에는 `SETUP.md`의 순서대로 본인 환경·자격증명만 채우면 바로 동작한다. 커밋 전에는 항상 `git status`로 위 파일들이 추적되지 않는지 확인한다.

## 설정으로 바꿀 수 있는 것

코드 수정 없이 `config/settings.yaml`(동작·디자인)과 `.env`(키·포트)에서 조정한다. 각 항목엔 주석이 달려 있다.

- content — 최소 분량, 목차, 쿠팡 고지문구, 배너 레이아웃(per_h2/grouped/grouped_h2)·개수.
- policy_workspace — 티스토리 전용 자동생성 시각·하루 편수, 보조금24 후보 갱신, SEO 기준, GPT Image, 쿠팡 광고·배너·로켓 설정. WordPress 설정과 독립된다.
- publish — 발행 모드(publish/draft), 하루 편수, 자동발행 시각(schedule_time).
- llm — anthropic/gemini 모델, max_tokens.
- keyword_research — 요청 딜레이·타임아웃, 구글/네이버 소스 on/off.
- topic_queue — 구매의도 키워드(intent_words), 롱테일 단어 수 범위.
- design — 본문 폭·글자 크기·행간·주색상·가격색·폰트.
- coupang — 로켓 전용, 글당 상품 수, 검색 수·타임아웃, 스크래퍼 포트, 배너 숏코드.
- 니치·카테고리·주제 씨앗 — `config/categories.yaml`.
- .env — LLM_PROVIDER·키, 쿠팡 키/태그, WordPress 자격증명, `DASHBOARD_PORT`, 예산·편수.
- 정책 작업실은 `.env`의 `DATA_GO_KR_API_KEY`와 이미지 생성용 `OPENAI_API_KEY`를 추가로 사용한다.

## 국가정책·티스토리 작업실

`./control.sh` 또는 `제어판.bat`에서 `17. 정책·티스토리 작업실`을 선택한다. 웹에서는 기존 대시보드의 **국가정책·티스토리 작업실 열기** 또는 `/policy`를 사용한다.

터미널에서 직접 실행할 수도 있다.

```bash
python -m src.policy_cli collect
python -m src.policy_cli list
python -m src.policy_cli import-url "https://공식정책주소"
python -m src.policy_cli generate 후보ID
python -m src.policy_cli generate-recommended --count 1
python -m src.policy_cli auto-run
python -m src.policy_schedule_task on
python -m src.policy_schedule_task status
python -m src.policy_cli seo-check 글ID
python -m src.policy_cli retry-images 글ID all --provider openai
python -m src.policy_cli settings show
python -m src.policy_cli dashboard
python -m src.policy_cli claude-login
python -m src.policy_cli banner-setup
python -m src.policy_cli required-pages
python -m src.policy_cli packages
# 기존 글에 쿠팡 상품 URL 적용
python -m src.policy_cli coupang-assets 글ID --url "https://link.coupang.com/a/..."
# HTML/iframe/script 소재는 UTF-8 파일로 저장한 뒤 적용
python -m src.policy_cli coupang-assets 글ID --file coupang_banner.html
# 기존 패키지 이미지 3장을 Supabase에 올리고 게시 HTML에 URL 삽입
python -m src.policy_cli upload-images 글ID
```

`collect`는 보조금24 여러 페이지와 공식 지원조건을 검사해 농림·수산업, 기업·특수직역 전용 정책을 숨기고 30~50대 주부·직장인에게 맞는 생활 혜택만 자동 추천한다. `list`에는 추천 상위 후보만 표시되며, 전체 저장 상태가 필요할 때만 `list --all`을 사용한다. `generate-recommended`는 수동 일괄 생성이고, `auto-run`은 하루 한도와 중복 실행을 확인한 뒤 점수·카테고리 분산 순서로 생성한다. 후보가 부족하거나 마지막 전체 수집 후 24시간이 지나면 다시 수집하며 선택 정책은 생성 직전 재검증한다.

생성물은 `output/tistory/YYYY/MM/DD/정책ID_제목/`에 저장된다. `00_게시가이드.txt` 순서대로 제목과 세 구간의 HTML을 복사하고 대표·본문 이미지를 업로드한다. 한 번에 넣을 때는 `02_본문_HTML블록용.txt`, 이미지 사이로 나눠 넣을 때는 `segments/*_HTML블록용.txt`를 티스토리의 **HTML 블록** 또는 HTML 모드에 붙여넣는다. **코드블록은 HTML 소스를 화면에 그대로 표시하므로 본문 입력에 사용하지 않는다.** 사람이 여는 HTML·텍스트 산출물은 macOS 텍스트 편집기의 잘못된 한글 인코딩 추정을 막도록 UTF-8 BOM으로 저장된다.

`05_출처_검증.md`, `07_SEO_게시정보.txt`, `seo/게시전_검사.json`을 확인한 후 먼저 비공개 저장으로 티스토리 스킨과 광고 표시를 점검한다. OpenAI 이미지 일부가 실패하면 `needs_image_retry`로 보관하며 누락된 이미지만 재시도할 수 있다. 게시 URL을 기록하면 `seo/게시후_검사.json`도 생성한다. 이 작업실은 티스토리에 자동 로그인하거나 자동 게시하지 않는다. 애드센스용 소개·개인정보처리방침·문의 페이지는 `output/tistory/pages/`에 별도 수동 게시 패키지로 만든다.

티스토리 글별 쿠팡 소재는 상품 URL, 쿠팡이 발급한 링크+이미지 HTML, iframe, `PartnersCoupang.G` 스크립트를 지원한다. 터미널에서는 소재 코드를 클립보드에 복사한 뒤 수동 글 생성 또는 `20. ...광고 소재 설정`에서 **클립보드 코드**를 선택한다. 웹 작업실은 소재 3개를 각각 별도 칸에 붙여넣는다. 크기는 manifest에 기록되고 모바일 폭을 넘지 않도록 감싸지만, 티스토리가 iframe/script를 제거할 수 있으므로 비공개 게시 후 반드시 확인한다.

`SUPABASE_URL`, `SUPABASE_SECRET_KEY`(레거시는 `SUPABASE_SERVICE_ROLE_KEY`), `SUPABASE_STORAGE_BUCKET`을 설정하고 해당 Storage 버킷을 공개로 만들면, 새 패키지의 대표·본문 이미지 3장을 자동 업로드한다. `02_본문_HTML블록용.txt`, 게시용 HTML과 세 구간 파일에는 Supabase 공개 URL의 `<img>`가 포함된다. 기존 패키지는 `upload-images 글ID` 또는 작업실 18번 이미지 메뉴에서 변환한다. secret/service_role 키는 로컬 `.env`에만 보관하고 Git이나 브라우저 코드에 넣지 않는다.

## 다른 PC에서 이어받기

다른 PC에서 clone 해 이어서 작업하는 전체 절차는 `CONTINUE-ON-NEW-PC.md` 참고. 요약하면 clone → `SETUP.md` 설치 → 개인 시크릿 2개(`.env`, `config/coupang_widget.html`) 준비 → Windows는 `제어판.bat`, macOS는 `./control.sh` 실행이다. 두 운영체제 모두 같은 콘솔 메뉴에서 발행·자동발행·설정·push·애드센스 페이지를 관리한다.
