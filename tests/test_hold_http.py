"""成品扣货接口：排查创建、幂等重跑、结果查询与恢复放行。"""

from tests.hold_cases import handover, two_line_payload


def create_investigation(client, payload):
    response = client.post("/api/holds/investigations", json=payload)
    assert response.status_code == 200, response.data
    return response.get_json()


def test_create_investigation_returns_hold_decisions(client):
    result = create_investigation(client, two_line_payload([handover("H1", "冲压", 1, 200, 198)]))
    assert result["summary"]["held_batches"] == 2
    assert result["summary"]["mismatched_handovers"] == ["H1"]
    assert len(result["holds"]) == 2


def test_rerun_is_idempotent_over_http(client):
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 198)])
    first = create_investigation(client, payload)
    second = create_investigation(client, payload)
    # 规则6：同一次排查重跑不重复生成扣货记录
    assert first["investigation_pk"] == second["investigation_pk"]
    assert second["revision"] == 2
    assert len(second["holds"]) == 2


def test_workbench_can_query_held_finished_goods(client):
    # 规则7：工作台能查成品扣货结果
    create_investigation(client, two_line_payload([handover("H1", "冲压", 1, 200, 200)]))
    response = client.get("/api/holds/results")
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 1
    assert body["holds"][0]["fg_batch"] == "FG-A"
    assert body["holds"][0]["decision"] == "HELD"


def test_late_handover_restores_release_and_results_reflect_it(client):
    # 规则5：晚到交接补齐去向后，证实无涉的成品恢复放行
    create_investigation(client, two_line_payload([handover("H1", "冲压", 1, 200, 198)]))
    fixed = two_line_payload([
        handover("H1", "冲压", 1, 200, 200, destinations=[("S-A", 100), ("S-B", 100)])])
    updated = create_investigation(client, fixed)
    by_batch = {item["fg_batch"]: item for item in updated["results"]}
    assert by_batch["FG-A"]["decision"] == "HELD"
    assert by_batch["FG-B"]["decision"] == "RELEASED"
    held = client.get("/api/holds/results").get_json()
    assert held["count"] == 1
    assert held["holds"][0]["fg_batch"] == "FG-A"


def test_investigation_detail_and_listing(client):
    created = create_investigation(client, two_line_payload([]))
    detail = client.get(f"/api/holds/investigations/{created['investigation_pk']}")
    assert detail.status_code == 200
    assert detail.get_json()["investigation_pk"] == created["investigation_pk"]
    listing = client.get("/api/holds/investigations")
    assert listing.status_code == 200
    assert any(item["investigation_pk"] == created["investigation_pk"] for item in listing.get_json())


def test_unknown_investigation_returns_404(client):
    response = client.get("/api/holds/investigations/nope1234567")
    assert response.status_code == 404
    assert response.get_json()["code"] == "INVESTIGATION_NOT_FOUND"


def test_create_requires_suspect(client):
    response = client.post("/api/holds/investigations", json={"work_reports": []})
    assert response.status_code == 400
    assert response.get_json()["code"] == "BAD_REQUEST"
