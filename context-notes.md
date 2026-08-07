# 컨텍스트 노트 (결정 기록)

## 2026-08-05 WordPress·티스토리 전수 정비

### 제품 경계

- 메인 제어판 1~16은 WordPress 전용이다. 17번 진입 뒤 1~24는 정책·티스토리 작업실 전용이다.
- WordPress는 실제 REST 게시, 티스토리는 수동 게시용 패키지 생성까지만 자동화한다.
- API 키·LLM 인증·쿠팡 공용 소재는 공유할 수 있지만 편수·시각·광고·로켓·이미지 설정은 서로 변경하지 않는다.

### 설정

- Git 추적 `config/settings.yaml`은 새 설치 공식 기본값만 보관한다.
  - WordPress: 공개, 하루 3편, 09:00.
  - 티스토리: 자동 생성 꺼짐, 하루 1편, 09:30.
- 개인 운영값은 gitignore된 `config/settings.local.yaml`에 쓰고 기본값과 깊은 병합한다.
- `.env`, 개인 쿠팡 소재, SQLite, 생성물, 로그는 Git에 넣지 않는다.

### WordPress 안정성

- 제어판의 “지금 1편”은 설정 하루 편수와 무관하게 `count=1`이다. 예약 실행과 키워드 갱신 발행은 설정 편수를 따른다.
- 파이프라인 실행 잠금, 원자적 발행 이력, 후보별 실패 후 계속, 목표의 3배 최대 시도를 사용한다.
- WordPress POST 전후 동일 slug를 조회해 네트워크 응답 손실에 따른 중복 게시를 막는다.
- Rank Math meta 없이 재시도하는 경우는 meta 관련 400 검증 오류로 한정한다. 인증·권한·서버 오류는 같은 POST를 반복하지 않는다.

### 정책 최신성과 생성

- 보조금24 공식 API와 사용자가 추가한 공식 URL만 정책 사실의 근거로 쓴다.
- 생성 직전에 상세 정보를 다시 확인한다. 실패하면 7일 이내 캐시만 허용하고 종료된 신청기간은 생성하지 않는다.
- 자동 추천은 30~50대 주부·직장인 생활 관련성, 구체적 혜택, 최신성, 카테고리 다양성을 반영하고 이미 생성된 후보를 제외한다.
- 예약 자동 생성은 당일 설정 편수를 넘기지 않으며 사용자 입력을 받지 않는다.

### 티스토리 산출물

- 폴더 단위 패키지를 `output/tistory/YYYY/MM/DD/`에 보관한다.
- 대표 이미지 1장과 본문 이미지 2장을 보관한다. 대표는 Supabase와 manifest에 남지만 본문 HTML에서는 제외하며 사용자가 티스토리에 따로 업로드·대표 지정한다.
- 본문 이미지는 Supabase `blog_image` Public bucket 공개 URL을 사용한다.
- `02_본문_HTML블록용.txt`는 HTML 블록/HTML 모드용이다. 코드블록은 사용하지 않는다.
- 한글 텍스트는 UTF-8 BOM, 모바일 표는 가로 스크롤 래퍼, 체크리스트는 `☐` 한 글자를 사용한다.
- 패키지는 임시 폴더에서 완성한 뒤 최종 이름으로 원자 이동해 중단 시 반쪽 폴더를 줄인다.

### 쿠팡 파트너스

- WordPress와 티스토리는 공통 렌더러·공용 배너 파일을 공유하되 각 플랫폼의 켜기/레이아웃/개수/로켓 설정을 명시적으로 전달한다.
- 티스토리 수동 입력은 URL, 링크+이미지 HTML, iframe, 공식 `PartnersCoupang.G` script를 지원한다.
- `1` URL 후속 입력, `2` 시스템 클립보드 자동 읽기, `3` UTF-8 파일, `0` 완료. 빈 줄은 완료가 아니다.
- 자동 예약 생성은 입력을 받을 수 없어 공식 API/저장된 공용 소재/검색 링크 순으로 처리한다.
- 검색 링크는 파트너스 수익 추적이 보장되지 않는다. 광고 사용 시 고지문구를 첫 광고보다 앞에 두고 제휴 링크에 `nofollow sponsored`를 유지한다.

