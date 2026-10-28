# 应收账款合同录入 + 应收看板系统

单机、离线、零第三方依赖的应收账款管理系统。Python 标准库做后端，原生 HTML/JS + ECharts 做前端，
数据存本地 SQLite，一张页面管合同、一张看板管账龄。

- **项目根目录**：`D:\aiprojects\应收账款系统`
- **开发时间**：2026-10-27 ～ 10-28
- **运行环境**：Windows 10/11 + Python 3.12/3.13（只用标准库，无需 pip install）

---

## 一、30 秒上手

```
双击 启动.bat
  → 浏览器自动打开 http://127.0.0.1:8765
  → 5 个页签：总览 / 合同录入 / 客户管理 / 合同台账 / 应收看板
```

停止服务：关掉那个黑色命令行窗口，或任务管理器结束占用 8765 端口的 python 进程。

端口被占用的换法：`set CONTRACT_PORT=8770` 再启动，或改 `启动.bat` 里的端口变量。

---

## 二、目录结构

```
D:\aiprojects\应收账款系统\
├── 启动.bat                     启动服务并打开浏览器（纯 ASCII，勿加中文）
├── server.py                    HTTP 服务 + SQLite + 所有 REST 路由（539 行）
├── web\index.html               单页应用，5 个页签（含 iframe 内嵌看板）
│
├── bridge.py                    合同库 → 应收数据 转换层（单向桥接）
├── build_dashboard.py           生成看板 HTML（ECharts 内嵌，完全离线）
├── update_dashboard.py          一键同步+重建（同进程 exec，不走 subprocess）
├── update_dashboard.bat         上面那个的双击入口
│
├── gen_data.py                  生成 100 条虚构示例应收数据（仅演示用）
├── seed_contracts.py            灌 6 条示范合同进数据库（可重复运行，自动跳过）
├── echarts.min.js               ECharts 5.5.1，1 MB，内嵌进看板用
│
├── data\
│   ├── contracts.db             ★ 唯一真实数据源（SQLite）
│   ├── ar_bridge.json           桥接产物（看板读这个）
│   ├── ar_bridge.js             window.__AR_BRIDGE = {...}，file:// 下也能读
│   ├── _bridge_state.json       增量同步状态（合同签名，判断有无变化）
│   └── ar_data.json             100 条示例数据（演示用，与业务库无关）
│
├── 应收账款看板_合同库版_离线版.html   ★ 主力看板（读 contracts.db 数据）
├── 应收账款看板_离线版.html            示例 100 条版本的看板（演示用）
│
├── 数据源_应收账款台账_示例100条.xlsx  示例台账（openpyxl 生成，演示用）
│
├── test_api.py                  API 层测试
├── test_frontend.py             前端 17 项测试
├── test_e2e.py                  端到端测试
├── test_loop.py                 录入→同步→出看板→删除 闭环测试
├── verify.py                    解析 HTML 内嵌数据复算聚合，核对数字
│
├── _obsolete\                   废弃的旧 bat（含中文导致 cmd 解析崩溃的那几个）
└── AGENTS.md                    ★ 给 AI 助手看的技术说明书（新会话先读这个）
```

---

## 三、数据流（**改代码前务必看懂这一段**）

```
                    ┌──────────────────────────────┐
     用户在浏览器   │  web/index.html（5 个页签）    │
       填表   ────► │  合同录入 / 客户管理 / 台账    │
                    └──────────────┬───────────────┘
                                   │ POST /api/contracts
                                   ▼
                    ┌──────────────────────────────┐
                    │  server.py                    │
                    │  save_contract() 写库         │
                    │        ↓                      │
                    │  sync_dashboard() 自动触发     │
                    └──────────────┬───────────────┘
                                   │ 同进程 exec
                                   ▼
                    ┌──────────────────────────────┐
                    │  bridge.py                    │
                    │  contracts.db → 应收行         │
                    │  按币种拆 1–3 期、模拟回款      │
                    └──────────────┬───────────────┘
                                   │
                      data/ar_bridge.json / .js
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  build_dashboard.py           │
                    │  读 json → 渲染 HTML 模板      │
                    │  内嵌 echarts.min.js + 数据    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
              应收账款看板_合同库版_离线版.html（1 MB 单文件）
              → file:// 双击可开、可离线分发、可 iframe 内嵌
```

