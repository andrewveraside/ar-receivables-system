# -*- coding: utf-8 -*-
"""
合同管理系统 · 本地服务（零第三方依赖，仅标准库）
- SQLite 存储 → data/contracts.db
- 提供录入/查询/编辑/删除 API + 调用看板
- 启动：双击 启动合同系统.bat，或命令行 python server.py
"""
import json
import os
import re
import sqlite3
import sys
import datetime as dt
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent

# 控制台强制 UTF-8（bat 里已 chcp 65001，这里再兜一层，避免重定向时中文变乱码）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
DB_PATH = BASE / "data" / "contracts.db"
WEB_DIR = BASE / "web"
PORT = int(os.environ.get("CONTRACT_PORT", "8765"))

# ---------------- 数据库 ----------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS customer (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  code        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  country     TEXT,
  currency    TEXT DEFAULT 'USD',
  pay_days    INTEGER DEFAULT 30,
  credit_limit REAL DEFAULT 0,
  salesman    TEXT,
  contact     TEXT,
  email       TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contract (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_no  TEXT NOT NULL UNIQUE,
  customer_id  INTEGER NOT NULL REFERENCES customer(id),
  sign_date    TEXT NOT NULL,
  start_date   TEXT,
  end_date     TEXT,
  currency     TEXT NOT NULL DEFAULT 'USD',
  amount       REAL NOT NULL DEFAULT 0,
  pay_term     TEXT,
  trade_term   TEXT,
  status       TEXT NOT NULL DEFAULT '执行中',
  salesman     TEXT,
  remark       TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contract_customer ON contract(customer_id);
CREATE INDEX IF NOT EXISTS idx_contract_status ON contract(status);

CREATE TABLE IF NOT EXISTS change_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,
  row_id     INTEGER NOT NULL,
  action     TEXT NOT NULL,
  detail     TEXT,
  at         TEXT NOT NULL
);
"""

CUR = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "KRW", "SEK", "CNY"]
STATUS = ["草签", "执行中", "已完结", "已作废"]
SALESMEN = ["周小杰", "刘小源", "张大丽"]


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as c:
        c.executescript(SCHEMA)
        # 首次运行灌入示例客户，避免空库难用
        n = c.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
        if n == 0:
            seed = [
                ("C001", "HANSA TRADING GmbH", "德国", "EUR", 30, 800000, "周小杰", "Hans Weber", "h.weber@hansa.example"),
                ("C002", "NORDIC HOME AB", "瑞典", "SEK", 30, 600000, "刘小源", "Lars Nilsson", "lars@nordichome.example"),
                ("C008", "PACIFIC RIM LLC", "美国", "USD", 60, 1500000, "张大丽", "Mike Chen", "mike@pacrim.example"),
            ]
            c.executemany(
                """INSERT INTO customer(code,name,country,currency,pay_days,credit_limit,salesman,contact,email,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                [s + (now(),) for s in seed])
    return DB_PATH


def log_change(conn, table, row_id, action, detail=""):
    conn.execute("INSERT INTO change_log(table_name,row_id,action,detail,at) VALUES(?,?,?,?,?)",
                 (table, row_id, action, detail, now()))


# ---------------- 校验 ----------------

def bad(msg):
    return {"ok": False, "error": msg}


def norm_str(v, maxlen=200):
    s = ("" if v is None else str(v)).strip()
    return s[:maxlen]


def norm_date(v, field, required=False):
    s = norm_str(v, 10)
    if not s:
        if required:
            raise ValueError(f"{field} 必填")
        return ""
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s)
    if not m:
        raise ValueError(f"{field} 格式应为 YYYY-MM-DD，收到 {s!r}")
    y, mo, d = map(int, m.groups())
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        raise ValueError(f"{field} 不是有效日期：{s}")


def norm_amount(v):
    s = norm_str(v, 30).replace(",", "").replace("，", "")
    if not s:
        return 0.0
    try:
        x = float(s)
    except ValueError:
        raise ValueError(f"金额必须是数字，收到 {s!r}")
    if x < 0:
        raise ValueError("金额不能为负")
    if x > 1e13:
        raise ValueError("金额过大")
    return round(x, 2)


# ---------------- 业务逻辑 ----------------

def list_customers():
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM customer ORDER BY code")]
    return {"ok": True, "data": rows}


