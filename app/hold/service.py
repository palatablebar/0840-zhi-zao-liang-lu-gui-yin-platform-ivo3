"""成品扣货排查的应用服务：整理、判定、幂等持久化与序列化。"""

import hashlib
import json

from app.errors import DomainIssue
from app.hold.engine import evaluate
from app.hold.normalize import normalize_investigation


def request_key_of(payload):
    """同一排查的稳定键。

    显式 investigation_id 标识同一次排查：补记报工/交接后重跑仍落到同一记录，
    只更新结论与版本号，不重复生成扣货记录；未给标识时按内容生成稳定键，
    保证完全相同的请求天然幂等。
    """
    explicit = (payload or {}).get("investigation_id")
    if explicit:
        return "ref:" + str(explicit).strip()
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(("hold:" + body).encode("utf-8")).hexdigest()[:24]


def run_investigation(store, payload):
    try:
        normalized = normalize_investigation(payload)
    except ValueError as exc:
        raise DomainIssue(str(exc), 400)
    evaluation = evaluate(normalized)
    request_key = request_key_of(payload)
    investigation_ref = normalized["investigation_id"] or request_key
    row, created = store.upsert(request_key, investigation_ref, payload, evaluation)
    return serialize(row, store.list_holds(row["id"])), created


def serialize(row, holds=None):
    if row is None:
        return None
    evaluation = json.loads(row["result_text"])
    result = {
        "investigation_pk": row["id"],
        "investigation_id": row["investigation_ref"],
        "status": row["status"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "suspect": evaluation["suspect"],
        "summary": evaluation["summary"],
        "issues": evaluation.get("issues", []),
        "results": evaluation["results"],
        "holds": [],
    }
    if holds is None:
        return result
    result["holds"] = [{
        "fg_batch": item["fg_batch"], "stage": item["stage"], "stage_seq": item["stage_seq"],
        "qty": item["qty"], "decision": item["decision"], "reason": item["reason"],
        "updated_at": item["updated_at"],
    } for item in holds]
    return result


def get_investigation(store, investigation_pk):
    row = store.get(investigation_pk)
    if row is None:
        raise DomainIssue("INVESTIGATION_NOT_FOUND", 404)
    return serialize(row, store.list_holds(investigation_pk))


def list_investigations(store):
    rows = store.list_investigations()
    return [serialize(row) for row in rows]
