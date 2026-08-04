from src import policy_store


def _candidate():
    return {
        "id": "abc123", "source_type": "gov24", "external_id": "SVC1",
        "title": "중장년 생활비 지원", "category": "생활비·세금·환급",
        "agency": "행정안전부", "region": "전국", "source_url": "https://www.gov.kr/test",
        "official": True, "facts": {"benefit": "10만원 지원"},
        "checked_at": policy_store.now_iso(), "score": 20, "status": "ready",
    }


def test_candidate_and_region_roundtrip(tmp_path):
    db = tmp_path / "workspace.sqlite3"
    policy_store.upsert_candidate(_candidate(), db)
    item = policy_store.get_candidate("abc123", db)
    assert item["official"] is True
    assert item["facts"]["benefit"] == "10만원 지원"
    assert policy_store.list_candidates(path=db)[0]["id"] == "abc123"

    policy_store.set_regions(["서울", " 성남 "], db)
    assert policy_store.get_regions(db) == ["서울", "성남"]

    policy_store.hide_gov24_candidates(db)
    assert policy_store.get_candidate("abc123", db)["status"] == "filtered_out"


def test_package_status_roundtrip(tmp_path):
    db = tmp_path / "workspace.sqlite3"
    policy_store.upsert_candidate(_candidate(), db)
    policy_store.save_package({
        "id": "post1", "candidate_id": "abc123", "title": "제목",
        "category": "생활비·세금·환급", "path": str(tmp_path / "post1"),
        "status": "ready", "created_at": policy_store.now_iso(),
    }, db)
    assert policy_store.get_package("post1", db)["status"] == "ready"
    marked = policy_store.mark_published("post1", "https://example.tistory.com/1", db)
    assert marked["status"] == "published"
    assert marked["tistory_url"].endswith("/1")
