# -*- coding: utf-8 -*-
"""自检：解析 HTML 里的 JS 逻辑，用 python 复算聚合值，验证口径一致 + 文件完整性"""
import json, re, datetime as dt
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent
html = (BASE / "应收账款看板_离线版.html").read_text(encoding="utf-8")
print("== 文件完整性 ==")
print("echarts 内嵌:", "echarts" in html and "LinearGradient" in html)
print("有 PAYLOAD:", "__PAYLOAD__" not in html or "null" in html)
m = re.search(r"const D = (\{.*?\});\nconst C = ", html, re.S)
assert m, "找不到数据块"
D = json.loads(m.group(1))
rows = D["rows"]
print("解析出记录数:", len(rows))
print("数据日期:", D["today"])

print("\n== 唯一性/键完整 ==")
need = ["id","c","cn","co","s","d","due","ccy","amt","paid","open","openCny","overdue","bucket","status"]
missing = [k for k in need if k not in rows[0]]
print("缺字段:", missing or "无")
print("发票号唯一:", len({r['id'] for r in rows}) == len(rows))

print("\n== 口径复算 ==")
tot = sum(r["openCny"] for r in rows)
print("未收本位币合计:", round(tot, 2))
od = [r for r in rows if r["status"] == "逾期"]
print("逾期金额:", round(sum(r['openCny'] for r in od), 2), "| 张数:", len(od))
o90 = [r for r in rows if r["bucket"] in ("91-180天", "180天以上")]
print("严重逾期(>90天):", round(sum(r['openCny'] for r in o90), 2), "| 张数:", len(o90))
print("平均账龄 DSO:", round(sum(r['agingDays'] for r in rows) / len(rows)))
bk = defaultdict(float)
for r in rows: bk[r["bucket"]] += r["openCny"]
order = ["未到期","1-30天","31-60天","61-90天","91-180天","180天以上"]
print("\n账龄结构:")
for b in order:
    print(f"  {b:10s} {bk[b]:>14,.0f}  ({bk[b]/tot*100:5.1f}%)")
print("  分档合计校验:", round(sum(bk.values()) - tot, 6))

print("\n== 边界校验 ==")
bad = [r for r in rows if abs(r['open'] - (r['amt'] - r['paid'])) > 0.01]
print("未收原币=金额-已收 不符:", len(bad))
neg = [r for r in rows if r['open'] < -0.01]
print("负余额单据:", len(neg))
# 逾期天数与到期日一致性
mismatch = [r for r in rows if r['overdue'] != max(0, (dt.date.fromisoformat(D['today']) - dt.date.fromisoformat(r['due'])).days)]
print("逾期天数与到期日不符:", len(mismatch))
# 币种与客户国别一致
cust = {c['code']: c for c in D['customers']}
print("\n== 客户维度 ==")
byc = defaultdict(float)
for r in rows: byc[r['cn']] += r['openCny']
top = sorted(byc.items(), key=lambda x: -x[1])
print("客户数:", len(byc), "| Top3 占比:", round(sum(v for _,v in top[:3]) / tot * 100, 1), "%")
for n, v in top[:5]:
    print(f"  {n:28s} {v:>13,.0f}  {v/tot*100:5.1f}%")
print("\n业务员:", len({r['s'] for r in rows}), "| 币种:", sorted({r['ccy'] for r in rows}))
