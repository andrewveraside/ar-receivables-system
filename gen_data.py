# -*- coding: utf-8 -*-
"""生成 100 条虚构应收账款账目 -> data/ar_data.json + 应收账款台账_示例100条.xlsx"""
import json, random, datetime as dt
from pathlib import Path

random.seed(20261027)
BASE = Path(__file__).resolve().parent
(BASE / "data").mkdir(exist_ok=True)

TODAY = dt.date(2026, 10, 27)

CUSTOMERS = [
    ("C001", "HANSA TRADING GmbH", "德国", "DE", 30),
    ("C002", "NORDIC HOME AB", "瑞典", "SE", 30),
    ("C003", "ALPINE SPORT AG", "奥地利", "AT", 45),
    ("C004", "MEDITERRANEO SRL", "意大利", "IT", 60),
    ("C005", "IBERIA TEXTIL SL", "西班牙", "ES", 45),
    ("C006", "ATLANTIC GOODS LTD", "英国", "GB", 30),
    ("C007", "MAPLE LEAF IMPORTS INC", "加拿大", "CA", 60),
    ("C008", "PACIFIC RIM LLC", "美国", "US", 60),
    ("C009", "GOLDEN GATE SUPPLY CO", "美国", "US", 30),
    ("C010", "SAHARA DISTRIBUTION SARL", "摩洛哥", "MA", 90),
    ("C011", "NILE TRADING CO", "埃及", "EG", 90),
    ("C012", "GULF STAR GENERAL TRD", "阿联酋", "AE", 45),
    ("C013", "ORIENT BRIDGE PTE LTD", "新加坡", "SG", 30),
    ("C014", "SAKURA IMPORTS KK", "日本", "JP", 30),
    ("C015", "HAN RIVER CO LTD", "韩国", "KR", 30),
    ("C016", "OZ DIRECT PTY LTD", "澳大利亚", "AU", 45),
    ("C017", "ANDES COMERCIAL SA", "智利", "CL", 90),
    ("C018", "SANTOS TRADING LTDA", "巴西", "BR", 120),
    ("C019", "KIEV IMPORT GROUP", "乌克兰", "UA", 120),
    ("C020", "PRAHA TRADING SRO", "捷克", "CZ", 45),
]

SALESMEN = ["周小杰", "刘小源", "张大丽"]

# 币种 -> 2026-10-27 中间价（虚构近似值）
CCY = {
    "USD": 7.1085, "EUR": 7.7420, "GBP": 9.1840, "JPY": 0.04712,
    "AUD": 4.6820, "CAD": 5.1240, "SGD": 5.4180, "KRW": 0.00498,
}
CCY_BY_COUNTRY = {"US": "USD", "DE": "EUR", "SE": "SEK", "AT": "EUR", "IT": "EUR",
                  "ES": "EUR", "GB": "GBP", "CA": "CAD", "MA": "USD", "EG": "USD",
                  "AE": "USD", "SG": "SGD", "JP": "JPY", "KR": "USD", "AU": "AUD",
                  "CL": "USD", "BR": "USD", "UA": "USD", "CZ": "EUR"}
CCY["SEK"] = 0.6742  # 补一个 SEK

# 简化：每个币种各月汇率（相对中间价漂移 ±3%）
def rate_for(ccy, d):
    base = CCY[ccy]
    drift = ((d.year - 2026) * 12 + d.month) * -0.0016  # 越早越不同
    return round(base * (1 + drift + random.uniform(-0.012, 0.012)), 6)

INV_PREFIX = "INV2610"

rows = []
for i in range(1, 101):
    code, name, country, cc, pay_days = random.choice(CUSTOMERS)
    ccy = CCY_BY_COUNTRY[cc]
    # 发票日期：近 300 天内
    inv_date = TODAY - dt.timedelta(days=random.randint(5, 300))
    due_date = inv_date + dt.timedelta(days=pay_days)

    # 不含税金额（原币），按币种给量级
    if ccy == "JPY":
        amt = round(random.uniform(1_200_000, 9_800_000), 0)
    elif ccy == "KRW":
        amt = round(random.uniform(9_000_000, 60_000_000), 0)
    else:
        amt = round(random.uniform(8_000, 120_000), 2)

    tax_rate = 0.0  # 出口零税率
    ex_rate = rate_for(ccy, inv_date)
    cny_amt = round(amt * ex_rate, 2)  # 含税=不含税（出口免税）

    # 已收金额：年轻账龄多已收，老账龄少已收
    days_past = (TODAY - due_date).days
    if days_past < 0:
        paid_ratio = random.choice([0, 0, 0, 0.3, 0.5, 1.0])
    elif days_past <= 30:
        paid_ratio = random.choice([0, 0, 0.2, 0.4, 0.7, 1.0])
    elif days_past <= 90:
        paid_ratio = random.choice([0, 0, 0.1, 0.3, 0.6])
    elif days_past <= 180:
        paid_ratio = random.choice([0, 0, 0, 0.2, 0.5])
    else:
        paid_ratio = random.choice([0, 0, 0, 0, 0.2])
    paid_amt = round(amt * paid_ratio, 2)

    rows.append({
        "发票号": f"{INV_PREFIX}{i:04d}",
        "客户代码": code,
        "客户名称": name,
        "国家": country,
        "业务员": random.choice(SALESMEN),
        "发票日期": inv_date.isoformat(),
        "账期天": pay_days,
        "到期日": due_date.isoformat(),
        "币种": ccy,
        "汇率": ex_rate,
        "不含税金额": amt,
        "出口退税率": random.choice([0.13, 0.09, 0.0]),
        "已收金额": paid_amt,
        "本位币金额": cny_amt,
        "本位币已收": round(paid_amt * ex_rate, 2),
    })

