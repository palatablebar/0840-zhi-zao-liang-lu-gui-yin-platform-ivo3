"""排查请求的整理与前置校验。

输入结构（均为 JSON）：

    {
      "investigation_id": "INV-20261125-01",   # 可选，缺省按内容生成稳定标识
      "suspect": {"stage": "冲压", "material_batch": "MB-BAD-09"},
      "work_reports": [
        {"report_id": "W1", "stage": "冲压", "stage_seq": 1,
         "inputs": [{"batch": "MB-BAD-09", "qty": 100}],
         "outputs": [{"batch": "S1", "qty": 100}]}
      ],
      "handovers": [
        {"handover_id": "H1", "stage": "冲压", "stage_seq": 1,
         "from_qty": 100, "to_qty": 100,
         "destinations": [{"batch": "S1", "qty": 100}]}
      ]
    }

报工允许一次投入多个批次（混装）、一次拆出多个批次（批次拆分），
用 inputs/outputs 记录每笔去向和数量。交接 destinations 可缺省，
缺省表示只登记总量、未登记逐批次去向。
"""

from app.intake.normalize import canonical


class HoldValidationError(ValueError):
    """携带原因码的整理层校验异常，便于映射为 DomainIssue。"""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _text(value, code):
    text = canonical(value)
    if not text:
        raise HoldValidationError(code)
    return text


def _qty(value, code):
    text = canonical(value)
    if not text:
        raise HoldValidationError(code)
    try:
        number = int(text)
    except (TypeError, ValueError):
        raise HoldValidationError(code)
    if number < 0:
        raise HoldValidationError(code)
    return number


def _batch_move(entry, kind, index, issues):
    batch = _text(entry.get("batch"), f"BAD_{kind}_BATCH")
    qty = _qty(entry.get("qty"), f"BAD_{kind}_QTY")
    return {"batch": batch, "qty": qty}


def _report(raw, issues):
    report_id = _text(raw.get("report_id"), "BAD_REPORT_ID")
    stage = _text(raw.get("stage"), "BAD_REPORT_STAGE")
    stage_seq = _qty(raw.get("stage_seq"), "BAD_REPORT_SEQ")
    if stage_seq <= 0:
        raise HoldValidationError("BAD_REPORT_SEQ")
    inputs, outputs = [], []
    for entry in raw.get("inputs") or []:
        try:
            inputs.append(_batch_move(entry, "INPUT", 0, issues))
        except ValueError as exc:
            issues.append({"source": "work_report", "ref": report_id, "code": str(exc)})
    for entry in raw.get("outputs") or []:
        try:
            outputs.append(_batch_move(entry, "OUTPUT", 0, issues))
        except ValueError as exc:
            issues.append({"source": "work_report", "ref": report_id, "code": str(exc)})
    if not inputs or not outputs:
        raise HoldValidationError("REPORT_WITHOUT_MOVEMENT")
    return {"report_id": report_id, "stage": stage, "stage_seq": stage_seq,
            "inputs": inputs, "outputs": outputs}


def _handover(raw, issues):
    handover_id = _text(raw.get("handover_id"), "BAD_HANDOVER_ID")
    stage = _text(raw.get("stage"), "BAD_HANDOVER_STAGE")
    stage_seq = _qty(raw.get("stage_seq"), "BAD_HANDOVER_SEQ")
    if stage_seq <= 0:
        raise HoldValidationError("BAD_HANDOVER_SEQ")
    from_qty = _qty(raw.get("from_qty"), "BAD_FROM_QTY")
    to_qty = _qty(raw.get("to_qty"), "BAD_TO_QTY")
    destinations = []
    for entry in raw.get("destinations") or []:
        try:
            destinations.append(_batch_move(entry, "DEST", 0, issues))
        except ValueError as exc:
            issues.append({"source": "handover", "ref": handover_id, "code": str(exc)})
    detail_registered = bool(raw.get("destinations"))
    return {"handover_id": handover_id, "stage": stage, "stage_seq": stage_seq,
            "from_qty": from_qty, "to_qty": to_qty,
            "destinations": destinations, "detail_registered": detail_registered,
            "total_matches": from_qty == to_qty}


def normalize_investigation(payload):
    """返回整理后的排查请求与隔离问题。问题不阻断，但会进入排查说明。"""
    if not isinstance(payload, dict):
        raise HoldValidationError("BAD_REQUEST")
    suspect_raw = payload.get("suspect") or {}
    suspect = {
        "stage": _text(suspect_raw.get("stage"), "SUSPECT_STAGE_MISSING"),
        "material_batch": _text(suspect_raw.get("material_batch"), "SUSPECT_BATCH_MISSING"),
    }
    issues = []
    reports = []
    for raw in payload.get("work_reports") or []:
        try:
            reports.append(_report(raw, issues))
        except ValueError as exc:
            issues.append({"source": "work_report",
                           "ref": canonical(raw.get("report_id")) if isinstance(raw, dict) else "",
                           "code": str(exc)})
    handovers = []
    for raw in payload.get("handovers") or []:
        try:
            handovers.append(_handover(raw, issues))
        except ValueError as exc:
            issues.append({"source": "handover",
                           "ref": canonical(raw.get("handover_id")) if isinstance(raw, dict) else "",
                           "code": str(exc)})
    investigation_id = canonical(payload.get("investigation_id"))
    return {
        "investigation_id": investigation_id,
        "suspect": suspect,
        "work_reports": reports,
        "handovers": handovers,
        "issues": issues,
    }
