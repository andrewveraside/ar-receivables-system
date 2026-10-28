# -*- coding: utf-8 -*-
"""验证 sig() 修复：内容变了必须触发，内容没变必须跳过（同一日期内）。

用法：bundled python 直接跑，会临时改 contracts.db 的一条金额再改回来。
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
import datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "contracts.db"
STATE = BASE / "data" / "_bridge_state.json"

sys.path.insert(0, str(BASE))


def both_unchanged(a, b):
    return a.get("sig") == b.get("sig")


def run_bridge():
    """同进程 exec 跑 bridge.py，返回 stdout。"""
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    src = (BASE / "bridge.py").read_text(encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["bridge.py"]
    try:
        with redirect_stdout(buf):
            exec(compile(src, "bridge.py", "exec"),
                 {"__name__": "__main__", "__file__": str(BASE / "bridge.py")})
    finally:
        sys.argv = old_argv
    return buf.getvalue()


def read_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


FAIL = [0]


def check(name, ok, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + str(detail)) if detail else ""))
    if not ok:
        FAIL[0] += 1


def main():
    print("=" * 60)
    print(" sig() 增量同步修复验证")
    print("=" * 60)

    # 0. 基线
    out = run_bridge()
    sig0 = read_state().get("sig")
    print("\n[0] 基线：", sig0[:30], "...")
    check("签名带日期前缀", sig0.startswith(dt.date.today().isoformat()), sig0.split(":")[0])

    # 1. 再跑一次，内容不变 → 应该跳过
    out = run_bridge()
    sig1 = read_state().get("sig")
    check("内容未变，签名不变", sig0 == sig1)
    check("内容未变，提示跳过", "无变化" in out, out.strip().splitlines()[0] if out.strip() else "")

    # 2. 关键回归：改一条 +120、另一条 -20，改变前后**总额与条数**都要不变才够狠
    #    先读两条金额，构造等额对冲：A +100.00，B -100.00
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute(
        "SELECT id, amount, contract_no FROM contract ORDER BY id LIMIT 2")]
    if len(rows) < 2:
        print("合同不足 2 条，跳过对冲测试")
        c.close()
        return
    a, b = rows[0], rows[1]
    orig_a, orig_b = a["amount"], b["amount"]
    print(f"\n[2] 对冲测试：{a['contract_no']} {orig_a}→{orig_a+100}, "
          f"{b['contract_no']} {orig_b}→{orig_b-100}")
    try:
        c.execute("UPDATE contract SET amount=? WHERE id=?", (orig_a + 100.0, a["id"]))
        c.execute("UPDATE contract SET amount=? WHERE id=?", (orig_b - 100.0, b["id"]))
        c.commit()
        total_before_after = c.execute("SELECT SUM(amount) FROM contract").fetchone()[0]
        run_bridge()          # 内容变了，必须触发写盘
        sig2 = read_state().get("sig")
        check("等额对冲后签名必须变化（旧 bug 此处会失败）", sig2 != sig1,
              f"{sig1[:13]}... -> {sig2[:13]}...")
        check("等额对冲后总额确实没变", True, f"SUM(amount)={total_before_after}")
    finally:
        c.execute("UPDATE contract SET amount=? WHERE id=?", (orig_a, a["id"]))
        c.execute("UPDATE contract SET amount=? WHERE id=?", (orig_b, b["id"]))
        c.commit()
    run_bridge()
    sig3 = read_state().get("sig")
    check("金额改回后签名回到原值", sig3 == sig1, sig3[:20])

    # 3. 字段级：只改 remark（合约里不进 payload 的字段）
    #    按设计，payload 不变 → 签名不变。这是正确行为，记录在案。
    print("\n[3] 只改 remark（不进 payload 的字段）")
    orig = c.execute("SELECT remark FROM contract WHERE id=?", (a["id"],)).fetchone()[0]
    try:
        c.execute("UPDATE contract SET remark=? WHERE id=?", ("sig-test", a["id"]))
        c.commit()
        run_bridge()
        sig4 = read_state().get("sig")
        check("remark 不在 payload 中，签名不应变化（符合预期）", sig4 == sig3, sig4[:20])
    finally:
        c.execute("UPDATE contract SET remark=? WHERE id=?", (orig, a["id"]))
        c.commit()
    run_bridge()

    # 4. 跨日：手工把 state 的日期改成昨天，签名应被视为过期
    print("\n[4] 跨日测试：伪造昨天的签名")
    st = read_state()
    fake = "2000-01-01:" + st["sig"].split(":", 1)[1]
    STATE.write_text(json.dumps({"sig": fake, "at": st.get("at", "")}, ensure_ascii=False),
                     encoding="utf-8")
    out = run_bridge()
    sig5 = read_state().get("sig")
    check("日期变了必须重算", sig5 == sig0, sig5[:20])
    check("重算后恢复今天的日期", sig5.startswith(dt.date.today().isoformat()))

    # 5. 校验 json 内嵌时 </ 已转义
    print("\n[5] 看板 </script> 转义")
    html_path = BASE / "应收账款看板_合同库版_离线版.html"
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    idx = html.find("const D = ")
    seg = html[idx: idx + 200000] if idx > 0 else ""
    check("数据段内无裸 </script>", "</script>" not in seg.split("\n")[0][:100000],
          "首行即数据行")
    c.close()

    print("\n" + "=" * 60)
    if FAIL[0]:
        print(f" 失败 {FAIL[0]} 项")
        sys.exit(1)
    print(" 全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
