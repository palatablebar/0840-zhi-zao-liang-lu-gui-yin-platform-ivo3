"""扣货存储：同一次排查重跑不重复生成扣货记录，晚到记录可更新结论。"""

from app.hold.service import get_investigation, run_investigation
from app.hold.store import HoldStore
from tests.hold_cases import handover, two_line_payload


def make_store(tmp_path):
    return HoldStore(str(tmp_path / "holds.sqlite3"))


def test_first_run_creates_holds(tmp_path):
    store = make_store(tmp_path)
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 198)])
    result, created = run_investigation(store, payload)
    assert created is True
    assert result["revision"] == 1
    assert len(result["holds"]) == 2
    assert all(hold["decision"] == "HELD" for hold in result["holds"])


def test_rerun_same_investigation_does_not_duplicate_holds(tmp_path):
    store = make_store(tmp_path)
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 198)])
    first, created_first = run_investigation(store, payload)
    second, created_second = run_investigation(store, payload)
    assert created_first is True and created_second is False
    assert first["investigation_pk"] == second["investigation_pk"]
    assert second["revision"] == 2
    # 规则6：扣货记录不重复生成
    assert len(store.list_holds(first["investigation_pk"])) == 2
    assert {hold["fg_batch"] for hold in second["holds"]} == {"FG-A", "FG-B"}


def test_late_handover_releases_clean_batch_without_new_hold_rows(tmp_path):
    store = make_store(tmp_path)
    mismatched = two_line_payload([handover("H1", "冲压", 1, 200, 198)])
    first, _ = run_investigation(store, mismatched)
    # 晚到的交接补齐数量与逐批去向
    fixed = two_line_payload([
        handover("H1", "冲压", 1, 200, 200, destinations=[("S-A", 100), ("S-B", 100)])])
    second, created = run_investigation(store, fixed)
    assert created is False
    assert len(store.list_holds(first["investigation_pk"])) == 2  # 仍是同一批扣货记录
    by_batch = {hold["fg_batch"]: hold for hold in second["holds"]}
    assert by_batch["FG-A"]["decision"] == "HELD"
    assert by_batch["FG-B"]["decision"] == "RELEASED"
    persisted = get_investigation(store, first["investigation_pk"])
    assert persisted["summary"]["held_batches"] == 1
    assert persisted["summary"]["released_batches"] == 1


def test_distinct_investigations_are_separate(tmp_path):
    store = make_store(tmp_path)
    first, _ = run_investigation(store, two_line_payload([]))
    other = two_line_payload([])
    other["investigation_id"] = "INV-T2"
    other["suspect"]["material_batch"] = "OTHER-BAD"
    second, created = run_investigation(store, other)
    assert created is True
    assert first["investigation_pk"] != second["investigation_pk"]
    assert len(store.list_investigations()) == 2


def test_content_key_when_no_investigation_id(tmp_path):
    store = make_store(tmp_path)
    payload = two_line_payload([])
    payload.pop("investigation_id")
    first, created_first = run_investigation(store, payload)
    second, created_second = run_investigation(store, payload)
    assert created_first is True and created_second is False
    assert first["investigation_pk"] == second["investigation_pk"]
