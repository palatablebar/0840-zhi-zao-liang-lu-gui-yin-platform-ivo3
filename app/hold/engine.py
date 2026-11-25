"""成品扣货判定引擎。

两层判定：

1. 报工批次血缘（work_reports）：以投入/产出批次建立有向图，
   沿工序顺序追溯每个成品批次是否由可疑来料批次转化而来。
   - 首道工序的叶子投入视为原料批次：非可疑即干净；
   - 后道工序消费、却没有任何报工产出的批次属于断链中间批，
     其下游成品无法证实未混入（报工补记后可解除）。
2. 交接对账（handovers）：
   - 交接数量对不上（from_qty != to_qty）：经过该交接的成品一律不得放行；
   - 只有总量、没有逐批次去向：能证实没混到的批次当天照发，
     断链或可能混到的成品全部扣住；
   - 晚到的交接记录补齐逐批次去向后，证实无涉的成品恢复放行。

同一输入始终产出同一结论；重跑幂等由存储层保证（app/hold/store.py）。
"""

from app.hold.reasons import (
    CLEAN_LINEAGE,
    CLEAR_PATH,
    DECISION_HELD,
    DECISION_RELEASED,
    HANDOVER_CONFIRMED_CLEAN,
    HANDOVER_MISMATCH,
    HANDOVER_MISSING,
    LINEAGE_GAP,
    MIX_UNVERIFIED,
    SUSPECT_LINEAGE,
)


def _lineage_graph(reports):
    produced_by = {}
    consumed_in = {}
    producing_stage = {}
    for report in reports:
        stage_key = (report["stage"], report["stage_seq"])
        for move in report["outputs"]:
            produced_by.setdefault(move["batch"], report)
            producing_stage[move["batch"]] = stage_key
        for move in report["inputs"]:
            consumed_in.setdefault(move["batch"], []).append(report)
    return produced_by, consumed_in, producing_stage


def _walk(batch, produced_by):
    """返回 (全部祖先批次含自身, 经过的工序集合)。环即停。"""
    ancestors = set()
    stages = set()
    stack = [batch]
    while stack:
        current = stack.pop()
        if current in ancestors:
            continue
        ancestors.add(current)
        report = produced_by.get(current)
        if report is None:
            continue
        stages.add((report["stage"], report["stage_seq"]))
        for move in report["inputs"]:
            stack.append(move["batch"])
    return ancestors, stages


def _descendants(batch, consumed_in):
    seen = {batch}
    stack = [batch]
    while stack:
        current = stack.pop()
        for report in consumed_in.get(current, []):
            for move in report["outputs"]:
                if move["batch"] not in seen:
                    seen.add(move["batch"])
                    stack.append(move["batch"])
    return seen


def _stage_order(reports):
    return sorted({(r["stage"], r["stage_seq"]) for r in reports}, key=lambda item: item[1])


def _handovers_by_stage(handovers):
    grouped = {}
    for handover in handovers:
        grouped.setdefault((handover["stage"], handover["stage_seq"]), []).append(handover)
    return grouped


def _representative_at_stage(batch, stage_key, produced_by):
    """成品批次在指定工序上的对应批次：该工序产出的祖先（或自身）。"""
    if producing_stage_of(batch, produced_by) == stage_key:
        return batch
    cursor_batch = batch
    guard = 0
    while guard < 10000:
        guard += 1
        report = produced_by.get(cursor_batch)
        if report is None:
            return None
        for move in report["inputs"]:
            ancestor = move["batch"]
            ancestor_stage = producing_stage_of(ancestor, produced_by)
            if ancestor_stage == stage_key:
                return ancestor
            if ancestor_stage is not None and ancestor_stage[1] < stage_key[1]:
                candidate = _representative_at_stage(ancestor, stage_key, produced_by)
                if candidate:
                    return candidate
        cursor_batch = report["inputs"][0]["batch"] if report["inputs"] else None
        if cursor_batch is None:
            return None
    return None


def producing_stage_of(batch, produced_by):
    report = produced_by.get(batch)
    if report is None:
        return None
    return report["stage"], report["stage_seq"]


def _open_intermediates(reports, produced_by, consumed_in):
    """后道工序消费但无报工产出的断链中间批（首道原料不算断链）。"""
    open_batches = set()
    for batch, consumers in consumed_in.items():
        if batch in produced_by:
            continue
        first_stage = min(report["stage_seq"] for report in consumers)
        if first_stage > 1:
            open_batches.add(batch)
    return open_batches


