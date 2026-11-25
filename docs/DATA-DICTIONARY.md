# 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `row_id` | text | 主键 |
| `work_order` | text | 业务字段 |
| `stage_seq` | int_positive | 业务字段 |
| `stage` | text | 业务字段 |
| `input_qty` | int_positive | 业务字段 |
| `good_qty` | int | 业务字段 |
| `scrap_qty` | int | 业务字段 |
| `rework_qty` | int | 业务字段 |
| `rework_good` | int | 业务字段 |

空字符串、`-`、`NA`、`null` 和 `未提供` 按空值处理。金额字段在整理层转为整数分或整数最小单位；日期按 ISO 日期解析；带时间的字段按本地时间解析。标识字段保持为文本，前导零不会被去除。

## 成品扣货字段

排查请求（`POST /api/holds/investigations`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `investigation_id` | text | 可选；同一次排查的稳定标识，重跑只更新结论不重复生成扣货记录 |
| `suspect.stage` | text | 发现可疑来料的工序，必填 |
| `suspect.material_batch` | text | 可疑来料批次号，必填 |
| `work_reports[].report_id` | text | 报工编号 |
| `work_reports[].stage` / `stage_seq` | text / int_positive | 报工工序与序号 |
| `work_reports[].inputs[]` | move | 投入批次与数量，多笔即混装 |
| `work_reports[].outputs[]` | move | 产出批次与数量，多笔即批次拆分 |
| `handovers[].handover_id` | text | 交接编号 |
| `handovers[].from_qty` / `to_qty` | int | 交接发出与收到总量；不等即数量对不上 |
| `handovers[].destinations[]` | move | 可选；逐批次去向，缺省表示只登记总量 |

`move` 为 `{"batch": text, "qty": int}`。数量为非负整数，全角数字会归一为半角。

排查结论中每个成品批次返回 `decision`（`HELD` 扣住 / `RELEASED` 放行）、`reason` 原因码、`qty` 数量与 `ancestors` 全部上游批次。原因码见 `app/hold/reasons.py`。
