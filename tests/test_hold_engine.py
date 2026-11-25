"""扣货引擎：覆盖来料追溯、批次拆分、混装、交接对账与恢复放行。"""

from app.hold.reasons import (
    CLEAN_LINEAGE,
    HANDOVER_CONFIRMED_CLEAN,
    HANDOVER_MISMATCH,
    LINEAGE_GAP,
    MIX_UNVERIFIED,
    SUSPECT_LINEAGE,
)
from tests.hold_cases import decisions, evaluate_payload, handover, report, two_line_payload


def test_suspect_lineage_holds_downstream_finished_goods():
    # 规则1：发现可疑来料后，发货前圈出该扣住的成品
    payload = two_line_payload([])
    result = decisions(payload)
    assert result["FG-A"] == ("HELD", SUSPECT_LINEAGE)
    assert result["FG-B"][0] == "RELEASED"


def test_batch_split_records_each_destination_and_qty():
    # 规则2：报工可补记批次拆分，扣住数量按拆分去向累加
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            report("W1", "冲压", 1, [("BAD", 100)], [("A", 60), ("B", 40)]),
            report("W2", "焊接", 2, [("A", 60)], [("FG-A", 60)]),
            report("W3", "焊接", 2, [("B", 40)], [("FG-B", 40)]),
        ],
        "handovers": [],
    }
    evaluation = evaluate_payload(payload)
    by_batch = {item["fg_batch"]: item for item in evaluation["results"]}
    assert by_batch["FG-A"]["qty"] == 60 and by_batch["FG-B"]["qty"] == 40
    assert all(item["decision"] == "HELD" for item in evaluation["results"])
    assert evaluation["summary"]["held_qty"] == 100
    assert evaluation["summary"]["held_batches"] == 2


def test_mixed_report_taints_all_outputs_but_keeps_clean_line_releasable():
    # 规则2：混装去向和数量被记录；干净批次仍可证实放行
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            report("W1", "冲压", 1, [("BAD", 50), ("OK", 50)], [("MIX", 100)]),
            report("W2", "冲压", 1, [("OK2", 80)], [("CLEAN", 80)]),
            report("W3", "焊接", 2, [("MIX", 100)], [("FG-MIX", 100)]),
            report("W4", "焊接", 2, [("CLEAN", 80)], [("FG-OK", 80)]),
        ],
        "handovers": [],
    }
    result = decisions(payload)
    assert result["FG-MIX"] == ("HELD", SUSPECT_LINEAGE)
    assert result["FG-OK"][0] == "RELEASED"


def test_total_only_handover_holds_possible_mix_but_releases_proven_clean():
    # 规则3：交接只对得上总量时，可能混到的成品扣住，证实没混到的当天照发
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 200)])
    result = decisions(payload)
    assert result["FG-A"] == ("HELD", SUSPECT_LINEAGE)
    assert result["FG-B"] == ("RELEASED", CLEAN_LINEAGE)


def test_total_only_handover_with_lineage_gap_is_unverified():
    # 规则3：总量一致但断链，无法排除混装 -> 扣住
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            report("W1", "冲压", 1, [("BAD", 50)], [("S-A", 50)]),
            report("W2", "焊接", 2, [("X", 40)], [("FG-X", 40)]),
        ],
        "handovers": [handover("H1", "冲压", 1, 90, 90)],
    }
    result = decisions(payload)
    assert result["FG-X"][0] == "HELD"
    assert result["FG-X"][1] in {MIX_UNVERIFIED, LINEAGE_GAP}


def test_handover_quantity_mismatch_blocks_everything_through_it():
    # 规则4：交接数量对不上，经过这笔交接的成品不能放行
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 198)])
    result = decisions(payload)
    assert result["FG-A"] == ("HELD", HANDOVER_MISMATCH)
    assert result["FG-B"] == ("HELD", HANDOVER_MISMATCH)
    evaluation = evaluate_payload(payload)
    assert evaluation["summary"]["mismatched_handovers"] == ["H1"]


def test_late_detailed_handover_restores_clean_release():
    # 规则5：晚到交接补齐去向，证实无涉的成品恢复放行；可疑下游仍扣住
    payload = two_line_payload([
        handover("H1", "冲压", 1, 200, 200, destinations=[("S-A", 100), ("S-B", 100)]),
    ])
    result = decisions(payload)
    assert result["FG-A"] == ("HELD", SUSPECT_LINEAGE)
    assert result["FG-B"] == ("RELEASED", HANDOVER_CONFIRMED_CLEAN)


def test_recovery_after_backfilled_work_report():
    # 规则5：补记报工使断链接上干净原料后，成品恢复放行
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            report("W1", "冲压", 1, [("BAD", 50)], [("S-A", 50)]),
            report("W9", "冲压", 1, [("RAW-OK", 40)], [("X", 40)]),
            report("W2", "焊接", 2, [("X", 40)], [("FG-X", 40)]),
        ],
        "handovers": [handover("H1", "冲压", 1, 90, 90)],
    }
    result = decisions(payload)
    assert result["FG-X"][0] == "RELEASED"


def test_engine_is_deterministic_for_same_input():
    # 规则6：同一次排查重跑，引擎结论稳定
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 200)])
    first = evaluate_payload(payload)
    second = evaluate_payload(payload)
    assert first["results"] == second["results"]
    assert first["summary"] == second["summary"]


def test_held_and_released_quantities_are_separated():
    payload = two_line_payload([handover("H1", "冲压", 1, 200, 200)])
    summary = evaluate_payload(payload)["summary"]
    assert summary["held_qty"] == 100
    assert summary["released_qty"] == 100
    assert summary["finished_batches"] == 2


def test_empty_reports_produce_zero_summary():
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [], "handovers": [],
    }
    summary = evaluate_payload(payload)["summary"]
    assert summary["finished_batches"] == 0
    assert summary["held_batches"] == 0 and summary["released_batches"] == 0


def test_cyclic_lineage_does_not_hang_and_holds_nothing_as_finished():
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "A"},
        "work_reports": [
            report("W1", "冲压", 1, [("A", 1)], [("B", 1)]),
            report("W2", "焊接", 2, [("B", 1)], [("A", 1)]),
        ],
        "handovers": [],
    }
    # 环中每个批次都被再次消费，没有成品批次；引擎必须正常终止
    assert evaluate_payload(payload)["results"] == []


def test_isolated_bad_report_does_not_block_valid_ones():
    payload = {
        "suspect": {"stage": "冲压", "material_batch": "BAD"},
        "work_reports": [
            {"report_id": "BAD1", "stage": "冲压", "stage_seq": 1, "inputs": [], "outputs": []},
            report("W1", "冲压", 1, [("BAD", 5)], [("F", 5)]),
        ],
        "handovers": [],
    }
    evaluation = evaluate_payload(payload)
    assert any(issue["code"] == "REPORT_WITHOUT_MOVEMENT" for issue in evaluation["issues"])
    assert [item["fg_batch"] for item in evaluation["results"]] == ["F"]