def _handover_kind(handover):
    if not handover["total_matches"]:
        return "mismatch"
    if handover["detail_registered"]:
        return "detailed"
    return "total_only"


def _evaluate_one(batch, tainted, unresolved, produced_by, stage_order, handover_map):
    ancestors, passed_stages = _walk(batch, produced_by)
    lineage_tainted = batch in tainted
    lineage_open = bool(ancestors & unresolved)

    mismatch = None
    unverified = False
    missing = False
    confirmed_path = False
    for stage_key in sorted(passed_stages, key=lambda item: item[1]):
        handovers = handover_map.get(stage_key)
        if not handovers:
            # 该工序之后仍有交接，说明交接应已发生却缺记录
            if any(key[1] > stage_key[1] for key in handover_map):
                missing = True
            continue
        representative = _representative_at_stage(batch, stage_key, produced_by)
        for handover in handovers:
            kind = _handover_kind(handover)
            if kind == "mismatch":
                mismatch = handover
                break
            if kind == "total_only":
                # 总量一致但无逐批去向：断链成品无法排除混装；血缘干净的当天照发
                if lineage_open:
                    unverified = True
            else:
                listed = representative is not None and any(
                    move["batch"] == representative for move in handover["destinations"])
                if listed:
                    confirmed_path = True
                else:
                    missing = True
        if mismatch:
            break

    if mismatch is not None:
        return DECISION_HELD, HANDOVER_MISMATCH, {
            "handover_id": mismatch["handover_id"],
            "from_qty": mismatch["from_qty"], "to_qty": mismatch["to_qty"]}
    if lineage_tainted:
        return DECISION_HELD, SUSPECT_LINEAGE, {}
    if missing:
        return DECISION_HELD, HANDOVER_MISSING, {}
    if unverified:
        return DECISION_HELD, MIX_UNVERIFIED, {}
    if lineage_open:
        return DECISION_HELD, LINEAGE_GAP, {}
    if confirmed_path:
        return DECISION_RELEASED, HANDOVER_CONFIRMED_CLEAN, {}
    if handover_map:
        return DECISION_RELEASED, CLEAN_LINEAGE, {}
    return DECISION_RELEASED, CLEAR_PATH, {}


def evaluate(normalized):
    reports = normalized["work_reports"]
    handovers = normalized["handovers"]
    suspect = normalized["suspect"]
    produced_by, consumed_in, producing_stage = _lineage_graph(reports)
    stage_order = _stage_order(reports)
    handover_map = _handovers_by_stage(handovers)

    tainted = _descendants(suspect["material_batch"], consumed_in)
    unresolved = _open_intermediates(reports, produced_by, consumed_in)

    output_batches = set(produced_by)
    input_batches = set(consumed_in)
    finished_batches = sorted(output_batches - input_batches)

    results = []
    held_qty = released_qty = 0
    for batch in finished_batches:
        decision, reason, detail = _evaluate_one(
            batch, tainted, unresolved, produced_by, stage_order, handover_map)
        stage_key = producing_stage[batch]
        producer = produced_by[batch]
        qty = next((move["qty"] for move in producer["outputs"] if move["batch"] == batch), 0)
        ancestors, _ = _walk(batch, produced_by)
        results.append({
            "fg_batch": batch,
            "stage": stage_key[0],
            "stage_seq": stage_key[1],
            "qty": qty,
            "decision": decision,
            "reason": reason,
            "detail": detail,
            "ancestors": sorted(ancestors),
        })
        if decision == DECISION_HELD:
            held_qty += qty
        else:
            released_qty += qty

    summary = {
        "finished_batches": len(finished_batches),
        "held_batches": sum(1 for item in results if item["decision"] == DECISION_HELD),
        "released_batches": sum(1 for item in results if item["decision"] == DECISION_RELEASED),
        "held_qty": held_qty,
        "released_qty": released_qty,
        "mismatched_handovers": [h["handover_id"] for h in handovers if not h["total_matches"]],
        "suspect_batch": suspect["material_batch"],
        "suspect_stage": suspect["stage"],
    }
    return {
        "investigation_id": normalized["investigation_id"],
        "suspect": suspect,
        "results": results,
        "summary": summary,
        "issues": normalized["issues"],
    }
