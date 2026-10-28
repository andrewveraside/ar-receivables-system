# -*- coding: utf-8 -*-
"""闭环测试：录入合同 → 自动同步 → 看板数据源更新 → 生成看板 HTML"""
import json
import sqlite3
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = 8769
DB = BASE / "data" / "contracts.db"
BRIDGE = BASE / "data" / "ar_bridge.json"


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


print("1) 初始同步状态:", call("POST", "/api/sync-dashboard", {}))
cus = call("GET", "/api/customers")["data"]
cid = cus[0]["id"]

print("2) 录入 3 份合同")
made = []
for i, (no, amt, ccy, st, sd, ed, end) in enumerate([
    ("HT-CLOSE-001", "120000", "EUR", "执行中", "2026-01-15", "2026-01-15", "2026-12-31"),
    ("HT-CLOSE-002", "88000", "USD", "已完结", "2025-11-01", "2025-11-01", "2026-05-01"),
    ("HT-CLOSE-003", "45000", "USD", "草签", "2026-10-01", "2026-10-01", "2027-09-30"),
], 1):
    r = call("POST", "/api/contracts", {
        "contract_no": no, "customer_id": cid, "sign_date": sd,
        "start_date": sd, "end_date": end, "amount": amt, "currency": ccy,
        "pay_term": "T/T 45天", "trade_term": "FOB", "status": st,
        "salesman": cus[0]["salesman"], "remark": "闭环测试"})
    made.append((no, r))
    print("   ", no, r)

print("3) 检查桥接输出")
b = json.loads(BRIDGE.read_text(encoding="utf-8"))
print("   contracts:", b["meta"]["contract_count"], " rows:", len(b["rows"]))
print("   样例:", {k: b["rows"][0][k] for k in
                 ("发票号", "合同号", "客户名称", "到期日", "币种", "不含税金额", "已收金额")})
tot = sum(r["不含税金额"] for r in b["rows"])
print(f"   原币合计: {tot:,.2f}（期望 120000+88000+45000=253000）")
assert abs(tot - 253000) < 0.01, "金额拆分有偏差"
assert b["meta"]["contract_count"] == 3
# 已完结合同应全额收回
done = [r for r in b["rows"] if r["合同号"] == "HT-CLOSE-002"]
assert done and all(abs(r["已收金额"] - r["不含税金额"]) < 1e-6 for r in done), "已完结合同未全额"
# 草签合同应零回款
draft = [r for r in b["rows"] if r["合同号"] == "HT-CLOSE-003"]
assert draft and all(r["已收金额"] == 0 for r in draft), "草签合同不该有回款"
print("   ✅ 状态映射正确：已完结=全额收回，草签=零回款")

print("4) 生成看板 HTML")
import subprocess, sys
r = subprocess.run([sys.executable, "build_dashboard.py", "--source=bridge"],
                   capture_output=True, text=True, encoding="utf-8", cwd=str(BASE))
print("   ", r.stdout.strip() or r.stderr.strip())
html = BASE / "应收账款看板_合同库版_离线版.html"
assert html.exists(), "看板 HTML 未生成"
txt = html.read_text(encoding="utf-8")
assert "HT-CLOSE-001" in txt or "AR-HT-CLOSE-001-1" in txt, "看板里没有合同数据"
print(f"   ✅ {html.name} {html.stat().st_size/1024:.1f} KB，含合同数据")

print("5) 清理测试合同")
for no, r in made:
    lst = call("GET", f"/api/contracts?q={no}")["data"]
    for x in lst:
        if x["contract_no"] == no:
            call("DELETE", f"/api/contracts/{x['id']}")
            print("   删除", no)

b2 = json.loads(BRIDGE.read_text(encoding="utf-8"))
print("6) 清理后同步:", b2["meta"]["contract_count"], "合同 /", len(b2["rows"]), "应收")
print("\n✅ 闭环全部通过")


