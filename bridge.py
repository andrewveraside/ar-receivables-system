# -*- coding: utf-8 -*-
"""合同库 → 看板数据源 桥接层

单向：contracts.db（录入界面写入）→ data/ar_bridge.json（看板读取，只读不改）
看板侧用 <script src="data/ar_bridge.json"> 不行（不是 JS），
所以同时输出 data/ar_bridge.js（window.__AR_BRIDGE = {...}），file:// 下也能读。

用法：
  python bridge.py            # 增量同步（合同有变化才重算）
  python bridge.py --rebuild  # 全量重建
  python bridge.py --stats    # 只看统计，不写文件
"""
import hashlib
import json
import sqlite3
import datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "data" / "contracts.db"
OUT_JSON = BASE / "data" / "ar_bridge.json"
OUT_JS = BASE / "data" / "ar_bridge.js"
STATE = BASE / "data" / "_bridge_state.json"

# 与本机看板同口径的折算汇率（虚构近似值，仅演示；接真实业务时换成取数接口）
RATES = {"USD": 7.1085, "EUR": 7.7420, "GBP": 9.1840, "JPY": 0.04712,
         "AUD": 4.6820, "CAD": 5.1240, "SGD": 5.4180, "KRW": 0.00498,
         "SEK": 0.6742, "CNY": 1.0}

# 每个合同按币种给不同"批次"：合同额按比例拆成 1-3 期应收（模拟分期发货/分期结汇）
SPLITS = {"USD": [0.40, 0.35, 0.25], "EUR": [0.50, 0.50], "SEK": [1.0],
          "GBP": [0.60, 0.40], "JPY": [0.50, 0.30, 0.20], "DEFAULT": [0.55, 0.45]}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build():
    if not DB_PATH.exists():
        raise SystemExit("找不到 data/contracts.db，先启动一次合同系统")
    conn = connect()
    contracts = [dict(r) for r in conn.execute(
        "SELECT c.*, u.name AS customer_name, u.code AS customer_code, "
        "u.country, u.currency AS cust_currency, u.pay_days, u.salesman AS cust_salesman "
        "FROM contract c JOIN customer u ON u.id = c.customer_id "
        "WHERE c.status <> '已作废' ORDER BY c.id")]
    conn.close()

    rows = []
    seq = 0
    for ct in contracts:
        ccy = ct["currency"] or "USD"
        rate = RATES.get(ccy, 1.0)
        amount = float(ct["amount"] or 0)
        if amount <= 0:
            continue
        sign = dt.date.fromisoformat(ct["sign_date"])
        pay_days = int(ct["pay_days"] or 30)
        # 没有到期日的合同按签订日 + 账期算
        end = dt.date.fromisoformat(ct["end_date"]) if ct.get("end_date") else None
        splits = SPLITS.get(ccy, SPLITS["DEFAULT"])
        # 若合同明确写了生效/到期区间，按区间均分各期出货日；否则按每期 30 天
        start = dt.date.fromisoformat(ct["start_date"]) if ct.get("start_date") else sign
        span = max(1, (end - start).days) if end and end > start else None

        for k, ratio in enumerate(splits):
            seq += 1
            # 有明确区间则按区间均分，否则每期 30 天
            offset = int(span * k / len(splits)) if span else k * 30
            inv_date = start + dt.timedelta(days=offset)
            due_date = inv_date + dt.timedelta(days=pay_days)
            amt = round(amount * ratio, 2)
            # 已完结合同视为全额收回；草签合同尚未开始执行，视为零回款
            if ct["status"] == "已完结":
                paid = amt
            elif ct["status"] == "草签":
                paid = 0.0
            else:
                # 执行中：到期日已过 → 按"结算进度"部分回款，制造真实的逾期与账龄分布。
                # 用 (发票日 → 到期日) 已走完的比例做回款率上限，再留一段未收尾款。
                days_since_due = (dt.date.today() - due_date).days
                if days_since_due < 0:
                    # 未到期：多数未回款，少量预付
                    paid = amt * (0.3 if inv_date < dt.date.today() - dt.timedelta(days=60) else 0.0)
                else:
                    # 逾期后逐步回款，但永远留 15%~45% 尾款挂在账上
                    base = min(0.85, 0.30 + days_since_due / 400.0)
                    keep = 0.45 - min(0.30, days_since_due / 900.0)
                    paid = amt * max(base * (1 - keep), 0.0) if base > keep else 0.0
                paid = round(paid, 2)
            rows.append({
                "发票号": f"AR-{ct['contract_no']}-{k+1}",
                "合同号": ct["contract_no"],
                "客户代码": ct["customer_code"],
                "客户名称": ct["customer_name"],
                "国家": ct["country"] or "",
                "业务员": ct["salesman"] or ct["cust_salesman"] or "",
                "发票日期": inv_date.isoformat(),
                "账期天": pay_days,
                "到期日": due_date.isoformat(),
                "币种": ccy,
                "汇率": rate,
                "不含税金额": amt,
                "出口退税率": 0.13,
                "已收金额": round(paid, 2),
                "本位币金额": round(amt * rate, 2),
                "本位币已收": round(paid * rate, 2),
            })

    meta = {
        "title": "应收账款台账（合同库驱动）",
        "source": "contracts.db",
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contract_count": len(contracts),
        "note": "由合同管理系统自动生成，勿手改；改数据请回录入界面",
    }
    payload = {"meta": meta, "rows": rows}
    return payload


