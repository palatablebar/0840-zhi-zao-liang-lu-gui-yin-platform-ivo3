# 接口

- `GET /`：工作台。
- `GET /api/catalog`：阶段、字段和样例。
- `POST /api/stages/{stage}`：按阶段返回处理结果。
- `POST /api/runs`：执行完整批次并保存草稿。
- `GET /api/runs/{id}`：读取批次。
- `POST /api/runs/{id}/review`：签发或暂缓，提交 `decision`、`comment`、`expected_revision`。
- `GET /api/runs/{id}/evidence`：下载已签发证据。
- `GET /api/examples/{profile}`：下载样例。
- `POST /api/holds/investigations`：发起或重跑成品扣货排查，提交可疑来料、报工（含拆分/混装去向数量）与交接记录。
- `GET /api/holds/investigations`：列出全部排查及其结论。
- `GET /api/holds/investigations/{id}`：排查详情，含每个成品批次的扣货/放行记录。
- `GET /api/holds/results`：工作台成品扣货结果，汇总仍处扣货状态的成品批次。
- `GET /healthz`：健康检查。
