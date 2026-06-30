# 주제 점수화 로직 단위 테스트 (네트워크 불필요, 오프라인 검증)
from src.topic_queue import score_keyword


def test_intent_word_boosts_score():
    assert score_keyword("에어프라이어 추천") > score_keyword("에어프라이어")


def test_longtail_range_scores_higher_than_single_word():
    assert score_keyword("가성비 로봇청소기 비교") > score_keyword("청소기")


def test_score_is_non_negative():
    assert score_keyword("a") >= 0
