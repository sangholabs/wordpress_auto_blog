# 수익형 블로그 자동화 파이프라인

WordPress 블로그에 쿠팡 파트너스 + 구글 애드센스 수익형 콘텐츠를 자동으로 기획·생성·게시하는 독립 프로젝트다. clone 후 `.env`만 채우면 다른 PC에서도 바로 동작하도록 설계한다.

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

## 설치·실행

`SETUP.md` 참고. 전역(Python/Node)은 PC에 설치, 의존성은 프로젝트 `.venv`에 격리 설치한다.

## 진행 상황

`checklist.md`(할 일)와 `context-notes.md`(결정 기록)에서 관리한다.

## 보안 / 배포

이 저장소에는 어떤 개인정보·시크릿도 포함되지 않는다. 다음 항목은 모두 `.gitignore`로 제외된다.

- `.env` (WordPress·API 키 등) — `.env.example`을 복사해 직접 채운다.
- `config/coupang_widget.html` (쿠팡 추적코드 포함) — `config/coupang_widget.example.html` 참고해 직접 만든다.
- `data/`, `logs/`, `output/`, 로그인 세션 프로필 — 실행 중 생성되는 로컬 데이터.

clone 후에는 `SETUP.md`의 순서대로 본인 환경·자격증명만 채우면 바로 동작한다. 커밋 전에는 항상 `git status`로 위 파일들이 추적되지 않는지 확인한다.