### LLM·이미지

- `anthropic`: Anthropic API 키 사용. Claude Code 설치·로그인 불필요.
- `gemini`: 유지보수 중단된 `google-generativeai`를 제거하고 `google-genai>=2`, `gemini-3.6-flash`로 이전한다.
- `claude_code`: 로컬 CLI를 명시적으로 선택했을 때만 Node.js와 PC별 로그인이 필요하다.
- LLM 제한 600초와 재시도 1회, OpenAI 이미지 장당 360초와 SDK 재시도 0회를 사용한다. 15초마다 경과 상태를 출력한다.
- OpenAI 기본 이미지는 `gpt-image-2`; ChatGPT/Codex 구독과 API 결제는 별개다. Pollinations는 사용자가 직접 고른 수동 대체 경로다.
- 이미지 일부 실패는 글을 폐기하지 않고 `needs_image_retry`로 남긴다.

### 스케줄러

- Windows WordPress: `blog-auto` → `run.bat` → `logs/pipeline.log`.
- Windows 티스토리: `blog-policy-tistory-auto` → `policy_run.bat` → `logs/policy_pipeline.log`.
- macOS WordPress: `com.wordpress-auto-blog.pipeline` LaunchAgent.
- macOS 티스토리: `com.wordpress-auto-blog.policy-tistory` LaunchAgent.
- 두 예약은 등록·상태·해제·시각·작업 이름·로그를 공유하지 않는다. LaunchAgent는 사용자 세션에서 실행하고 `RunAtLoad`를 사용하지 않는다.

### 보안·진단·배포

- 로컬 대시보드의 상태 변경 POST는 난수 쿠키 토큰과 Host/Origin 검증을 통과해야 한다.
- `python -m src.doctor`는 로컬 진단, `--live`는 보조금24·Supabase·WordPress 읽기 전용 확인이다. 실제 게시·유료 LLM·이미지는 호출하지 않는다.
- GitHub 메뉴는 변경 목록·브랜치·원격 → 전체 테스트 → 마스킹된 비밀값 검사 → 사용자 확인 → commit/push 순서다. `git add .`와 고정 `update` 메시지를 사용하지 않는다.
- GitHub Actions는 Ubuntu·Windows·macOS, Python 3.12에서 외부 키 없이 테스트·compileall·설정 파싱·셸 문법·전체 Git 이력 비밀값 검사를 수행한다.
- GitHub CLI 인증은 이 PC 상태이므로 `gh auth status`를 실제로 확인하기 전 성공했다고 기록하지 않는다. 일반 `git push`는 `gh`에 의존하지 않는다.

## 2026-08-04 macOS 지원 결정

- Windows 지원을 보존하고 macOS를 동등한 터미널 실행 대상으로 추가했다.
- macOS 자동화는 관리자 권한이 필요한 LaunchDaemon이 아닌 로그인 사용자의 LaunchAgent다.
- launchd가 터미널 PATH를 자동 상속하지 않으므로 등록 시 현재 PATH를 plist에 기록한다. Node/Claude 위치가 바뀌면 관련 작업을 다시 등록한다.
- 공식 진입점은 Windows `제어판.bat`/`run.bat`, macOS `control.sh`/`run.sh`다.

## 유지할 운영 원칙

- 외부 사실과 금액·대상·기간을 LLM이 추측하지 않는다.
- 실제 게시·유료 호출·스케줄러 등록·GitHub push는 자동 테스트에 포함하지 않는다.
- 기존 개인 파일과 미커밋 변경을 보존하고, 파괴적 Git 명령을 사용하지 않는다.
- 원격에 push가 끝나기 전에는 GitHub가 최신이라고 표현하지 않는다.
