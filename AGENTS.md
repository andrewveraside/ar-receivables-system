# AGENTS.md — 应收账款系统 · AI 助手工作说明书

> 本文件给**所有接手本项目的 AI 助手**看。新会话第一件事：读这个文件 + `README.md`。
> 项目根目录 `D:\aiprojects\应收账款系统`。最后更新 2026-10-28。

---

## 0. 一句话

本地单机应收账款系统：Python 标准库后端 + 原生 HTML/JS 前端 + SQLite 存储 + ECharts 离线看板。
**零第三方依赖**（不用 pip install 任何东西）。启动 = 双击 `启动.bat`。

---

## 1. 动手前必做的三件事

1. **读 `README.md`** —— 目录结构、数据流、表结构、接口清单都在那。
2. **看懂数据流**（README 第三节那张图）：录入 → `contracts.db` → `bridge.py` → `data/ar_bridge.js` → `build_dashboard.py` → 看板 HTML。
3. **改之前先跑一遍 `python update_dashboard.py`** 确认当前状态正常，再动手。

---

## 2. 文件职责速查

| 文件 | 一句话职责 | 改了会影响谁 |
|---|---|---|
| `server.py` | HTTP 服务 + SQLite + 全部 REST 路由 | 前端所有页签、桥接触发 |
| `web/index.html` | 单页应用，5 个页签（总览/合同录入/客户管理/合同台账/应收看板） | 用户看到的全部交互 |
| `bridge.py` | 合同库 → 应收行 的转换（拆期、模拟回款、算逾期） | 看板上的每个数字 |
| `build_dashboard.py` | 读桥接 json → 渲染单文件 HTML 看板 | 看板外观和数据 |
| `update_dashboard.py` | 一键调 bridge + build_dashboard（同进程 exec） | 无 |
| `启动.bat` | 找 Python + 启服务 + 开浏览器 | 用户能不能用起来 |
| `gen_data.py` | 生成 100 条虚构示例数据 | 仅演示文件，与业务库无关 |
| `seed_contracts.py` | 往库里灌 6 条示范合同 | `contracts.db` |
| `test_*.py` | 5 个测试脚本（api / frontend / e2e / loop / sig） | 无 |
| `verify.py` | 复算看板数字核对 | 无 |

**改代码前先确定改的是哪一层**：
- 数字口径不对 → `bridge.py`（逾期/回款算法）或 `build_dashboard.py` 顶部（账龄分档）
- 页面不显示 → `web/index.html`
- 接口报错 → `server.py`
- 看板样式/图表 → `build_dashboard.py` 里的 HTML 模板字符串（第 81 行往后）
- 服务起不来 → `启动.bat`

---

## 3. 硬约束（违反会出线上级事故）

### 3.1 `.bat` 文件**禁止出现任何中文字符**

连 `REM` 注释里的中文都不行。实测事故：boss 双击 bat 后服务没起来，网页显示 `Failed to fetch`。
根因是 cmd.exe 按 GBK 逐字节解析，UTF-8 中文把行结构切碎了，`python server.py` 那行**根本没执行**。
`chcp 65001` 写在文件里无效（解析先于执行）。

→ 中文提示一律交给 Python `print`。新建任何 bat 都要检查：`[IO.File]::ReadAllLines(path)` 里有没有非 ASCII 行。

### 3.2 不要用 subprocess 调其他脚本

沙箱下 `subprocess.run(capture_output=True)` 会抛 `PermissionError: [WinError 5] 拒绝访问`。
用同进程 exec：

```python
def run_script(path, argv=()):
    src = Path(path).read_text(encoding="utf-8")
    old = sys.argv
    sys.argv = [str(path)] + list(argv)
    try:
        exec(compile(src, str(path), "exec"),
             {"__name__": "__main__", "__file__": str(path)})
    finally:
        sys.argv = old
```

`update_dashboard.py` 和 `server.py` 的 `build_dashboard_html()` 都是这个模式，照抄。

### 3.3 报表日期必须 `date.today()`，禁止硬编码

历史事故：`build_dashboard.py` 曾写死 `TODAY = 2026-10-27`，隔几天账龄档位全错。

### 3.4 模板占位符替换后必须 assert

`build_dashboard.py:424`：
```python
assert "__DATA__" not in html and "__PAYLOAD__" not in html, "占位符未替换干净"
```
历史事故：`__DATA__` 与 `__PAYLOAD__` 互为子串，替换互相污染 → 非法 JS → **整页白屏**。
新增任何占位符，替换后都要加断言。

### 3.5 不要删 `build_dashboard.py:381-391` 的 resize 补丁

```javascript
const resizeAll = () => { Object.values(charts).forEach(c => { try{ c.resize(); }catch(e){} }); };
window.addEventListener('resize', resizeAll);
if (window.ResizeObserver) { new ResizeObserver(() => resizeAll()).observe(document.body); }
[0, 60, 200, 600, 1500].forEach(t => setTimeout(resizeAll, t));
```
看板是以 iframe 内嵌的，首帧容器宽度为 0，没有这段图表就画不出来（用户会报「看板空白」）。

---

## 4. 验证怎么算「改完了」

