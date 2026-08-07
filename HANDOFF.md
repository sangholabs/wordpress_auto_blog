# 운영 인수인계 (2026-08-05)

## 1. 프로젝트 범위

한 저장소에 두 흐름이 있다.

- WordPress: 생활·리빙·가전 글을 생성해 설치형 WordPress REST API로 자동 게시한다.
- 티스토리 정책 작업실: 30~50대 주부·직장인에게 유용한 공식 정책을 수집해 제목·본문·대표/본문 이미지·출처·SEO 패키지를 만든다. 티스토리 게시는 사용자가 수동으로 한다.

메인 제어판 1~16은 WordPress, 17번 내부의 1~24는 티스토리다. 공용 API 키와 쿠팡 소재를 제외한 편수·시각·광고·이미지 동작 설정은 서로 독립적이다.

## 2. 현재 코드 상태

- 로컬 브랜치: `main`
- 현재 기준 커밋: `455def9`
- 원격: `https://github.com/sangholabs/wordpress_auto_blog.git`
- 이 문서 작성 시점에는 안정성·Tistory 대표 이미지 본문 제거·문서·CI 변경이 아직 커밋/푸시되지 않은 로컬 변경으로 남아 있다. 따라서 원격을 최신 구현이라고 표시하면 안 된다.
- 실제 게시, 유료 LLM·OpenAI 이미지, 예약 등록, GitHub push는 정비 검증 중 실행하지 않았다.

GitHub CLI의 기존 `sangholabs` 토큰은 현재 유효하지 않다. PR 등 `gh` 기능을 쓰기 전 아래 두 번째 명령이 성공하는지 확인한다.

```sh
gh auth login -h github.com
gh auth status
```

일반 `git push`는 Git 자격증명 관리자를 사용하며 `gh` 로그인과 별개다.

## 3. 주요 안정성 변경

### WordPress

- `pipeline.run(refresh_keywords=False, count=None)`과 `python -m src.pipeline --count N [--refresh]`를 지원한다.
- 제어판의 “지금 1편”은 정확히 `count=1`; 예약과 키워드 갱신 발행은 설정 하루 편수를 사용한다.
- 실행 잠금, 후보별 실패 후 계속 진행, 목표 편수의 3배 최대 시도, 원자적 `published.json` 저장을 적용했다.
- 게시 전후 같은 slug를 조회해 응답 타임아웃 때문에 같은 글을 다시 POST하는 것을 막는다.
- Rank Math meta 제거 재시도는 실제 meta 검증 400 오류에만 수행한다.
- Windows `run.bat`이 로그 폴더를 먼저 만들고 macOS `run.sh`는 프로젝트 경로와 UTF-8을 고정한다.

### 티스토리

- 수동 일괄 생성은 각 글마다 쿠팡 소재를 별도로 받는다. `1` URL 입력, `2` 클립보드 자동 읽기, `3` 코드 파일, `0` 완료이고 빈 줄은 다시 선택한다.
- LLM 600초, OpenAI 이미지 장당 360초, SDK 자동 재시도 0회, 15초 경과 메시지를 적용했다.
- 정상 장기 작업이 stale 처리되지 않도록 후보 생성 heartbeat를 갱신한다.
- 패키지를 임시 폴더에서 만들고 manifest까지 완료된 뒤 최종 폴더로 이동한다. 실패 시 임시 폴더를 정리한다.
- 대표 이미지는 로컬 파일·Supabase `blog_image`·manifest에 보존하지만 본문 HTML에는 넣지 않는다. 본문 이미지 2장만 공개 URL로 들어간다.
- 이미지 일부 실패는 패키지를 보존하고 `needs_image_retry`로 처리한다.

### 공통

- 추적 설정 `config/settings.yaml`과 PC별 `config/settings.local.yaml`을 깊은 병합한다.
- 공식 기본값: WordPress 공개/하루 3편/09:00, 티스토리 자동 생성 꺼짐/하루 1편/09:30.
- 로컬 대시보드 POST 요청에 난수 쿠키 토큰과 Host/Origin 검증을 적용했다.
- GitHub 메뉴는 상태 표시 → 전체 테스트 → 비밀값 검사 → 명시적 확인 → 입력한 메시지로 commit → push 순서다.
- Gemini는 `google-genai>=2`와 `gemini-3.6-flash`로 이전했다.
- `python -m src.doctor [--live]`와 3개 운영체제 GitHub Actions를 추가했다.

## 4. 로컬 개인 상태

다음은 Git에서 제외되므로 새 PC나 새 작업자가 GitHub에서 받을 수 없다.

- `.env`
- `config/settings.local.yaml`
- `config/coupang_widget.html`
- `data/published.json`, `data/policy_workspace.sqlite3`
- `output/`, `logs/`, `.venv/`

현재 PC의 운영값은 로컬 설정에 남기고 새 설치 기본값과 섞지 않는다. 개인 키나 생성물의 실제 내용은 문서·커밋 메시지·로그에 복사하지 않는다.

## 5. 검증과 설치 주의

검증 명령:

```sh
./.venv/bin/python -m pytest -q
./.venv/bin/python -m compileall -q src tests
./.venv/bin/python -m src.secret_scan
./.venv/bin/python -m src.secret_scan --history
zsh -n control.sh run.sh
./.venv/bin/python -m src.doctor
./.venv/bin/python -m src.doctor --live
```

정비 과정에서 `requirements.txt` 설치 승인이 실행 환경의 사용 한도 때문에 거절됐다. 따라서 현재 `.venv`에 새 `google-genai`가 실제 설치됐다고 가정하면 안 된다. 사용자가 다음을 한 번 실행한 뒤 doctor 결과를 확인해야 한다.

```sh
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m src.doctor
```

`doctor --live`는 보조금24·Supabase·WordPress를 읽기 전용으로만 검사한다. 게시나 유료 생성은 하지 않는다.

## 6. 운영 명령

제어판:

```sh
./control.sh
```

WordPress:

```sh
python -m src.pipeline --count 1
python -m src.schedule_task on|status|off
```

티스토리:

```sh
python -m src.policy_cli collect
python -m src.policy_cli generate-recommended --count 5
python -m src.policy_cli remove-featured-from-body --all
python -m src.policy_schedule_task on|status|off
```

셸의 `on|status|off`는 설명 표기다. 실제 실행 때는 하나만 선택한다(예: `python -m src.schedule_task status`).

## 7. 다음 인수자의 완료 조건

1. `requirements.txt`를 현재 `.venv`에 설치하고 doctor의 의존성 검사를 통과시킨다.
2. 전체 테스트·compileall·YAML·셸 문법·현재/전체 Git 이력 비밀값 검사를 통과시킨다.
3. 실제 게시·유료 호출 없이 기존 티스토리 패키지를 로컬 재빌드해 대표 이미지가 본문에서만 제외되는지 확인한다.
4. 변경 목록을 검토한 뒤에만 사용자의 별도 확인을 받고 commit/push한다.

설치 상세는 [SETUP.md](SETUP.md), 새 PC 이전 범위는 [CONTINUE-ON-NEW-PC.md](CONTINUE-ON-NEW-PC.md)를 따른다.
