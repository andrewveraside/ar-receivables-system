# -*- coding: utf-8 -*-
"""把 ar_data.json 渲染成单文件 HTML 看板（ECharts 内嵌，完全离线）"""
import json, datetime as dt
from pathlib import Path
from collections import defaultdict

import sys

BASE = Path(__file__).resolve().parent

# 数据源选择：--source=bridge 用合同库生成的数据（bridge.py 产物）；默认用示例 100 条
SOURCE = "bridge" if "--source=bridge" in sys.argv else "ar_data"
if SOURCE == "bridge":
    bridge_file = BASE / "data" / "ar_bridge.json"
    if not bridge_file.exists():
        sys.exit("找不到 data/ar_bridge.json，先跑 python bridge.py")
    data = json.loads(bridge_file.read_text(encoding="utf-8"))
    rows = data["rows"]
    # 客户清单从行里反推（合同库驱动时没有独立客户表）
    _seen = {}
    for r in rows:
        _seen.setdefault(r["客户代码"], {"code": r["客户代码"], "name": r["客户名称"],
                                       "country": r["国家"], "cc": "", "paydays": r["账期天"]})
    cust = _seen
    OUT_NAME = "应收账款看板_合同库版.html"
else:
    data = json.loads((BASE / "data" / "ar_data.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    cust = {c["code"]: c for c in data["meta"]["customers"]}
    OUT_NAME = None

TODAY = dt.date.today()

BUCKETS = [("未到期", None, 0), ("1-30天", 1, 30), ("31-60天", 31, 60),
           ("61-90天", 61, 90), ("91-180天", 91, 180), ("180天以上", 181, 10**9)]

def bucket_of(days_past):
    if days_past <= 0:
        return "未到期"
    for name, lo, hi in BUCKETS[1:]:
        if lo <= days_past <= hi:
            return name
    return "180天以上"

recs = []
for r in rows:
    inv = dt.date.fromisoformat(r["发票日期"])
    due = dt.date.fromisoformat(r["到期日"])
    open_amt = round(r["不含税金额"] - r["已收金额"], 2)
    open_cny = round(open_amt * r["汇率"], 2)
    days_past = max(0, (TODAY - due).days)
    recs.append({
        "id": r["发票号"], "c": r["客户代码"], "cn": r["客户名称"], "co": r["国家"],
        "s": r["业务员"], "d": r["发票日期"], "due": r["到期日"], "pay": r["账期天"],
        "ccy": r["币种"], "rate": r["汇率"], "amt": r["不含税金额"],
        "paid": r["已收金额"], "open": open_amt, "openCny": open_cny,
        "overdue": days_past, "bucket": bucket_of(days_past),
        "agingDays": (TODAY - inv).days,
        "status": "未到期" if days_past <= 0 else ("逾期" if open_amt > 0 else "已结清"),
        "topRisk": 0,
    })

# 客户聚合
by_cust = defaultdict(lambda: {"open": 0.0, "over90": 0.0, "cnt": 0, "overdue": 0.0})
for r in recs:
    d = by_cust[r["c"]]
    d["open"] += r["openCny"]; d["cnt"] += 1
    if r["bucket"] not in ("未到期",):
        d["overdue"] += r["openCny"]
    if r["bucket"] in ("91-180天", "180天以上"):
        d["over90"] += r["openCny"]

payload = {
    "today": TODAY.isoformat(),
    "rows": recs,
    "customers": list(cust.values()),
    "source": SOURCE,
    "meta": data.get("meta", {}),
}

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>应收账款看板 · 示例100条</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"Microsoft YaHei","PingFang SC",Inter,system-ui,-apple-system,sans-serif;
       background:#0d1117;color:#e6edf3;padding:20px 24px 40px}
  h1{font-size:20px;font-weight:650;letter-spacing:.3px;display:flex;align-items:center;gap:10px}
  h1 .dot{width:8px;height:8px;border-radius:50%;background:#2ea043;box-shadow:0 0 10px #2ea043}
  .sub{color:#7d8590;font-size:12.5px;margin-top:5px}
  .wrap{max-width:1560px;margin:0 auto}
  .topnav{display:flex;align-items:center;gap:14px;margin-bottom:14px;padding-bottom:12px;
          border-bottom:1px solid #21262d}
  .topnav .spacer{flex:1}
  .topnav .back{color:#58a6ff;text-decoration:none;font-size:13px;padding:5px 11px;
                border:1px solid #30363d;border-radius:6px;transition:.15s}
  .topnav .back:hover{background:#1f2b3d;border-color:#1f6feb}
  .topnav .src{font-size:11.5px;color:#6e7681}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:18px 0 16px;padding:12px 14px;
       background:#161b22;border:1px solid #21262d;border-radius:10px}
  .bar label{font-size:12px;color:#8b949e}
  select{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;
         padding:6px 10px;font-size:12.5px;font-family:inherit;outline:none;min-width:132px}
  select:focus{border-color:#1f6feb}
  .btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;
       padding:6px 12px;font-size:12.5px;cursor:pointer;font-family:inherit}
  .btn:hover{background:#30363d;border-color:#8b949e}
  .spacer{flex:1}
  .hint{font-size:11.5px;color:#6e7681}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(212px,1fr));gap:14px;margin-bottom:16px}
  .kpi{background:linear-gradient(160deg,#161b22,#131921);border:1px solid #21262d;border-radius:12px;
       padding:16px 18px;position:relative;overflow:hidden}
  .kpi:after{content:"";position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;
             background:radial-gradient(circle,rgba(31,111,235,.18),transparent 70%)}
  .kpi .t{font-size:12px;color:#8b949e;letter-spacing:.5px}
  .kpi .v{font-size:27px;font-weight:660;margin-top:8px;letter-spacing:-.5px;font-variant-numeric:tabular-nums}
  .kpi .f{font-size:11.5px;color:#6e7681;margin-top:7px}
  .kpi.warn .v{color:#f0883e}.kpi.bad .v{color:#f85149}.kpi.good .v{color:#3fb950}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
  .card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:14px 16px 6px}
  .card .hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}
  .card .hd span{font-size:13px;font-weight:600;color:#c9d1d9}
  .card .hd em{font-size:11px;color:#6e7681;font-style:normal}
  .chart{width:100%}
  .full{grid-column:1/-1}
  table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
  th{text-align:left;font-weight:600;color:#8b949e;font-size:11.5px;padding:8px 10px;
     border-bottom:1px solid #21262d;position:sticky;top:0;background:#161b22;z-index:2}
  td{padding:8px 10px;border-bottom:1px solid #1b2129;color:#c9d1d9}
  td.num,th.num{text-align:right}
  tbody tr:hover{background:#1c2430}
  .tag{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:500}
  .t-ok{background:rgba(63,185,80,.14);color:#3fb950}
  .t-warn{background:rgba(240,136,62,.14);color:#f0883e}
  .t-bad{background:rgba(248,81,73,.14);color:#f85149}
  .t-idle{background:rgba(139,148,158,.14);color:#8b949e}
  .scroll{max-height:420px;overflow:auto}
  .scroll::-webkit-scrollbar{width:8px;height:8px}
  .scroll::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
  .tooltip-note{font-size:11px;color:#6e7681;padding:8px 2px 10px}
  @media(max-width:1080px){.grid{grid-template-columns:1fr}}
  @media print{body{background:#fff;color:#000}.bar,.btn{display:none}}
</style>
<script>__ECHARTS__</script>
</head>
<body>
<div class="wrap">
  <div class="topnav">
    <a class="back" id="backBtn" href="/" target="_self">← 返回合同录入</a>
    <span class="src" id="srcNote"></span>
    <span class="spacer"></span>
    <button class="btn ghost" onclick="reloadSelf()">重新加载</button>
  </div>
  <h1><span class="dot"></span>应收账款看板<span style="font-size:12px;color:#6e7681;font-weight:400" id="srcTag"></span></h1>
  <div class="sub">数据截至 <b id="asOf"></b> · 本位币 CNY · 点击任意图表联动筛选 · 支持钻取</div>

  <div class="bar">
    <label>客户</label><select id="fCust"><option value="">全部客户</option></select>
    <label>业务员</label><select id="fSale"><option value="">全部</option></select>
    <label>币种</label><select id="fCcy"><option value="">全部</option></select>
    <label>账龄档</label><select id="fBucket"><option value="">全部</option></select>
    <label>状态</label><select id="fStatus"><option value="">全部</option>
      <option value="未到期">未到期</option><option value="逾期">逾期</option><option value="已结清">已结清</option></select>
    <span class="spacer"></span>
    <span class="hint" id="filterNote"></span>
    <button class="btn" onclick="resetAll()">重置筛选</button>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="card"><div class="hd"><span>账龄结构</span><em>未收本位币 · 点击柱体筛选</em></div>
      <div id="cAging" class="chart" style="height:300px"></div></div>
    <div class="card"><div class="hd"><span>客户集中度 Top 10</span><em>未收本位币 · 点击柱体筛选客户</em></div>
      <div id="cTop" class="chart" style="height:300px"></div></div>
    <div class="card"><div class="hd"><span>逾期趋势</span><em>按到期月份 · 未到期/逾期</em></div>
      <div id="cTrend" class="chart" style="height:290px"></div></div>
    <div class="card"><div class="hd"><span>币种分布</span><em>未收本位币占比</em></div>
      <div id="cCcy" class="chart" style="height:290px"></div></div>
    <div class="card full"><div class="hd"><span>客户 × 账龄 热力矩阵</span><em>颜色越深金额越大，单位：万元</em></div>
      <div id="cHeat" class="chart" style="height:420px"></div></div>
    <div class="card full"><div class="hd"><span>明细清单</span><em id="detailCount"></em></div>
      <div class="scroll"><table id="tbl">
        <thead><tr>
          <th>发票号</th><th>客户</th><th>国家</th><th>业务员</th><th>发票日期</th><th>到期日</th>
          <th class="num">币种</th><th class="num">原币金额</th><th class="num">未收原币</th>
          <th class="num">未收本位币</th><th class="num">逾期天数</th><th>账龄档</th><th>状态</th>
        </tr></thead><tbody></tbody>
      </table></div>
    </div>
  </div>
</div>

<script>
const D = __DATA__;
const C = {blue:'#1f6feb',cyan:'#39c5cf',green:'#2ea043',orange:'#f0883e',red:'#f85149',
           purple:'#8957e5',yellow:'#d29922',gray:'#30363d',text:'#c9d1d9',dim:'#8b949e'};
const BUCKET_COLOR = {'未到期':C.green,'1-30天':C.cyan,'31-60天':C.yellow,
                      '61-90天':C.orange,'91-180天':'#db6d28','180天以上':C.red};
const BUCKETS = ['未到期','1-30天','31-60天','61-90天','91-180天','180天以上'];
const fmt = n => (n/10000).toFixed(1);
const money = n => '¥' + n.toLocaleString('zh-CN',{minimumFractionDigits:0,maximumFractionDigits:0});

let state = {cust:'',sale:'',ccy:'',bucket:'',status:''};
let charts = {};

function filtered(){ return D.rows.filter(r =>
  (!state.cust || r.c===state.cust) && (!state.sale || r.s===state.sale) &&
  (!state.ccy || r.ccy===state.ccy) && (!state.bucket || r.bucket===state.bucket) &&
  (!state.status || r.status===state.status)); }

function sum(arr,f){ return arr.reduce((a,b)=>a+b[f],0); }

function render(){ const R = filtered(); drawKPI(R); drawAging(R); drawTop(R); drawTrend(R); drawCcy(R); drawHeat(R); drawTable(R); }

function drawKPI(R){
  const total=sum(R,'openCny'), overdue=R.filter(r=>r.status==='逾期');
  const odAmt=sum(overdue,'openCny');
  const over90=R.filter(r=>r.bucket==='91-180天'||r.bucket==='180天以上');
  const o90=sum(over90,'openCny');
  const eff=sum(R,'amt')? (sum(R,'openCny')/ (sum(R,'amt')*1))*100:0;
  const dso = R.length? Math.round(sum(R,'agingDays')/R.length):0;
  const rate = total? (odAmt/total*100):0;
  const k=[
    {t:'未收应收总额',v:money(total),f:`${R.length} 张单据 · 本位币 CNY`,cls:''},
    {t:'逾期金额',v:money(odAmt),f:`${overdue.length} 张逾期 · 占比 ${rate.toFixed(1)}%`,cls:rate>30?'bad':'warn'},
    {t:'严重逾期(>90天)',v:money(o90),f:`${over90.length} 张 · 建议重点催收`,cls:o90/total>0.15?'bad':''},
    {t:'平均账龄 DSO',v:dso+' 天',f:'按发票日至今天数均值',cls:dso>90?'warn':'good'},
    {t:'客户数',v:new Set(R.map(r=>r.c)).size,f:'涉及 '+new Set(R.map(r=>r.s)).size+' 名业务员',cls:''},
    {t:'单均金额',v:R.length?money(total/R.length):'¥0',f:'未收本位币 / 单据数',cls:''},
  ];
  document.getElementById('kpis').innerHTML = k.map(x=>
    `<div class="kpi ${x.cls}"><div class="t">${x.t}</div><div class="v">${x.v}</div><div class="f">${x.f}</div></div>`).join('');
}

function mk(id,opt){ if(!charts[id]) charts[id]=echarts.init(document.getElementById(id),null,{renderer:'canvas'});
  charts[id].setOption(opt,true); }

const AXIS={axisLine:{lineStyle:{color:C.gray}},axisLabel:{color:C.dim,fontSize:11},
            splitLine:{lineStyle:{color:'#21262d'}},axisTick:{show:false}};

function drawAging(R){
  const v=BUCKETS.map(b=>sum(R.filter(r=>r.bucket===b),'openCny'));
  mk('cAging',{grid:{left:8,right:16,top:18,bottom:22,containLabel:true},
    tooltip:{trigger:'axis',backgroundColor:'#0d1117',borderColor:C.gray,textStyle:{color:C.text},
      formatter:p=>`${p[0].name}<br/><b>${money(p[0].value)}</b>（${fmt(p[0].value)} 万）`},
    xAxis:{type:'category',data:BUCKETS,...AXIS,axisLabel:{color:C.dim,fontSize:10.5}},
    yAxis:{type:'value',...AXIS,axisLabel:{color:C.dim,fontSize:10.5,formatter:v=>fmt(v)+'万'}},
    series:[{type:'bar',data:v.map((x,i)=>({value:x,itemStyle:{color:BUCKET_COLOR[BUCKETS[i]],borderRadius:[5,5,0,0]}})),
      barMaxWidth:46,label:{show:true,position:'top',color:C.text,fontSize:10.5,formatter:p=>fmt(p.value)}}]});
}

function drawTop(R){
  const m={}; R.forEach(r=>m[r.cn]=(m[r.cn]||0)+r.openCny);
  const arr=Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10).reverse();
  mk('cTop',{grid:{left:8,right:56,top:12,bottom:18,containLabel:true},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'#0d1117',borderColor:C.gray,
      textStyle:{color:C.text},formatter:p=>`${p[0].name}<br/><b>${money(p[0].value)}</b>`},
    xAxis:{type:'value',...AXIS,axisLabel:{color:C.dim,fontSize:10.5,formatter:v=>fmt(v)+'万'}},
    yAxis:{type:'category',data:arr.map(a=>a[0]),...AXIS,axisLabel:{color:C.text,fontSize:11}},
    series:[{type:'bar',data:arr.map(a=>a[1]),barMaxWidth:16,
      itemStyle:{color:new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#1a4a8a'},{offset:1,color:C.blue}]),borderRadius:[0,4,4,0]},
      label:{show:true,position:'right',color:C.dim,fontSize:10.5,formatter:p=>fmt(p.value)}}]});
}

function drawTrend(R){
  const m={}; R.forEach(r=>{ const k=r.due.slice(0,7); m[k]=m[k]||{ok:0,od:0};
    r.status==='逾期'? m[k].od+=r.openCny : m[k].ok+=r.openCny; });
  const ks=Object.keys(m).sort();
  mk('cTrend',{grid:{left:8,right:16,top:28,bottom:20,containLabel:true},
    legend:{data:['未到期','逾期'],textStyle:{color:C.dim,fontSize:11},top:0,right:0,itemWidth:10,itemHeight:10},
    tooltip:{trigger:'axis',backgroundColor:'#0d1117',borderColor:C.gray,textStyle:{color:C.text},
      formatter:p=>p[0].axisValue+'<br/>'+p.map(x=>`${x.marker}${x.seriesName} <b>${money(x.value)}</b>`).join('<br/>')},
    xAxis:{type:'category',data:ks,...AXIS,axisLabel:{color:C.dim,fontSize:10.5}},
    yAxis:{type:'value',...AXIS,axisLabel:{color:C.dim,fontSize:10.5,formatter:v=>fmt(v)+'万'}},
    series:[
      {name:'未到期',type:'bar',stack:'t',data:ks.map(k=>m[k].ok),barMaxWidth:26,itemStyle:{color:'#1f6feb'}},
      {name:'逾期',type:'bar',stack:'t',data:ks.map(k=>m[k].od),barMaxWidth:26,itemStyle:{color:C.red,borderRadius:[4,4,0,0]}}]});
}

function drawCcy(R){
  const m={}; R.forEach(r=>m[r.ccy]=(m[r.ccy]||0)+r.openCny);
  const arr=Object.entries(m).sort((a,b)=>b[1]-a[1]).map(([n,v])=>({name:n,value:Math.round(v)}));
  mk('cCcy',{tooltip:{trigger:'item',backgroundColor:'#0d1117',borderColor:C.gray,textStyle:{color:C.text},
      formatter:p=>`${p.name}<br/><b>${money(p.value)}</b> · ${p.percent}%`},
    legend:{orient:'vertical',right:8,top:'center',textStyle:{color:C.dim,fontSize:11},itemWidth:9,itemHeight:9},
    series:[{type:'pie',radius:['52%','76%'],center:['38%','50%'],avoidLabelOverlap:true,
      itemStyle:{borderColor:'#161b22',borderWidth:2},
      label:{show:false},labelLine:{show:false},
      data:arr,color:['#1f6feb','#39c5cf','#8957e5','#d29922','#2ea043','#f0883e','#f85149','#8b949e']}]});
}
function drawHeat(R){
  const names=[...new Set(R.map(r=>r.cn))];
  const m={}; R.forEach(r=>{ m[r.c+'|'+r.bucket]=(m[r.c+'|'+r.bucket]||0)+r.openCny; });
  const cst={}; R.forEach(r=>cst[r.c]=r.cn);
  const codes=Object.keys(cst).sort((a,b)=>{
    const x=BUCKETS.reduce((s,b)=>s+(m[a+'|'+b]||0),0), y=BUCKETS.reduce((s,b)=>s+(m[b+'|'+b]||0),0);
    return BUCKETS.reduce((s,b)=>s+(m[b+'|'+b]||0),0)-BUCKETS.reduce((s,b)=>s+(m[a+'|'+b]||0),0);});
  const d=[]; codes.forEach((c,ci)=>BUCKETS.forEach((b,bi)=>{
    const v=m[c+'|'+b]||0; if(v>0) d.push([bi,ci,Math.round(v/1000)/10]); }));  // 单位：万元
  const max=Math.max(...d.map(x=>x[2]),1);
  mk('cHeat',{grid:{left:8,right:90,top:10,bottom:26,containLabel:true},
    tooltip:{backgroundColor:'#0d1117',borderColor:C.gray,textStyle:{color:C.text},
      formatter:p=>`${codes[p.value[1]]} · ${BUCKETS[p.value[0]]}<br/><b>${p.value[2]} 万元</b>`},
    xAxis:{type:'category',data:BUCKETS,splitArea:{show:false},...AXIS},
    yAxis:{type:'category',data:codes.map(c=>cst[c]),splitArea:{show:false},...AXIS,
           axisLabel:{color:C.text,fontSize:11}},
    visualMap:{min:0,max:max,calculable:true,orient:'vertical',right:0,top:'center',
      inRange:{color:['#12202e','#164b8a','#1f6feb','#f0883e','#f85149']},
      textStyle:{color:C.dim,fontSize:10},itemWidth:12,itemHeight:130,text:['高','低']},
    series:[{type:'heatmap',data:d,itemStyle:{borderColor:'#0d1117',borderWidth:1.5},
      label:{show:true,color:'#fff',fontSize:10,formatter:p=>p.value[2]>=1?p.value[2].toFixed(0):''},
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1}}}]});
}

function drawTable(R){
  const tb=document.querySelector('#tbl tbody');
  const sorted=[...R].sort((a,b)=>b.openCny-a.openCny).slice(0,200);
  tb.innerHTML=sorted.map(r=>{
    const cls=r.status==='逾期'?(r.bucket==='180天以上'||r.bucket==='91-180天'?'t-bad':'t-warn'):
              (r.status==='未到期'?'t-idle':'t-ok');
    return `<tr><td>${r.id}</td><td>${r.cn}</td><td>${r.co}</td><td>${r.s}</td>
      <td>${r.d}</td><td>${r.due}</td>
      <td class="num">${r.ccy}</td><td class="num">${r.amt.toLocaleString('zh-CN',{maximumFractionDigits:2})}</td>
      <td class="num">${r.open.toLocaleString('zh-CN',{maximumFractionDigits:2})}</td>
      <td class="num">${Math.round(r.openCny).toLocaleString('zh-CN')}</td>
      <td class="num">${r.overdue||'-'}</td><td>${r.bucket}</td>
      <td><span class="tag ${cls}">${r.status}</span></td></tr>`;}).join('');
  document.getElementById('detailCount').textContent=`命中 ${R.length} 张 · 按未收金额降序，最多显示 200 行`;
}

function bindChartClick(){
  charts['cAging'].on('click',p=>{ state.bucket = state.bucket===p.name?'':p.name;
    document.getElementById('fBucket').value=state.bucket; sync(); });
  charts['cTop'].on('click',p=>{ const c=D.customers.find(x=>x.name===p.name);
    if(c){ state.cust = state.cust===c.code?'':c.code; document.getElementById('fCust').value=state.cust; sync(); } });
}

function sync(){
  const n=Object.values(state).filter(Boolean).length;
  document.getElementById('filterNote').textContent = n? `已应用 ${n} 个筛选条件` : '未筛选';
  render();
}

function resetAll(){ state={cust:'',sale:'',ccy:'',bucket:'',status:''};
  ['fCust','fSale','fCcy','fBucket','fStatus'].forEach(id=>document.getElementById(id).value=''); sync(); }

function reloadSelf(){ location.reload(); }

function init(){
  document.getElementById('asOf').textContent=D.today;
  // 数据来源标注 + 返回按钮智能显隐（file:// 打开时没有录入系统可返回）
  try{
    const meta = D.meta || {};
    const isBridge = (D.source === 'bridge');
    const tag = document.getElementById('srcTag');
    if(tag) tag.textContent = isBridge
      ? ('合同库驱动 · ' + (meta.contract_count||0) + ' 份合同 · 生成于 ' + (meta.generated||''))
      : ('示例数据 ' + (D.rows||[]).length + ' 条');
    const src = document.getElementById('srcNote');
    if(src) src.textContent = isBridge ? '数据源：data/contracts.db' : '数据源：示例数据';
    const back = document.getElementById('backBtn');
    if(back && location.protocol === 'file:') back.style.display = 'none';
  }catch(e){}
  const f1=document.getElementById('fCust');
  [...new Set(D.rows.map(r=>r.c))].sort().forEach(c=>{
    const cu=D.customers.find(x=>x.code===c);
    f1.insertAdjacentHTML('beforeend',`<option value="${c}">${c} ${cu?cu.name:c}</option>`);});
  [...new Set(D.rows.map(r=>r.s))].sort().forEach(s=>
    document.getElementById('fSale').insertAdjacentHTML('beforeend',`<option>${s}</option>`));
  [...new Set(D.rows.map(r=>r.ccy))].sort().forEach(s=>
    document.getElementById('fCcy').insertAdjacentHTML('beforeend',`<option>${s}</option>`));
  BUCKETS.forEach(s=>
    document.getElementById('fBucket').insertAdjacentHTML('beforeend',`<option>${s}</option>`));
  const map={fCust:'cust',fSale:'sale',fCcy:'ccy',fBucket:'bucket',fStatus:'status'};
  Object.entries(map).forEach(([id,k])=>document.getElementById(id)
    .addEventListener('change',e=>{state[k]=e.target.value; sync();}));
  render(); setTimeout(bindChartClick,120);
  // 图表尺寸自适应：iframe 内初次渲染时容器宽度可能为 0，需在下一帧后再 resize
  const resizeAll = () => { Object.values(charts).forEach(c => { try{ c.resize(); }catch(e){} }); };
  window.addEventListener('resize', resizeAll);
  if (window.ResizeObserver) {
    try {
      const ro = new ResizeObserver(() => resizeAll());
      ro.observe(document.body);
    } catch(e){}
  }
  // iframe 场景：父页面完成布局后主动通知 / 或本帧尺寸变化时补齐
  [0, 60, 200, 600, 1500].forEach(t => setTimeout(resizeAll, t));
}

// 启动
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else { init(); }
</script>
</body>
</html>
"""

# 内嵌 echarts
echarts_src = None
cand = BASE / "echarts.min.js"
if cand.exists():
    echarts_src = cand.read_text(encoding="utf-8")

if echarts_src:
    html = html.replace("__ECHARTS__", echarts_src)
    out = BASE / (OUT_NAME.replace(".html", "_离线版.html") if OUT_NAME else "应收账款看板_离线版.html")
else:
    # CDN 版
    html = html.replace("<script>__ECHARTS__</script>",
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>')
    out = BASE / (OUT_NAME.replace(".html", "_CDN版.html") if OUT_NAME else "应收账款看板_CDN版.html")

# 关键：一次性替换，用 str.replace 传入 dict 无意义，改为顺序替换且先长后短
# __DATA__ 与 __PAYLOAD__ 互不为前缀以外的子串关系，但 __DATA__ 出现在 __PAYLOAD__ 中不成立，
# 之前 bug 的根因是旧版尾块把 "PAYLOAD" 也一并换掉。现在两处占位均独立，安全。
DATA_JSON = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
html = html.replace("__PAYLOAD__", DATA_JSON)
html = html.replace("__DATA__", DATA_JSON)
assert "__DATA__" not in html and "__PAYLOAD__" not in html, "占位符未替换干净"

out.write_text(html, encoding="utf-8")
print("written:", out.name, round(out.stat().st_size / 1024, 1), "KB")
print("rows:", len(recs), "total_open_cny:", round(sum(r['openCny'] for r in recs), 2))
