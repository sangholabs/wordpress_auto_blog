# 체크리스트

## 0. 환경 (사용자 PC, 전역 설치)
- [ ] Python 3.11+ 설치 (전역) → verify: `python --version`
- [ ] Node.js LTS 설치 (전역, Playwright/일부 도구용) → verify: `node -v`
- [ ] 프로젝트 venv 생성 + 의존성 설치 → verify: `pip list`에 requests 등 노출
- [ ] Playwright 브라우저 설치 → verify: `playwright install` 성공

## 1. 자격증명 발급 (사용자)
- [ ] WordPress.com 현재 플랜 확인 (REST API 게시 가능 여부)
- [ ] WordPress.com OAuth2 앱 등록 → client_id/secret 발급
- [ ] 쿠팡 파트너스 트래킹 ID 확보
- [ ] 애드센스 승인 상태 확인 (글 30편 축적 후 신청 권장)
- [ ] LLM provider/예산 결정 → API 키 발급

## 2. 설계 (완료/진행)
- [x] 니치 선정: 생활/리빙·가전
- [x] 산출물 형태: 독립 프로젝트 + cron
- [x] 카테고리 초안: config/categories.yaml
- [ ] 인기 블로그 디자인 벤치마크 → 테마/레이아웃 가이드 문서화

## 3. 파이프라인 구현
- [x] src/config.py — .env/yaml 로더
- [x] src/keyword_research.py — 자동완성/연관검색어 수집 → verify(PC): 키워드 수집
- [x] src/topic_queue.py — 스코어링·중복제거 → verify(PC): 우선순위 큐 생성
- [x] src/llm_provider.py — claude_code/gemini/anthropic 추상화 + 사용량 로깅
- [x] tests/test_topic_queue.py — 점수화 오프라인 테스트
- [x] src/prompts.py — SEO/한국어 문체 프롬프트
- [x] src/generate_post.py — SEO 구조 글 생성 → verify(PC): min_chars 충족
- [x] src/formatter.py — 목차/쿠팡링크/고지문구/스타일 → verify(PC): 미리보기 HTML
- [x] src/wp_auth.py — WordPress.com OAuth2 토큰 1회 발급
- [x] src/wp_publish.py — REST API 게시 → verify(PC): draft 1건 생성 확인
- [x] src/pipeline.py — 전체 오케스트레이션 → verify(PC): end-to-end 1건 ✅ (draft 발행 확인)

## 4. 자동화
- [x] run.bat + 작업 스케줄러 등록 안내 (SETUP 8단계) → verify(PC): 1일 1회 실행
- [x] 실행 로그 logs/pipeline.log, 발행 기록 data/published.json

## 5. 검증·배포
- [x] 단위 테스트 작성·통과 → verify: `pytest`
- [x] 더미데이터/비밀정보 누출 점검 → verify: `git ls-files` 시크릿 없음 확인
- [x] README/SETUP 최종 점검 후 GitHub 배포 완료
