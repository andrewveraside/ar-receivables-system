# -*- coding: utf-8 -*-
"""真实服务端到端：通过 HTTP 写入一条合同 → 读 SQLite 验证落盘"""
import json
import sqlite3
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = 8766
DB = BASE / "data" / "contracts.db"

def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

print("health:", call("GET", "/api/health"))
cus = call("GET", "/api/customers")["data"]
print("seed 客户:", [c["code"] for c in cus], "币种:", [c["currency"] for c in cus])
cid = cus[0]["id"]
r = call("POST", "/api/contracts", {
    "contract_no": "E2E-TEST-001", "customer_id": cid, "sign_date": "2026-10-27",
    "start_date": "2026-10-27", "end_date": "2027-10-26", "amount": "66,666.66",
    "currency": "EUR", "pay_term": "T/T 30天", "trade_term": "FOB",
    "status": "执行中", "salesman": cus[0]["salesman"], "remark": "端到端测试"})
print("写入:", r)
lst = call("GET", "/api/contracts?q=E2E")["data"]
print("查回:", lst[0]["contract_no"], lst[0]["amount"], lst[0]["status"])

conn = sqlite3.connect(DB)
row = conn.execute("SELECT contract_no,amount,currency,status,created_at "
                   "FROM contract WHERE contract_no='E2E-TEST-001'").fetchone()
tables = [x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
conn.close()
print("SQLite 表:", tables)
print("SQLite 行:", row)
assert row and abs(row[1] - 66666.66) < 0.01, "落盘金额不符"
print("✅ 端到端通过：浏览器录入 → SQLite 持久化")

# 清理测试数据
print("清理:", call("DELETE", f"/api/contracts/{lst[0]['id']}"))
