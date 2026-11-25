"""扣货请求整理：必填校验、空值归一与隔离问题。"""

import pytest

from app.errors import DomainIssue
from app.hold.normalize import normalize_investigation
from tests.hold_cases import handover, report, two_line_payload


def test_valid_payload_is_normalized():
    normalized = normalize_investigation(two_line_payload([]))
    assert normalized["suspect"] == {"stage": "冲压", "material_batch": "BAD"}
    assert len(normalized["work_reports"]) == 4


def test_suspect_stage_and_batch_are_required():
    with pytest.raises(ValueError) as first:
        normalize_investigation({"suspect": {"material_batch": "BAD"}, "work_reports": [], "handovers": []})
    with pytest.raises(ValueError) as second:
        normalize_investigation({"suspect": {"stage": "冲压"}, "work_reports": [], "handovers": []})
    assert first.value.code == "SUSPECT_STAGE_MISSING"
    assert second.value.code == "SUSPECT_BATCH_MISSING"


def test_blank_sentinels_are_treated_as_missing():
    payload = two_line_payload([])
    payload["suspect"]["material_batch"] = "未提供"
    with pytest.raises(ValueError) as exc:
        normalize_investigation(payload)
    assert exc.value.code == "SUSPECT_BATCH_MISSING"


def test_report_requires_inputs_and_outputs():
    payload = two_line_payload([])
    payload["work_reports"][0]["outputs"] = []
    normalized = normalize_investigation(payload)
    assert any(issue["code"] == "REPORT_WITHOUT_MOVEMENT" for issue in normalized["issues"])


def test_bad_quantity_is_isolated_not_raised():
    payload = two_line_payload([])
    payload["work_reports"][0]["inputs"][0]["qty"] = -5
    normalized = normalize_investigation(payload)
    assert any(issue["code"] == "BAD_INPUT_QTY" for issue in normalized["issues"])


def test_handover_without_destinations_is_total_only():
    normalized = normalize_investigation(
        two_line_payload([handover("H1", "冲压", 1, 200, 200)]))
    handover_item = normalized["handovers"][0]
    assert handover_item["detail_registered"] is False
    assert handover_item["total_matches"] is True


def test_fullwidth_digits_are_canonical():
    payload = two_line_payload([])
    payload["work_reports"][0]["inputs"][0]["qty"] = "１００"
    normalized = normalize_investigation(payload)
    assert normalized["work_reports"][0]["inputs"][0]["qty"] == 100


def test_service_raises_domain_issue_for_bad_payload(client):
    response = client.post("/api/holds/investigations", json={"suspect": {}})
    assert response.status_code == 400
    assert response.get_json()["code"] == "SUSPECT_STAGE_MISSING"
