# -*- coding: utf-8 -*-
"""后端接口自测：起服务 → 打全部 API → 断言 → 关服务。不改动正式库（用临时库）"""
import json
import os
import sys
import time
import socket
import sqlite3
import subprocess
import urllib.request
import urllib.error
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable
# 用独立临时库，避免污染正式数据
TMP_DB = BASE / "data" / "_test_contracts.db"
TMP_DB_BYTE = BASE / "data" / "_test_contracts.db"
PORT = 8799

def wait_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = socket.socket(); r = s.connect_ex(("127.0.0.1", port)); s.close()
        if r == 0: return True
        time.sleep(0.15)
    return False

def req(method, path, body=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

# 指向临时库：monkeypatch DB_PATH
env = dict(os.environ)
env["CONTRACT_PORT"] = str(PORT)
env["CONTRACT_NO_BROWSER"] = "1"
env["TEST_DB"] = str(TMP_DB)

runner = BASE / "_test_server.py"
runner.write_text(f'''
import runpy, sys
sys.argv = ["server.py"]
import server
server.DB_PATH = __import__("pathlib").Path(r"{TMP_DB}")
server.init_db()
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", {PORT}), server.Handler)
srv.serve_forever()
''', encoding="utf-8")

PROC = None
results = []
def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("PASS " if cond else "FAIL ") + name + (("  | " + str(extra)) if extra else ""))

