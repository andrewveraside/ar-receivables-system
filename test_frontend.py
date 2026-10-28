# -*- coding: utf-8 -*-
"""前端 JS 逻辑校验：stub DOM + fetch，在 node 里实跑 web/index.html 的脚本"""
import json
import os
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
html = (BASE / "web" / "index.html").read_text(encoding="utf-8")
blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
js = blocks[-1]

CUSTOMERS = {"ok": True, "data": [
    {"id": 1, "code": "C001", "name": "HANSA TRADING GmbH", "country": "德国", "currency": "EUR",
     "pay_days": 30, "credit_limit": 800000, "salesman": "周小杰", "contact": "Hans", "email": "a@b"},
    {"id": 2, "code": "C008", "name": "PACIFIC RIM LLC", "country": "美国", "currency": "USD",
     "pay_days": 60, "credit_limit": 1500000, "salesman": "张大丽", "contact": "Mike", "email": "c@d"},
]}
CONTRACTS = {"ok": True, "data": [
    {"id": 1, "contract_no": "HT-2026-001", "customer_id": 1, "customer_name": "HANSA TRADING GmbH",
     "customer_code": "C001", "country": "德国", "sign_date": "2026-10-01", "start_date": "2026-10-01",
     "end_date": "2027-10-01", "currency": "EUR", "amount": 125000.5, "pay_term": "T/T 45天",
     "trade_term": "FOB", "status": "执行中", "salesman": "周小杰", "remark": ""},
    {"id": 2, "contract_no": "HT-2026-002", "customer_id": 2, "customer_name": "PACIFIC RIM LLC",
     "customer_code": "C008", "country": "美国", "sign_date": "2026-09-15", "start_date": "2026-09-15",
     "end_date": "2027-09-15", "currency": "USD", "amount": 88000, "pay_term": "L/C 60天",
     "trade_term": "CIF", "status": "已完结", "salesman": "张大丽", "remark": ""},
]}
STATS = {"ok": True, "customers": 2, "contracts": 2,
         "by_status": {"执行中": 1, "已完结": 1}, "total_amount": 213000.5,
         "latest": CONTRACTS["data"],
         "options": {"currencies": ["USD", "EUR", "GBP"],
                     "statuses": ["草签", "执行中", "已完结", "已作废"],
                     "salesmen": ["周小杰", "刘小源", "张大丽"]}}

DATA_JS = "\n".join(
    "var %s = %s;" % (k, json.dumps(v, ensure_ascii=False))
    for k, v in [("CUSTOMERS", CUSTOMERS), ("CONTRACTS", CONTRACTS), ("STATS", STATS)]
) + "\n"

pre = r"""
// ---- stub DOM ----
var __els = {};
function El(id){ this.id=id; this.value=''; this.innerHTML=''; this.textContent='';
  this.className=''; this.style={}; this.dataset={}; this.disabled=false; this._h={}; }
El.prototype.addEventListener=function(e,f){ this._h[e]=f; };
El.prototype.insertAdjacentHTML=function(p,h){ this.innerHTML+=h; };
El.prototype.querySelector=function(s){ return mkEl(this.id+'::'+s); };
El.prototype.querySelectorAll=function(){ return []; };
El.prototype.classList={add:function(){},remove:function(){},toggle:function(){},contains:function(){return true;}};
El.prototype.requestSubmit=function(){};
El.prototype.reset=function(){ this.value=''; };
El.prototype.closest=function(){ return null; };
function mkEl(id){ return __els[id] || (__els[id]=new El(id)); }

global.document = {
  getElementById: function(id){ return mkEl(id); },
  querySelector: function(s){ return mkEl(s); },
  querySelectorAll: function(){ return []; },
  addEventListener: function(){},
};
global.window = { scrollTo: function(){}, location:{} };
global.confirm = function(){ return true; };
global.alert = function(){};
var __timers=[];
global.setInterval = function(fn){ __timers.push(fn); return 1; };

// ---- stub fetch ----
var __calls=[];
global.fetch = function(path, opt){
  __calls.push({path:path, method:(opt&&opt.method)||'GET', body:(opt&&opt.body)||null});
  var body;
  if(path.indexOf('/api/stats')===0) body = STATS;
  else if(path.indexOf('/api/customers')===0) body = CUSTOMERS;
  else if(path.indexOf('/api/contracts')===0) body = CONTRACTS;
  else body = {ok:true};
  return Promise.resolve({ status:200, json: function(){ return Promise.resolve(body); } });
};
"""