**为什么是单向桥接，不让看板直连数据库？**
看板必须保持「双击即开、零依赖、能发给别人看」。直连 SQLite 就需要后端，离线分享就废了。
所以库是唯一真源，看板是快照；改动数据后重新生成快照即可。

**看板数据为什么不 fetch JSON？**
`file://` 协议下浏览器禁止 fetch 本地 JSON（CORS），所以同时输出一份 `.js`，
内容是 `window.__AR_BRIDGE = {...}`，用 `<script>` 加载不受限制。

---

## 四、数据库表结构

三张表，全部在 `data/contracts.db`。

### customer（客户）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| code | TEXT UNIQUE | 客户代码，如 C001 |
| name | TEXT | 客户全称 |
| country | TEXT | 国家 |
| currency | TEXT | 默认结算币种，如 EUR |
| pay_days | INTEGER | 默认账期天数（30/45/60/90/120） |
| credit_limit | REAL | 信用额度 |
| salesman | TEXT | 业务员：周小杰 / 刘小源 / 张大丽 |
| contact / email | TEXT | 联系人 / 邮箱 |
| created_at | TEXT | 创建时间 |

### contract（合同）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| contract_no | TEXT UNIQUE | 合同号，如 HT-2026-001 |
| customer_id | INTEGER FK | 关联 customer.id |
| sign_date | TEXT | 签订日期 yyyy-mm-dd |
| start_date / end_date | TEXT | 生效 / 失效日期 |
| currency | TEXT | 结算币种 |
| amount | REAL | 合同金额（**原币**） |
| pay_term | TEXT | 付款条件文本 |
| trade_term | TEXT | 贸易术语，如 FOB / CIF |
| status | TEXT | 草签 / 执行中 / 已完结 / 已作废 |
| salesman | TEXT | 业务员（可覆盖客户默认） |
| remark | TEXT | 备注 |
| created_at / updated_at | TEXT | 时间戳 |

### change_log（变更留痕）

`table_name` / `row_id` / `action` / `detail` / `at`，所有增删改都记一条。

**枚举值**（定义在 `server.py:78-80`，改这里就能扩）：
- 币种：`USD EUR GBP JPY AUD CAD SGD KRW SEK CNY`
- 状态：`草签 执行中 已完结 已作废`
- 业务员：`周小杰 刘小源 张大丽`

---

## 五、REST 接口

