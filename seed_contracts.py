# -*- coding: utf-8 -*-
"""给空库灌几条示范合同，让看板有内容可看（可重复运行，合同号冲突自动跳过）"""
import sqlite3
import datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "contracts.db"
TODAY = dt.date(2026, 10, 27)

SAMPLE = [
    # (合同号, 客户代码, 签订, 生效, 到期, 币种, 金额, 状态, 业务员, 付款条件, 贸易术语)
    ("HT-DEMO-001", "C001", "2026-01-15", "2026-01-15", "2026-12-31", "EUR", 480000, "执行中", "周小杰", "T/T 30天", "FOB"),
    ("HT-DEMO-002", "C002", "2026-03-01", "2026-03-01", "2027-02-28", "SEK", 3600000, "执行中", "刘小源", "T/T 30天", "CIF"),
    ("HT-DEMO-003", "C008", "2025-11-01", "2025-11-01", "2026-10-31", "USD", 260000, "执行中", "张大丽", "L/C 60天", "FOB"),
    ("HT-DEMO-004", "C001", "2025-08-01", "2025-08-01", "2026-07-31", "EUR", 320000, "已完结", "周小杰", "T/T 45天", "CIF"),
    ("HT-DEMO-005", "C008", "2026-09-01", "2026-09-01", "2027-08-31", "USD", 150000, "草签", "张大丽", "T/T 60天", "DDP"),
    ("HT-DEMO-006", "C002", "2026-05-20", "2026-05-20", "2027-05-19", "SEK", 2400000, "执行中", "刘小源", "L/C 30天", "FOB"),
]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
added = skipped = 0
for no, code, sign, sd, ed, ccy, amt, st, sm, pay, trade in SAMPLE:
    c = conn.execute("SELECT id FROM customer WHERE code=?", (code,)).fetchone()
    if not c:
        print("跳过（无此客户）", no, code)
        skipped += 1
        continue
    if conn.execute("SELECT 1 FROM contract WHERE contract_no=?", (no,)).fetchone():
        skipped += 1
        continue
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""INSERT INTO contract(contract_no,customer_id,sign_date,start_date,end_date,
                    currency,amount,pay_term,trade_term,status,salesman,remark,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (no, c["id"], sign, sd, ed, ccy, amt, pay, trade, st, sm, "示范数据", ts, ts))
    added += 1
conn.execute("INSERT INTO change_log(table_name,row_id,action,detail,at) VALUES(?,?,?,?,?)",
             ("contract", 0, "SEED", f"灌入示范合同 {added} 条",
              dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
conn.commit()
n = conn.execute("SELECT COUNT(*) FROM contract").fetchone()[0]
conn.close()
print(f"新增 {added} 条，跳过 {skipped} 条；当前合同总数 {n}")
