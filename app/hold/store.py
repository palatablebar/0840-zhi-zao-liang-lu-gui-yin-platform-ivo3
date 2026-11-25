"""成品扣货排查的 SQLite 存储。

同一次排查重跑不重复生成扣货记录：
- investigations 以 request_key 做唯一约束，重复提交返回原排查并 revision+1；
- holds 以 (investigation_id, fg_batch) 做唯一约束，
  重跑时按最新结论更新状态，已存在的扣货记录不重复插入。
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class HoldStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=8)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS investigations(
              id TEXT PRIMARY KEY,
              request_key TEXT UNIQUE NOT NULL,
              investigation_ref TEXT NOT NULL,
              suspect_stage TEXT NOT NULL,
              suspect_batch TEXT NOT NULL,
              status TEXT NOT NULL,
              revision INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              request_text TEXT NOT NULL,
              result_text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS holds(
              id TEXT PRIMARY KEY,
              investigation_id TEXT NOT NULL,
              fg_batch TEXT NOT NULL,
              stage TEXT NOT NULL,
              stage_seq INTEGER NOT NULL,
              qty INTEGER NOT NULL,
              decision TEXT NOT NULL,
              reason TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(investigation_id, fg_batch),
              FOREIGN KEY(investigation_id) REFERENCES investigations(id)
            );
            ''')

    def find_by_request(self, request_key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM investigations WHERE request_key=?", (request_key,)).fetchone()
        return dict(row) if row else None

    def get(self, investigation_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM investigations WHERE id=?", (investigation_id,)).fetchone()
        return dict(row) if row else None

    def list_holds(self, investigation_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM holds WHERE investigation_id=? ORDER BY stage_seq, fg_batch",
                (investigation_id,)).fetchall()
        return [dict(row) for row in rows]

    def list_investigations(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM investigations ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def upsert(self, request_key, investigation_ref, request_text, evaluation):
        """幂等写入。首次创建排查与扣货记录；重跑只更新结论，不重复生成扣货。"""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM investigations WHERE request_key=?", (request_key,)).fetchone()
            if existing is None:
                investigation_id = uuid.uuid4().hex[:12]
                db.execute(
                    "INSERT INTO investigations(id,request_key,investigation_ref,suspect_stage,"
                    "suspect_batch,status,revision,created_at,updated_at,request_text,result_text) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (investigation_id, request_key, investigation_ref,
                     evaluation["suspect"]["stage"], evaluation["suspect"]["material_batch"],
                     "OPEN", 1, now, now,
                     json.dumps(request_text, ensure_ascii=False),
                     json.dumps(evaluation, ensure_ascii=False)))
                for item in evaluation["results"]:
                    db.execute(
                        "INSERT INTO holds(id,investigation_id,fg_batch,stage,stage_seq,qty,"
                        "decision,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (uuid.uuid4().hex[:12], investigation_id, item["fg_batch"], item["stage"],
                         item["stage_seq"], item["qty"], item["decision"], item["reason"], now, now))
                created = True
            else:
                investigation_id = existing["id"]
                db.execute(
                    "UPDATE investigations SET revision=revision+1, updated_at=?, result_text=? WHERE id=?",
                    (now, json.dumps(evaluation, ensure_ascii=False), investigation_id))
                for item in evaluation["results"]:
                    db.execute(
                        "INSERT INTO holds(id,investigation_id,fg_batch,stage,stage_seq,qty,"
                        "decision,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(investigation_id, fg_batch) DO UPDATE SET "
                        "decision=excluded.decision, reason=excluded.reason, qty=excluded.qty, "
                        "updated_at=excluded.updated_at",
                        (uuid.uuid4().hex[:12], investigation_id, item["fg_batch"], item["stage"],
                         item["stage_seq"], item["qty"], item["decision"], item["reason"], now, now))
                created = False
        return self.get(investigation_id), created
