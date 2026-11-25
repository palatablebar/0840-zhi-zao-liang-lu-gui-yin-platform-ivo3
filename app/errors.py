from flask import jsonify


MESSAGES = {
    "EMPTY_FILE": "文件为空",
    "BLANK_FILE": "文件只有空白",
    "HEADER_ONLY": "文件只有表头",
    "HEADER_MISMATCH": "表头与本项目字段不一致",
    "UNCLOSED_QUOTE": "引号未闭合，文件已拒收",
    "TOO_MANY_ROWS": "数据行超过上限",
    "FILE_TOO_LARGE": "文件超过大小上限",
    "KEY_MISSING": "主键为空",
    "CONFLICT_DUPLICATE": "同一键存在冲突内容",
    "SAMPLE_UNKNOWN": "样例不存在",
    "STAGE_UNKNOWN": "阶段不存在",
    "RUN_NOT_FOUND": "批次不存在",
    "STALE_REVIEW": "批次已被更新，请刷新后复核",
    "GATE_BLOCKED": "存在阻断项，不能签发",
    "NOT_APPROVED": "批次尚未签发",
    "BAD_REQUEST": "请求内容不完整",
    "SUSPECT_STAGE_MISSING": "可疑来料缺少工序信息",
    "SUSPECT_BATCH_MISSING": "可疑来料缺少批次号",
    "BAD_REPORT_ID": "报工缺少报工编号",
    "BAD_REPORT_STAGE": "报工缺少工序",
    "BAD_REPORT_SEQ": "报工工序序号必须为正整数",
    "BAD_INPUT_BATCH": "报工投入批次号为空",
    "BAD_INPUT_QTY": "报工投入数量必须为非负整数",
    "BAD_OUTPUT_BATCH": "报工产出批次号为空",
    "BAD_OUTPUT_QTY": "报工产出数量必须为非负整数",
    "REPORT_WITHOUT_MOVEMENT": "报工必须同时登记投入批次与产出批次",
    "BAD_HANDOVER_ID": "交接缺少交接编号",
    "BAD_HANDOVER_STAGE": "交接缺少工序",
    "BAD_HANDOVER_SEQ": "交接工序序号必须为正整数",
    "BAD_FROM_QTY": "交接发出数量必须为非负整数",
    "BAD_TO_QTY": "交接收到数量必须为非负整数",
    "BAD_DEST_BATCH": "交接去向批次号为空",
    "BAD_DEST_QTY": "交接去向数量必须为非负整数",
    "INVESTIGATION_NOT_FOUND": "扣货排查不存在",
}


class DomainIssue(Exception):
    def __init__(self, code: str, status: int = 400, detail: str | None = None):
        self.code = code
        self.status = status
        self.detail = detail
        super().__init__(code)


def error_response(exc: DomainIssue):
    return jsonify(error=exc.detail or MESSAGES.get(exc.code, "请求无法处理"), code=exc.code), exc.status