data = {
    "meta": {
        "title": "应收账款台账",
        "generated": TODAY.isoformat(),
        "note": "100 条虚构数据，仅用于演示看板能力",
        "customers": [{"code": c[0], "name": c[1], "country": c[2], "cc": c[3], "paydays": c[4]} for c in CUSTOMERS],
        "rates": CCY,
    },
    "rows": rows,
}

(BASE / "data" / "ar_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- 生成 Excel 台账 ----
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule

wb = Workbook()
ws = wb.active
ws.title = "03_应收单据"

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=10)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

headers = ["发票号", "客户代码", "客户名称", "国家", "业务员", "发票日期", "账期天", "到期日",
           "币种", "汇率", "不含税金额", "出口退税率", "已收金额", "本位币金额", "本位币已收",
           "未收原币", "未收本位币", "逾期天数", "账龄档", "单据状态"]
ws.append(headers)
for c in ws[1]:
    c.fill = HEAD_FILL; c.font = HEAD_FONT
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = BORDER

for r, row in enumerate(rows, start=2):
    ws.cell(r, 1, row["发票号"])
    ws.cell(r, 2, row["客户代码"])
    ws.cell(r, 3, row["客户名称"])
    ws.cell(r, 4, row["国家"])
    ws.cell(r, 5, row["业务员"])
    ws.cell(r, 6, dt.date.fromisoformat(row["发票日期"]))
    ws.cell(r, 7, row["账期天"])
    ws.cell(r, 8, dt.date.fromisoformat(row["到期日"]))
    ws.cell(r, 9, row["币种"])
    ws.cell(r, 10, row["汇率"])
    ws.cell(r, 11, row["不含税金额"])
    ws.cell(r, 12, row["出口退税率"])
    ws.cell(r, 13, row["已收金额"])
    ws.cell(r, 14, f"=K{r}*J{r}")
    ws.cell(r, 15, f"=M{r}*J{r}")
    ws.cell(r, 16, f"=K{r}-M{r}")
    ws.cell(r, 17, f"=N{r}-O{r}")
    ws.cell(r, 18, f'=IF(Q{r}<=0,0,TODAY()-H{r})')
    ws.cell(r, 19, f'=IF(Q{r}<=0,"未到期",IF(S{r}<=30,"1-30天",IF(S{r}<=60,"31-60天",IF(S{r}<=90,"61-90天",IF(S{r}<=180,"91-180天","180天以上")))))')
    ws.cell(r, 20, f'=IF(Q{r}<=0,"未到期",IF(S{r}>0,"逾期","已结清"))')

for r in range(2, 102):
    for c in range(1, 21):
        cell = ws.cell(r, c)
        cell.border = BORDER
        if c in (6, 8):
            cell.number_format = "yyyy-mm-dd"
        elif c in (11, 13, 14, 15, 16, 17):
            cell.number_format = "#,##0.00"
        elif c == 10:
            cell.number_format = "0.0000"
        elif c == 12:
            cell.number_format = "0%"

widths = [14, 10, 26, 8, 9, 12, 8, 12, 7, 10, 14, 10, 13, 14, 14, 13, 14, 9, 11, 10]
for i, w in enumerate(widths, start=1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"
ws.auto_filter.ref = "A1:T101"

dv = DataValidation(type="list", formula1='"USD,EUR,GBP,JPY,AUD,CAD,SGD,KRW,SEK"', allow_blank=True)
ws.add_data_validation(dv); dv.add("I2:I500")

ws.conditional_formatting.add("S2:S101",
    CellIsRule(operator="greaterThan", formula=["180"], fill=PatternFill("solid", fgColor="FFC7CE"), font=Font(color="9C0006")))
ws.conditional_formatting.add("Q2:Q101",
    ColorScaleRule(start_type="min", start_color="C6EFCE", mid_type="percentile", mid_value=50, mid_color="FFEB9C",
                   end_type="max", end_color="FFC7CE"))

# 参数表
ws2 = wb.create_sheet("01_参数")
ws2.append(["参数项", "值", "说明"])
ws2.append(["账龄分档", "30/60/90/180", "逾期天数分档"])
ws2.append(["坏账计提-1-30天", 0.05, "按未收本位币计提"])
ws2.append(["坏账计提-31-90天", 0.10, ""])
ws2.append(["坏账计提-91-180天", 0.30, ""])
ws2.append(["坏账计提-180天以上", 0.50, ""])
for r in range(1, 7):
    for c in range(1, 4):
        ws2.cell(r, c).border = BORDER
for c in ws2[1]:
    c.fill = HEAD_FILL; c.font = HEAD_FONT
ws2.column_dimensions["A"].width = 22
ws2.column_dimensions["B"].width = 14
ws2.column_dimensions["C"].width = 40

wb.save(BASE / "数据源_应收账款台账_示例100条.xlsx")
print("OK rows=", len(rows))
print("未收本位币合计=", round(sum(x["本位币金额"] - x["本位币已收"] for x in rows), 2))