服务地址 `http://127.0.0.1:8765`。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/` | 返回 `web/index.html` |
| GET | `/web/*` | 静态资源 |
| GET | `/api/health` | 健康检查，返回库路径和时间 |
| GET | `/api/stats` | 总览统计（合同数、金额、状态分布） |
| GET | `/api/customers` | 客户列表 |
| GET | `/api/contracts?q=` | 合同列表，`q` 支持模糊搜索 |
| GET | `/api/export.json` | 全库导出 JSON（客户+合同） |
| POST | `/api/customers` | 新增/更新客户 → 自动同步看板 |
| POST | `/api/contracts` | 新增/更新合同 → 自动同步看板 |
| DELETE | `/api/contracts/{id}` | 删除合同 → 自动同步看板 |
| POST | `/api/sync-dashboard` | 手动增量同步（不重建 HTML） |
| POST | `/api/rebuild-dashboard` | 全量重建看板 HTML |
| GET | `/dashboard/view` | 看板 HTML 内嵌视图（iframe 用），不存在则自动生成 |
| GET | `/api/dashboard/download` | 下载看板 HTML 文件 |

写接口全部返回 `{"ok": true/false, ...}`；出错返回 500 + `{"ok": false, "error": "..."}`。

---

## 六、看板功能

`应收账款看板_合同库版_离线版.html`，深色主题，单文件 1 MB（ECharts 已内嵌）。

**筛选器（顶部 5 个下拉）**：客户 / 业务员 / 币种 / 账龄档 / 状态

**KPI 卡（6 张）**：应收总额、逾期总额、逾期占比、超 90 天、合同数、客户数

**图表（5 个）**：
1. 账龄分布柱状图（未到期 / 1-30 / 31-60 / 61-90 / 91-180 / 180 天以上）
2. 客户 Top10 未收余额条形图
3. 逾期趋势堆叠柱状图
4. 币种构成环形图
5. 客户 × 账龄热力矩阵

**联动**：点柱状图某一档 → 自动筛选该账龄档；点客户条形 → 自动筛选该客户。

**数据来源标注**：顶部会显示「合同库驱动 · N 份合同 · 生成于 时间」或「示例数据 N 条」。
`file://` 打开时隐藏「返回合同录入」按钮（没有后端，点了也没用）。

**账龄口径**（`build_dashboard.py:34-43`）：
以 `date.today()` 为基准，`逾期天数 = max(0, 今天 - 到期日)`，
`未收金额 = 不含税金额 - 已收金额`，`本位币金额 = 未收金额 × 汇率`。
分档：未到期 / 1-30 / 31-60 / 61-90 / 91-180 / 180 天以上。

---

## 七、常用命令

所有命令在项目根目录执行。Python 用 bundled 解释器最稳：

```bat
set PY=C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe

:: 重新生成看板（读合同库）
%PY% update_dashboard.py

:: 只同步桥接数据，不重建 HTML
%PY% bridge.py

:: 全量重建桥接数据
%PY% bridge.py --rebuild

:: 只看桥接统计，不写文件
%PY% bridge.py --stats

:: 灌示范合同
%PY% seed_contracts.py

:: 跑测试
%PY% test_loop.py        :: 闭环测试（会临时起服务，端口 8769）
%PY% test_frontend.py    :: 前端 17 项
%PY% test_api.py         :: API 层
%PY% verify.py           :: 复算看板数字
```

---

## 八、坑与约定（**改代码前必读，都是真踩过的**）

### 1. `.bat` 文件绝对不能有中文 —— 连 REM 注释里都不行

**这是踩得最惨的一个。** cmd.exe 按系统代码页（GBK）逐字节解析 `.bat`，UTF-8 中文被切成
半个字符后行结构崩坏，报 `'xxx' is not recognized as an internal or external command`，
**真正的命令（python server.py）根本不执行**，表现为「双击了 bat 但服务没起来」，
网页上就是 `Failed to fetch` / `无法连接后端服务`。

`chcp 65001` 写在文件里也救不了，因为解析发生在执行之前。

**约定**：所有 `.bat` 纯 ASCII，中文提示交给 Python 脚本 `print`。
启动脚本要做多路径找 Python（bundled → `D:\py\python3.13.1` → 常见路径 → `where python`），
失败要 `pause` 别闪退。

### 2. 沙箱里不能用 subprocess

在受限沙箱下，`subprocess.run(..., capture_output=True)` 会抛
`PermissionError: [WinError 5] 拒绝访问`（CreatePipe 被封）。
所以 `update_dashboard.py` 和 `server.py` 调用其他脚本一律用**同进程 exec**：

```python
src = (BASE / "bridge.py").read_text(encoding="utf-8")
exec(compile(src, "bridge.py", "exec"), {"__name__": "__main__", "__file__": str(BASE / "bridge.py")})
```

### 3. 报表日期禁止硬编码

`build_dashboard.py` 里必须用 `TODAY = dt.date.today()`。早期版本硬编码了
`TODAY = 2026-10-27`，隔几天账龄档位就全错。

### 4. 模板占位符替换后必须 assert

`build_dashboard.py:424` 有这一行，别删：

```python
assert "__DATA__" not in html and "__PAYLOAD__" not in html, "占位符未替换干净"
```

历史事故：旧模板里 `__DATA__` 和 `__PAYLOAD__` 互为子串，先替换 `__DATA__`
污染了 `const PAYLOAD=` 那行，产出非法 JS，**整页白屏**（用户反馈「什么数据都没有」）。
修法是保证两处占位独立 + 替换后断言清空。

### 5. 前端改了必须实跑，不能只跑语法检查

`node --check` 通过不代表能跑。正确做法（`test_frontend.py` 就是这么干的）：
抽出 `<script>` 块，stub 掉 `document` / `window` / `echarts`，在 node 里实跑，
断言 `echarts.init` 被调用 5 次、`setOption` 次数、DOM innerHTML 长度、筛选后的聚合值。
bundled node 在 `C:\Users\23171\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe`，
启动时**必须传完整环境变量**，清空 PATH 会触发 `Assertion failed: ncrypto::CSPRNG(nullptr, 0)` 崩溃。

### 6. 看板初始化不要用 setTimeout(..., 0)

用 `document.readyState === 'loading' ? addEventListener('DOMContentLoaded', init) : init()`。
在 iframe 里用 setTimeout 会踩到容器宽度为 0 的时机，图表画不出来。
另外 `build_dashboard.py:381-391` 有一段 resize 补丁（ResizeObserver + 多档延时 resize），
专门解决 iframe 内首帧尺寸为 0 的问题，改布局时别删。

### 7. 汇率是写死的近似值

`bridge.py:25-27` 的 `RATES` 和 `build_dashboard.py` 用同一套固定汇率（USD 7.1085 等），
**仅演示用**。接真实业务要换成取数接口或每日汇率表。

### 8. 合同拆期规则

`bridge.py:30-31` 的 `SPLITS` 按币种把合同额拆成 1–3 期应收（模拟分期发货/结汇）。
回款是**模拟**的：已完结 = 全额收回，草签 = 零回款，执行中按到期天数算部分回款。
这是演示逻辑，不是真实账务。

### 9. 端口冲突

`ThreadingHTTPServer` 在 8765 被占时抛 `[WinError 10013]`。`server.py` 已捕获并友好提示
三条出路（关旧窗口 / 直接用现有服务 / `netstat -ano | findstr :8765` 查 PID），然后 `sys.exit(2)`。

### 10. `python` 命令可能静默失败

系统 PATH 里的 python（WindowsApps 商店版）在受限 shell 里跑 `python -c` 会
**静默 exit 49 且无输出**（但 `python -V` 正常）。一律用 bundled 解释器，或 `启动.bat` 里找路径的逻辑。

---

## 九、历史沿革

| 时间 | 事件 |
|---|---|
| 2026-10-27 上午 | 从 0 做起：先做 100 条虚构数据的 Excel 台账 + HTML 账龄看板（`gen_data.py` / `数据源_应收账款台账_示例100条.xlsx` / `应收账款看板_离线版.html`） |
| 2026-10-27 下午 | 加前端录入界面 + SQLite 存储（`server.py` / `web/index.html`） |
| 2026-10-27 傍晚 | 打通合同库 → 看板（`bridge.py` / `build_dashboard.py --source=bridge` / `update_dashboard.py`） |
| 2026-10-27 晚 | 修 `.bat` 中文崩溃问题，`启动.bat` 重写为纯 ASCII |
| 2026-10-27 深夜 | 录入与看板合并为单页 5 页签（iframe 内嵌） |
| 2026-10-28 | 从 `E:\文档\deepseek-harness\default-workspace\ar-dashboard` 迁移到 `D:\aiprojects\应收账款系统` |
| 2026-10-28 | 修看板 iframe 白屏（resize 补丁），补本文档与 `AGENTS.md` |

E 盘原目录 `E:\文档\deepseek-harness\default-workspace\ar-dashboard` 保留作备份，可删。

---

## 十、给新会话的 AI 助手

先读 `AGENTS.md`（同目录），那里是浓缩版技术说明 + 操作约定。
本文档讲「是什么」，`AGENTS.md` 讲「改的时候注意什么」。