def save_customer(p):
    code = norm_str(p.get("code"), 20).upper()
    name = norm_str(p.get("name"))
    if not code or not name:
        return bad("客户代码、客户名称必填")
    ccy = norm_str(p.get("currency"), 8).upper() or "USD"
    if ccy not in CUR:
        return bad(f"币种不在允许列表：{ccy}")
    try:
        pay = int(p.get("pay_days") or 0)
        if not (0 <= pay <= 365):
            raise ValueError
    except (ValueError, TypeError):
        return bad("账期天必须是 0~365 的整数")
    cl = norm_amount(p.get("credit_limit"))
    sm = norm_str(p.get("salesman"), 20)
    if sm and sm not in SALESMEN:
        return bad(f"业务员只允许 {'/'.join(SALESMEN)}")
    row = (code, name, norm_str(p.get("country"), 40), ccy, pay, cl, sm,
           norm_str(p.get("contact"), 60), norm_str(p.get("email"), 80))
    with connect() as c:
        ex = c.execute("SELECT id FROM customer WHERE code=?", (code,)).fetchone()
        if ex:
            c.execute("""UPDATE customer SET name=?,country=?,currency=?,pay_days=?,
                         credit_limit=?,salesman=?,contact=?,email=? WHERE id=?""",
                      row[1:] + (ex["id"],))
            log_change(c, "customer", ex["id"], "UPDATE", code)
            rid = ex["id"]
        else:
            cur = c.execute("""INSERT INTO customer(code,name,country,currency,pay_days,
                               credit_limit,salesman,contact,email,created_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?)""", row + (now(),))
            rid = cur.lastrowid
            log_change(c, "customer", rid, "INSERT", code)
    return {"ok": True, "id": rid}


def list_contracts(q=""):
    sql = """SELECT ct.*, cu.name AS customer_name, cu.code AS customer_code, cu.country
             FROM contract ct JOIN customer cu ON cu.id=ct.customer_id"""
    args = []
    if q:
        sql += """ WHERE ct.contract_no LIKE ? OR cu.name LIKE ? OR ct.salesman LIKE ?"""
        k = f"%{q}%"
        args = [k, k, k]
    sql += " ORDER BY ct.sign_date DESC, ct.id DESC LIMIT 500"
    with connect() as c:
        rows = [dict(r) for r in c.execute(sql, args)]
    return {"ok": True, "data": rows}


