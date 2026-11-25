"""成品扣货排查测试夹具与场景构造。"""

from app.hold.engine import evaluate
from app.hold.normalize import normalize_investigation


def report(report_id, stage, seq, inputs, outputs):
    return {"report_id": report_id, "stage": stage, "stage_seq": seq,
            "inputs": [{"batch": b, "qty": q} for b, q in inputs],
            "outputs": [{"batch": b, "qty": q} for b, q in outputs]}


def handover(handover_id, stage, seq, from_qty, to_qty, destinations=None):
    item = {"handover_id": handover_id, "stage": stage, "stage_seq": seq,
            "from_qty": from_qty, "to_qty": to_qty}
    if destinations is not None:
        item["destinations"] = [{"batch": b, "qty": q} for b, q in destinations]
    return item


def two_line_payload(handovers):
    """FG-A 源自可疑料 BAD；FG-B 全程源自干净原料 OK。"""
    return {
        "investigation_id": "INV-T1",
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            report("W1", "冲压", 1, [("BAD", 100)], [("S-A", 100)]),
            report("W2", "冲压", 1, [("OK", 100)], [("S-B", 100)]),
            report("W3", "焊接", 2, [("S-A", 100)], [("FG-A", 100)]),
            report("W4", "焊接", 2, [("S-B", 100)], [("FG-B", 100)]),
        ],
        "handovers": handovers,
    }


def evaluate_payload(payload):
    return evaluate(normalize_investigation(payload))


def decisions(payload):
    return {item["fg_batch"]: (item["decision"], item["reason"])
            for item in evaluate_payload(payload)["results"]}