try:
    if TMP_DB.exists(): TMP_DB.unlink()
    logf = open(BASE / "_test_server.log", "wb")
    PROC = subprocess.Popen([PY, str(runner)], stdout=logf, stderr=logf, env=env)
    ok = wait_port(PORT)
    check("服务启动", ok, f"port {PORT}")
    if not ok:
        print((BASE / "_test_server.log").read_text(encoding="utf-8", errors="replace")[:2000])
        raise SystemExit(1)

    # health
    st, j = req("GET", "/api/health")
    check("GET /api/health", st == 200 and j["ok"], j)

    # 首页 HTML
    st_html = None
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=10) as r:
        html = r.read().decode("utf-8")
        st_html = r.status
    check("GET / 返回 HTML", st_html == 200 and "合同管理系统" in html, f"{len(html)} 字符")

    # 初始 seed 客户
    st, j = req("GET", "/api/customers")
    check("GET /api/customers 有种子客户", j["ok"] and len(j["data"]) == 3, f"{len(j['data'])} 个")

    # 新增客户
    st, j = req("POST", "/api/customers", {
        "code": "C777", "name": "TEST BAYER AG", "country": "德国", "currency": "EUR",
        "pay_days": 45, "credit_limit": "1,200,000.50", "salesman": "刘小源",
        "contact": "Anna", "email": "anna@test.example"})
    check("POST 新增客户", j["ok"] and j.get("id"), j)
    cid = j.get("id")

    # 重复代码 = update
    st, j = req("POST", "/api/customers", {"code": "C777", "name": "TEST BAYER AG (v2)",
                                           "currency": "EUR", "pay_days": 60})
    st2, j2 = req("GET", "/api/customers")
    row = [x for x in j2["data"] if x["code"] == "C777"]
    check("同代码覆盖更新(不重复插入)", len(row) == 1 and row[0]["name"].endswith("(v2)"), row)

    # 非法币种
    st, j = req("POST", "/api/customers", {"code": "C888", "name": "X", "currency": "XYZ"})
    check("拒绝非法币种", j["ok"] is False, j.get("error"))

    # 非法业务员
    st, j = req("POST", "/api/customers", {"code": "C889", "name": "X", "salesman": "王峰"})
    check("拒绝非白名单业务员", j["ok"] is False, j.get("error"))

    # 新增合同
    st, j = req("POST", "/api/contracts", {
        "contract_no": "ht-2026-001", "customer_id": cid, "sign_date": "2026/10/1",
        "start_date": "2026-10-01", "end_date": "2027-10-01", "currency": "EUR",
        "amount": "125,000.5", "pay_term": "T/T 45天", "trade_term": "FOB",
        "status": "执行中", "salesman": "刘小源", "remark": "测试"})
    check("POST 新增合同(日期/金额已规范化)", j["ok"], j)
    ct_id = j.get("id")

    st, j = req("GET", "/api/contracts")
    c = [x for x in j["data"] if x["contract_no"] == "HT-2026-001"]
    check("合同号自动转大写", len(c) == 1, c[0]["contract_no"] if c else None)
    if c:
        check("金额千分位被清洗", c[0]["amount"] == 125000.5, c[0]["amount"])
        check("日期 / 被规范化为 -", c[0]["sign_date"] == "2026-10-01", c[0]["sign_date"])

    # 合同号重复
    st, j = req("POST", "/api/contracts", {"contract_no": "HT-2026-001", "customer_id": cid,
                                           "sign_date": "2026-10-02"})
    check("拒绝重复合同号", j["ok"] is False, j.get("error"))

    # 更新合同
    st, j = req("POST", "/api/contracts", {"id": ct_id, "contract_no": "HT-2026-001",
                "customer_id": cid, "sign_date": "2026-10-01", "amount": "99999",
                "currency": "EUR", "status": "已完结"})
    st2, j2 = req("GET", "/api/contracts")
    c = [x for x in j2["data"] if x["contract_no"] == "HT-2026-001"][0]
    check("更新合同生效", c["amount"] == 99999 and c["status"] == "已完结", c["amount"])

    # 各种校验
    for name, payload, key in [
        ("拒绝缺失客户", {"contract_no": "HT-X-1", "customer_id": 0, "sign_date": "2026-10-01"}, "客户"),
        ("拒绝缺签订日期", {"contract_no": "HT-X-2", "customer_id": cid}, "签订日期"),
        ("拒绝到期早于生效", {"contract_no": "HT-X-3", "customer_id": cid, "sign_date": "2026-10-01",
                          "start_date": "2027-01-01", "end_date": "2026-01-01"}, "到期"),
        ("拒绝非法状态", {"contract_no": "HT-X-4", "customer_id": cid, "sign_date": "2026-10-01",
                       "status": "乱填"}, "状态"),
        ("拒绝负金额", {"contract_no": "HT-X-5", "customer_id": cid, "sign_date": "2026-10-01",
                     "amount": "-5"}, "负"),
        ("拒绝非法日期", {"contract_no": "HT-X-6", "customer_id": cid, "sign_date": "2026-13-45"}, "日期"),
        ("拒绝不存在客户", {"contract_no": "HT-X-7", "customer_id": 99999, "sign_date": "2026-10-01"}, "不存在"),
    ]:
        st, j = req("POST", "/api/contracts", payload)
        check(name, j["ok"] is False, j.get("error"))

    # 搜索
    st, j = req("GET", "/api/contracts?q=HT-2026-001")
    check("搜索命中", len(j["data"]) == 1, len(j["data"]))
    st, j = req("GET", "/api/contracts?q=zzz-not-exist")
    check("搜索无结果返回空", j["ok"] and len(j["data"]) == 0, len(j["data"]))

    # 统计
    st, j = req("GET", "/api/stats")
    check("GET /api/stats", j["ok"] and j["contracts"] >= 1 and "salesmen" in j["options"], j["contracts"])

    # 导出（注意：/api/export.json 不返回 ok 字段，直接断言两张表都在）
    st, j = req("GET", "/api/export.json")
    check("GET /api/export.json 返回含两表",
          "customers" in j and "contracts" in j,
          f"{len(j.get('customers', []))} 客户 / {len(j.get('contracts', []))} 合同")
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/export.json", timeout=10) as r:
        ex = json.loads(r.read().decode("utf-8"))
    check("导出 JSON 含两表", "customers" in ex and "contracts" in ex,
          f"{len(ex['customers'])} 客户 / {len(ex['contracts'])} 合同")

    # 删除
    st, j = req("DELETE", f"/api/contracts/{ct_id}")
    check("DELETE 合同", j["ok"], j)
    st, j = req("GET", "/api/contracts?q=HT-2026-001")
    check("删除后查不到", len(j["data"]) == 0, len(j["data"]))
    st, j = req("DELETE", "/api/contracts/999999")
    check("删除不存在返回错误", j["ok"] is False, j.get("error"))

    # 路径穿越
    st, j = req("GET", "/web/../server.py")
    check("拒绝路径穿越", st == 404 or j.get("ok") is False, st)

    # 未知接口
    st, j = req("GET", "/api/nothing")
    check("未知接口 404", st == 404, st)

    # 数据库落盘
    conn = sqlite3.connect(TMP_DB)
    n_ct = conn.execute("SELECT COUNT(*) FROM contract").fetchone()[0]
    n_cu = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
    n_log = conn.execute("SELECT COUNT(*) FROM change_log").fetchone()[0]
    conn.close()
    check("SQLite 真实落盘", TMP_DB.exists() and n_cu == 4, f"{n_cu} 客户 / {n_ct} 合同 / {n_log} 日志")
    check("变更日志有记录", n_log >= 4, n_log)

finally:
    if PROC:
        PROC.terminate()
        try: PROC.wait(timeout=5)
        except Exception: PROC.kill()
    for f in (runner, TMP_DB, BASE / "_test_server.log"):
        Path(f).unlink(missing_ok=True)

fail = [r for r in results if not r[1]]
print("\n" + "=" * 50)
print(f"总计 {len(results)} 项，通过 {len(results)-len(fail)}，失败 {len(fail)}")
if fail:
    print("失败项：")
    for n, _, e in fail: print("  -", n, e)