def save_contract(p):
    no = norm_str(p.get("contract_no"), 40).upper()
    if not no:
        return bad("合同号必填")
    if not re.match(r"^[A-Z0-9\-_/]{3,40}$", no):
        return bad("合同号只允许字母数字和 - _ /，至少 3 位")
    try:
        cid = int(p.get("customer_id") or 0)
    except (TypeError, ValueError):
        return bad("请选择客户")
    if cid <= 0:
        return bad("请选择客户")
    try:
        sign = norm_date(p.get("sign_date"), "签订日期", required=True)
        start = norm_date(p.get("start_date"), "生效日期")
        end = norm_date(p.get("end_date"), "到期日期")
        amt = norm_amount(p.get("amount"))
    except ValueError as e:
        return bad(str(e))
    if start and end and end < start:
        return bad("到期日期不能早于生效日期")
    ccy = norm_str(p.get("currency"), 8).upper() or "USD"
    if ccy not in CUR:
        return bad(f"币种不在允许列表：{ccy}")
    st = norm_str(p.get("status"), 10) or "执行中"
    if st not in STATUS:
        return bad(f"状态必须为 {'/'.join(STATUS)}")
    sm = norm_str(p.get("salesman"), 20)
    if sm and sm not in SALESMEN:
        return bad(f"业务员只允许 {'/'.join(SALESMEN)}")

    vals = (no, cid, sign, start, end, ccy, amt, norm_str(p.get("pay_term"), 60),
            norm_str(p.get("trade_term"), 20), st, sm, norm_str(p.get("remark"), 500))
    with connect() as c:
        if not c.execute("SELECT id FROM customer WHERE id=?", (cid,)).fetchone():
            return bad("客户不存在")
        dup = c.execute("SELECT id FROM contract WHERE contract_no=?", (no,)).fetchone()
        rid = int(p.get("id") or 0)
        if dup and rid and dup["id"] != rid:
            return bad(f"合同号 {no} 已被其他记录占用")
        if dup and not rid:
            return bad(f"合同号 {no} 已存在")
        if rid:
            c.execute("""UPDATE contract SET contract_no=?,customer_id=?,sign_date=?,
                         start_date=?,end_date=?,currency=?,amount=?,pay_term=?,trade_term=?,
                         status=?,salesman=?,remark=?,updated_at=? WHERE id=?""",
                      vals + (now(), rid))
            log_change(c, "contract", rid, "UPDATE", no)
        else:
            cur = c.execute("""INSERT INTO contract(contract_no,customer_id,sign_date,start_date,
                               end_date,currency,amount,pay_term,trade_term,status,salesman,remark,
                               created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            vals + (now(), now()))
            rid = cur.lastrowid
            log_change(c, "contract", rid, "INSERT", no)
    return {"ok": True, "id": rid}


def delete_contract(cid):
    with connect() as c:
        row = c.execute("SELECT contract_no FROM contract WHERE id=?", (cid,)).fetchone()
        if not row:
            return bad("记录不存在")
        c.execute("DELETE FROM contract WHERE id=?", (cid,))
        log_change(c, "contract", cid, "DELETE", row["contract_no"])
    return {"ok": True}


def stats():
    with connect() as c:
        nc = c.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
        ct = c.execute("SELECT COUNT(*) FROM contract").fetchone()[0]
        by = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM contract GROUP BY status")}
        amt = c.execute("SELECT COALESCE(SUM(amount),0) FROM contract").fetchone()[0]
        latest = [dict(r) for r in c.execute(
            """SELECT ct.contract_no, cu.name customer_name, ct.amount, ct.currency,
                      ct.sign_date, ct.status FROM contract ct JOIN customer cu
                      ON cu.id=ct.customer_id ORDER BY ct.id DESC LIMIT 5""")]
    return {"ok": True, "customers": nc, "contracts": ct, "by_status": by,
            "total_amount": round(amt, 2), "latest": latest,
            "options": {"currencies": CUR, "statuses": STATUS, "salesmen": SALESMEN}}


# ---------------- 看板数据源同步 ----------------
# 合同库 → data/ar_bridge.js/.json → 看板。任何写操作后触发，失败不影响录入。
DASHBOARD_HTML = BASE / "应收账款看板_合同库版_离线版.html"


def build_dashboard_html():
    """同进程执行 build_dashboard.py 生成看板 HTML（不走 subprocess，避开管道限制）。"""
    path = BASE / "build_dashboard.py"
    if not path.exists():
        return False, "找不到 build_dashboard.py"
    src = path.read_text(encoding="utf-8")
    old_argv = sys.argv[:]
    sys.argv = [str(path), "--source=bridge"]
    g = {"__name__": "__main__", "__file__": str(path), "__builtins__": __builtins__}
    try:
        exec(compile(src, str(path), "exec"), g)
        return True, "看板已生成"
    except SystemExit as e:
        return e.code in (0, None), "build_dashboard 退出 %s" % (e.code,)
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)
    finally:
        sys.argv = old_argv


def sync_dashboard(rebuild=False):
    """调用 bridge.py 增量同步，可选顺带重建看板 HTML。返回 (ok, msg)。"""
    try:
        sys.path.insert(0, str(BASE))
        import importlib
        import bridge
        importlib.reload(bridge)
        payload = bridge.build()
        s = bridge.sig(payload)
        changed = True
        if bridge.STATE.exists():
            try:
                old = json.loads(bridge.STATE.read_text(encoding="utf-8"))
                if old.get("sig") == s:
                    changed = False
            except Exception:
                pass
        if changed:
            bridge.write(payload)
        msg = f"{len(payload['rows'])} 笔应收" + ("" if changed else "（无变化）")
        if rebuild:
            ok, m = build_dashboard_html()
            if not ok:
                return False, msg + "；看板生成失败：" + m
        return True, msg
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ---------------- HTTP ----------------

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    server_version = "ContractServer/1.0"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (dt.datetime.now().strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _serve_file(self, rel):
        p = (WEB_DIR / rel).resolve()
        if not str(p).startswith(str(WEB_DIR.resolve())) or not p.is_file():
            return self._send(404, {"ok": False, "error": "文件不存在"})
        self._send(200, p.read_bytes(), MIME.get(p.suffix.lower(), "application/octet-stream"))

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path, qs = u.path, urllib.parse.parse_qs(u.query)
        try:
            if path in ("/", "/index.html"):
                return self._serve_file("index.html")
            if path.startswith("/web/"):
                return self._serve_file(path[5:])
            if path == "/api/health":
                return self._send(200, {"ok": True, "db": str(DB_PATH), "time": now()})
            if path == "/api/stats":
                return self._send(200, stats())
            if path == "/api/customers":
                return self._send(200, list_customers())
            if path == "/api/contracts":
                return self._send(200, list_contracts((qs.get("q") or [""])[0]))
            if path == "/api/export.json":
                with connect() as c:
                    data = {
                        "exported_at": now(),
                        "customers": [dict(r) for r in c.execute("SELECT * FROM customer")],
                        "contracts": [dict(r) for r in c.execute("SELECT * FROM contract")],
                    }
                return self._send(200, data)
            # ---- 内嵌看板 ----
            if path == "/dashboard/view":
                if not DASHBOARD_HTML.exists():
                    ok, m = sync_dashboard(rebuild=True)
                    if not ok:
                        return self._send(500, {"ok": False, "error": "看板生成失败：" + m})
                return self._send(200, DASHBOARD_HTML.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/dashboard/download":
                if not DASHBOARD_HTML.exists():
                    sync_dashboard(rebuild=True)
                if not DASHBOARD_HTML.exists():
                    return self._send(404, {"ok": False, "error": "看板尚未生成"})
                body = DASHBOARD_HTML.read_bytes()
                fname = urllib.parse.quote("应收账款看板.html")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Disposition",
                                 "attachment; filename=dashboard.html; filename*=UTF-8''" + fname)
                self.end_headers()
                self.wfile.write(body)
                return
            return self._send(404, {"ok": False, "error": "未知接口"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            p = self._json_body()
            if path == "/api/customers":
                r = save_customer(p)
                if r.get("ok"):
                    sync_dashboard()
                return self._send(200, r)
            if path == "/api/contracts":
                r = save_contract(p)
                if r.get("ok"):
                    sync_dashboard()
                return self._send(200, r)
            if path == "/api/sync-dashboard":
                ok, msg = sync_dashboard()
                return self._send(200 if ok else 500, {"ok": ok, "msg": msg})
            if path == "/api/rebuild-dashboard":
                ok, msg = sync_dashboard(rebuild=True)
                return self._send(200 if ok else 500, {"ok": ok, "msg": msg})
            return self._send(404, {"ok": False, "error": "未知接口"})
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "请求体不是合法 JSON"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        m = re.match(r"^/api/contracts/(\d+)$", path)
        try:
            if m:
                r = delete_contract(int(m.group(1)))
                if r.get("ok"):
                    sync_dashboard()
                return self._send(200, r)
            return self._send(404, {"ok": False, "error": "未知接口"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})


def main():
    init_db()
    ok, msg = sync_dashboard()
    print(f"  看板同步: {'成功' if ok else '失败'} · {msg}")

    # 端口被占用：直接说明，不要让用户看到一闪而过的 traceback
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        print()
        print("!" * 58)
        print(f"  启动失败：端口 {PORT} 已被占用。")
        print(f"  原因：{e}")
        print()
        print("  可能已有一个合同系统窗口在运行。处理方式（任选其一）：")
        print("    1) 关掉所有黑底「合同管理系统」窗口，再重新双击本 bat；")
        print("    2) 直接打开浏览器访问 http://127.0.0.1:%d/ 用现有服务；" % PORT)
        print("    3) 先用下面的命令找出占用进程再结束它：")
        print("       netstat -ano | findstr :%d" % PORT)
        print("!" * 58)
        sys.exit(2)

    url = f"http://127.0.0.1:{PORT}/"
    print("=" * 58)
    print("  合同管理系统 已启动")
    print(f"  地址: {url}")
    print(f"  数据库: {DB_PATH}")
    print("  关闭此窗口即停止服务（数据已存库，不会丢）")
    print("=" * 58)
    if os.environ.get("CONTRACT_NO_BROWSER") != "1":
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