def write(payload):
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_JS.write_text("window.__AR_BRIDGE = " + json.dumps(payload, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    STATE.write_text(json.dumps({"sig": sig(payload), "at": payload["meta"]["generated"]},
                                ensure_ascii=False), encoding="utf-8")


def sig(payload):
    """增量同步签名。

    对 bridge 的**输出**（payload 全量）排序后整体取 SHA-256，而不是对 contract 表
    或某几个汇总值取签名。原因：
      1. 汇总值签名会漏 —— 改一条 100→120、另一条 100→80，总和与条数都不变，
         签名也不变，main() 就会跳过写盘，看板停在旧数据（2026-10-28 代码评审发现）。
      2. 用 MAX(updated_at) 也会漏 —— updated_at 只在 save_contract 里写，
         seed_contracts.py 直接 INSERT、手工 SQL 都不更新它。
      3. 必须覆盖**输出**而不是**输入** —— RATES / SPLITS / 回款模拟公式变了，
         contract 表一字未动，但看板该变；哈希 payload 天然覆盖这一层。
      4. 带日期 —— build_dashboard.py 用 date.today() 算逾期，隔夜后数据没变
         但账龄该往前推一天，所以每天必须重算一次。
    """
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{dt.date.today().isoformat()}:{h}"


def main():
    import sys
    payload = build()
    s = sig(payload)
    if "--stats" in sys.argv:
        unpaid = sum(r["本位币金额"] - r["本位币已收"] for r in payload["rows"])
        print(f"合同 {payload['meta']['contract_count']} 份 → 应收 {len(payload['rows'])} 笔")
        print(f"未收本位币合计 {unpaid:,.2f}")
        return
    if "--rebuild" not in sys.argv and STATE.exists():
        old = json.loads(STATE.read_text(encoding="utf-8"))
        if old.get("sig") == s:
            print(f"无变化，跳过（{payload['meta']['contract_count']} 合同 / "
                  f"{len(payload['rows'])} 应收）")
            return
    write(payload)
    unpaid = sum(r["本位币金额"] - r["本位币已收"] for r in payload["rows"])
    print(f"已同步：{payload['meta']['contract_count']} 合同 → {len(payload['rows'])} 应收")
    print(f"未收本位币合计 {unpaid:,.2f}")
    print(f"输出：{OUT_JS.name} / {OUT_JSON.name}")


if __name__ == "__main__":
    main()
