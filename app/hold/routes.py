"""成品扣货排查接口。"""

from flask import Blueprint, jsonify, request

from app.errors import DomainIssue
from app.hold.service import get_investigation, list_investigations, run_investigation

hold_api = Blueprint("hold_api", __name__)


def hold_store():
    from flask import current_app
    return current_app.extensions["holds"]


@hold_api.post("/api/holds/investigations")
def create_investigation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "suspect" not in payload:
        raise DomainIssue("BAD_REQUEST")
    result, _created = run_investigation(hold_store(), payload)
    return jsonify(result)


@hold_api.get("/api/holds/investigations")
def investigations():
    return jsonify(list_investigations(hold_store()))


@hold_api.get("/api/holds/investigations/<investigation_pk>")
def investigation_detail(investigation_pk):
    return jsonify(get_investigation(hold_store(), investigation_pk))


@hold_api.get("/api/holds/results")
def hold_results():
    """工作台扣货结果查询：汇总所有排查下仍处扣货状态的成品批次。"""
    store = hold_store()
    items = []
    for row in store.list_investigations():
        for hold in store.list_holds(row["id"]):
            if hold["decision"] == "HELD":
                items.append({
                    "investigation_id": row["investigation_ref"],
                    "investigation_pk": row["id"],
                    "fg_batch": hold["fg_batch"],
                    "stage": hold["stage"],
                    "stage_seq": hold["stage_seq"],
                    "qty": hold["qty"],
                    "decision": hold["decision"],
                    "reason": hold["reason"],
                    "updated_at": hold["updated_at"],
                })
    return jsonify({"count": len(items), "holds": items})