**不做验证不算完成。** 按改动范围选：

| 改了什么 | 必须跑 |
|---|---|
| `bridge.py` / `build_dashboard.py` | `python update_dashboard.py`，看输出的 rows 数和 total_open_cny 是否合理 |
| `web/index.html` | `python test_frontend.py`（17 项） |
| `server.py` 接口 | `python test_api.py` + `python test_loop.py` |
| 数字口径 | `python verify.py` 复算核对 |
| 全流程 | `python test_e2e.py` |

前端改动**不能只跑 `node --check`**。正确做法（`test_frontend.py` 的套路）：抽 `<script>` 块，
stub `document` / `window` / `echarts`，在 node 里实跑，断言 `echarts.init` 次数、`setOption` 次数、
DOM innerHTML 长度、筛选后的聚合值。

bundled node：`C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe`，
**必须传完整 `os.environ`**，清空 PATH 会触发 `Assertion failed: ncrypto::CSPRNG(nullptr, 0)` 崩溃（exit 134）。

bundled python：`C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`

---

## 5. 关键设计决策（**别轻易推翻**）

| 决策 | 理由 | 推翻的代价 |
|---|---|---|
| **单向桥接**，看板不直连数据库 | 看板必须能 `file://` 双击打开、零依赖、发给别人看 | 一旦直连，离线分享能力就没了 |
| **同时输出 `.json` 和 `.js`** | `file://` 下浏览器禁止 fetch 本地 JSON（CORS），但 `<script>` 加载 `.js` 可以 | 只留 json，看板离线打开就白屏 |
| **ECharts 内嵌进 HTML**（1 MB） | 保证完全离线，不依赖 CDN | 改成 CDN 引用，断网就废 |
| **一期看板用公式不用透视表** | openpyxl 生成不了数据透视表缓存 | 只能手工刷新，不自动 |
| **服务端零第三方依赖** | 用户机器可能装不了包，也不想装 | 引入 Flask/pandas，部署成本上升 |
| **合同按币种拆 1–3 期** | 模拟真实分期发货/分期结汇，让账龄有分布 | 不拆的话看板只有几行，看不出账龄差异 |

---

## 6. 目前是**演示逻辑**、不是真实业务的地方

接手时注意，这些地方用户知道是假的，别当成 bug 去「修」：

1. **汇率写死**：`bridge.py:25-27` 的 `RATES`（USD 7.1085 等），固定近似值。
2. **回款是模拟的**：`bridge.py` 里「已完结=全额收回、草签=零回款、执行中按到期天数算部分回款」。
3. **拆期规则**：`bridge.py:30-31` 的 `SPLITS`，按币种定死。
4. **`gen_data.py` 和 `data/ar_data.json`**：100 条虚构数据，跟 `contracts.db` 完全无关，只是早期演示残留。
5. **`应收账款看板_离线版.html`**（不带「合同库版」的那个）：示例数据版看板，也是演示残留。

真正在用的数据源只有 `data/contracts.db`，真正在用的看板只有 `应收账款看板_合同库版_离线版.html`。

---

## 7. 用户偏好（当事人习惯）

- 要**能直接用**的成品：命令、脚本、配置整段给好，不要留占位符让人自己填。
- 结论先行，能用表格就用表格，不要铺垫。
- 对成本敏感，省 token：结构化数据（CSV/日志/JSON）不要整读，先 grep 或分段读，要算就写脚本只把结果读回来。
- 排障要让用户能**一眼看懂根因**，不要甩一堆日志。

---

## 8. 常见故障速查

| 现象 | 最可能的原因 | 怎么查 |
|---|---|---|
| 双击 bat 服务没起来 / 网页 `Failed to fetch` | bat 里有中文 | `[IO.File]::ReadAllLines("启动.bat")` 查非 ASCII 行 |
| 看板空白（有框架没内容） | 模板占位符污染 / iframe resize | 查 HTML 里有没有 `__DATA__` 残留；查有没有 resize 补丁 |
| 看板数字不更新 | 桥接没跑 | 跑 `python bridge.py --stats` 看变化，再 `update_dashboard.py` |
| 端口 8765 被占 | 有旧 python 进程没关 | `netstat -ano \| findstr :8765` 拿 PID，再 taskkill |
| 账龄档位全错 | 日期写死了 | 查 `build_dashboard.py` 顶部有没有 `date.today()` |
| `python` 命令无输出且 exit 49 | WindowsApps 商店版 python | 换 bundled 解释器 |
| 打开 HTML 是源码/乱码 | 缺 `<meta charset="utf-8">` | 检查模板头 |

---

## 9. 工作纪律

1. **小步改**：一次改一个点，改完立刻验证，不要攒一堆改动一起测。
2. **先备份**：动 `contracts.db` 之前先复制一份 `contracts.db.bak`。
3. **不假装**：没跑过的测试不要说通过，没读过的文件不要描述其内容。
4. **别乱加依赖**：这个项目最大的卖点就是零第三方依赖，除非用户明确要求，不要引入 Flask / pandas / jQuery。
5. **改完更新本文件**：如果改了架构、加了约束、踩了新坑，回写到第 3 节（硬约束）或第 5 节（设计决策）。