post = r"""
// ---- 断言 ----
(async function(){
  await new Promise(r=>setTimeout(r,0));
  await new Promise(r=>setImmediate(r));
  await new Promise(r=>setImmediate(r));
  var out = {};
  out.calls = __calls.map(c=>c.method+' '+c.path.split('?')[0]);
  out.statsCards = (mkEl('stats').innerHTML.match(/class="stat"/g)||[]).length;
  out.customerOptions = (mkEl('customer_id').innerHTML.match(/<option/g)||[]).length;
  out.customerRows = (mkEl('cuBody').innerHTML.match(/<tr>/g)||[]).length;
  out.contractRows = (mkEl('ctBody').innerHTML.match(/<tr>/g)||[]).length;
  out.salesmanOpts = (mkEl('salesman').innerHTML.match(/<option/g)||[]).length;
  out.statusOpts = (mkEl('status').innerHTML.match(/<option/g)||[]).length;
  out.currencyOpts = (mkEl('currency').innerHTML.match(/<option/g)||[]).length;
  out.liveText = mkEl('live').innerHTML.slice(0,120);
  out.hasContractNo = mkEl('ctBody').innerHTML.indexOf('HT-2026-001') >= 0;
  out.hasCustomerName = mkEl('ctBody').innerHTML.indexOf('PACIFIC RIM LLC') >= 0;
  out.hasEditBtn = mkEl('ctBody').innerHTML.indexOf('data-edit="1"') >= 0;
  out.latestRows = (mkEl('latestBody').innerHTML.match(/<tr>/g)||[]).length;
  out.emptyHidden = mkEl('ctEmpty').style.display;
  out.errors = mkEl('errbox').innerHTML.slice(0,500);
  out.noUndef = !/undefined|NaN/.test(mkEl('ctBody').innerHTML + mkEl('stats').innerHTML +
                                      mkEl('cuBody').innerHTML + mkEl('latestBody').innerHTML);
  try{
    await editContract(1);
    out.editFilled = [mkEl('contract_no').value, mkEl('amount').value, mkEl('status').value].join('|');
    out.editTitle = mkEl('ctFormTitle').textContent;
  }catch(e){ out.editFilled = 'ERR '+e.message; }
  require('fs').writeFileSync(process.env.OUT, JSON.stringify(out,null,1));
})().catch(function(e){
  require('fs').writeFileSync(process.env.OUT,
    JSON.stringify({FATAL:String(e && e.stack || e), errbox: mkEl('errbox').innerHTML.slice(0,500)}));
});
"""

harness = DATA_JS + pre + js + post
hp = BASE / "_fh.js"
hp.write_text(harness, encoding="utf-8")
outp = BASE / "_fh_out.json"
logp = BASE / "_fh.log"
env = dict(os.environ)
env["OUT"] = str(outp)
NODE = r"C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
with open(logp, "wb") as lg:
    r = subprocess.run([NODE, str(hp)], stdout=lg, stderr=lg, env=env, cwd=str(BASE))
print("node exit:", r.returncode)
log = logp.read_text(encoding="utf-8", errors="replace")
if log.strip():
    print("LOG:", log[:1500])
res = {}
if outp.exists():
    res = json.loads(outp.read_text(encoding="utf-8"))
    print(outp.read_text(encoding="utf-8"))

checks = [
    ("无异常", res.get("FATAL") is None, res.get("FATAL")),
    ("统计卡片 6 张", res.get("statsCards") == 6, res.get("statsCards")),
    ("客户下拉已填充", res.get("customerOptions") == 3, res.get("customerOptions")),
    ("客户表 2 行", res.get("customerRows") == 2, res.get("customerRows")),
    ("合同表 2 行", res.get("contractRows") == 2, res.get("contractRows")),
    ("业务员选项已填充", res.get("salesmanOpts") == 4, res.get("salesmanOpts")),
    ("状态选项已填充", res.get("statusOpts") == 4, res.get("statusOpts")),
    ("币种选项已填充", res.get("currencyOpts") == 3, res.get("currencyOpts")),
    ("合同号渲染", res.get("hasContractNo") is True, ""),
    ("客户名渲染", res.get("hasCustomerName") is True, ""),
    ("编辑按钮带 id", res.get("hasEditBtn") is True, ""),
    ("最近合同 2 行", res.get("latestRows") == 2, res.get("latestRows")),
    ("列表非空时隐藏空态", res.get("emptyHidden") == "none", res.get("emptyHidden")),
    ("无 undefined/NaN", res.get("noUndef") is True, ""),
    ("编辑回填正确", res.get("editFilled") == "HT-2026-001|125000.5|执行中", res.get("editFilled")),
    ("编辑标题切换", str(res.get("editTitle", "")).startswith("编辑合同"), res.get("editTitle")),
    ("启动调用了 3 个加载接口",
     sorted(set(x for x in res.get("calls", []) if x.startswith("GET"))) ==
     ["GET /api/contracts", "GET /api/customers", "GET /api/stats"], res.get("calls")),
]
bad = [c for c in checks if not c[1]]
print("=" * 50)
for n, ok, extra in checks:
    print(("PASS " if ok else "FAIL ") + n + (("  | " + str(extra)) if extra else ""))
print(f"总计 {len(checks)} 项，通过 {len(checks)-len(bad)}，失败 {len(bad)}")

for f in (hp, outp, logp):
    Path(f).unlink(missing_ok=True)
