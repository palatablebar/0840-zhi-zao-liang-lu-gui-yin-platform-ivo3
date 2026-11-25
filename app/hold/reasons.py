"""扣货与放行的结论原因码。"""

DECISION_HELD = "HELD"
DECISION_RELEASED = "RELEASED"

# 扣货原因
SUSPECT_LINEAGE = "SUSPECT_LINEAGE"          # 报工血缘可追溯到可疑来料批次
MIX_UNVERIFIED = "MIX_UNVERIFIED"            # 交接只对得上总量，混装去向无法排除
HANDOVER_MISMATCH = "HANDOVER_MISMATCH"      # 交接数量对不上
HANDOVER_MISSING = "HANDOVER_MISSING"        # 经过的交接缺记录，去向无法证实
LINEAGE_GAP = "LINEAGE_GAP"                  # 报工缺失，血缘断链无法证明未混入

HOLD_REASONS = {
    SUSPECT_LINEAGE: "报工批次血缘追溯到可疑来料",
    MIX_UNVERIFIED: "交接仅总量一致，混装去向无法排除",
    HANDOVER_MISMATCH: "交接数量对不上，该交接下游成品不得放行",
    HANDOVER_MISSING: "交接记录缺失，成品去向无法证实",
    LINEAGE_GAP: "报工断链，无法证实未混入可疑来料",
}

# 放行原因
CLEAN_LINEAGE = "CLEAN_LINEAGE"              # 血缘可证实未混入
HANDOVER_CONFIRMED_CLEAN = "HANDOVER_CONFIRMED_CLEAN"  # 补齐交接后证实无涉
CLEAR_PATH = "CLEAR_PATH"                    # 未经过任何受影响交接，且血缘干净

RELEASE_REASONS = {
    CLEAN_LINEAGE: "报工血缘证实未混入可疑来料，当天照发",
    HANDOVER_CONFIRMED_CLEAN: "晚到交接补齐去向后证实无涉，恢复放行",
    CLEAR_PATH: "未经过受影响交接，放行",
}
