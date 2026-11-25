# 运行说明

## 启动

```bash
docker compose up --build
```

## 测试

```bash
docker compose exec -T app pytest -q
```

## 样例

- `dirty`：包含编码、列数、空值或冲突重复，适合检查隔离区。
- `clean`：可通过当前规则并完成签发。
- `hold_investigation.json`：成品扣货排查样例，含可疑料拆分、干净生产线与仅总量一致的交接。

## 成品扣货

`POST /api/holds/investigations` 提交排查后，扣货记录写入独立的 `instance/holds.sqlite3`（可用环境变量 `HOLD_DB` 覆盖）。同一 `investigation_id` 重跑只更新结论与版本号；`GET /api/holds/results` 供工作台查询仍被扣住的成品。

## 重置

```bash
docker compose down -v
docker compose up --build
```

历史批次保存在 SQLite 卷中。重置会清除本地批次与签发记录。
