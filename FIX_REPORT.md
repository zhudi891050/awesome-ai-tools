# 🔧 GEO系统 · 审计修复报告

修复日期：2026-05-20 | 基于审计报告 AUDIT_REPORT.md

---

## 修复概览

| # | 严重度 | 问题 | 文件 | 状态 |
|---|--------|------|------|------|
| 1 | 🔴 高 | 腾讯元宝API缺少TC3签名认证 | tracker/engines/yuanbao.py | ✅ 已修复 |
| 2 | 🔴 高 | config.yaml `${VAR}` 未做环境变量替换 | 新增 config_loader.py | ✅ 已修复 |
| 3 | 🟡 中 | tracker引擎遍历不一致（可用vs全部） | tracker/tracker.py | ✅ 已修复 |
| 4 | 🟡 中 | 追踪引擎串行执行浪费等待时间 | tracker/tracker.py | ✅ 已并行化 |
| 5 | 🟡 中 | asyncio.gather 无错误隔离 | content/adapter.py | ✅ 已修复 |
| 6 | 🟡 中 | 日报引擎权重硬编码 | reporter/report_generator.py | ✅ 动态读取 |
| 7 | 🟡 中 | 知乎发布器headless硬编码False | publisher/zhihu.py + config.yaml | ✅ 配置化 |
| 8 | 🟢 低 | _fill_prompt正则误删花括号 | content/generator.py | ✅ 已修复 |
| 9 | 🟢 低 | 内容生成串行+asyncio.sleep(1) | content/generator.py | ✅ 并行+信号量 |

### 额外发现

| # | 发现 | 说明 |
|---|------|------|
| A | 百度文心接口已正确实现 | 审计标记为"需修复"不准确，baidu_ernie.py 早已覆盖 query() 实现 OAuth2 token 认证，无需修改 |
| B | main.py L132/L154 "截断" 是 read_file 显示 artifact | 实际代码语法正确（ast.parse 验证通过），审计报告已更新 |

---

## 详细修复内容

### Fix 1: 腾讯元宝 TC3-HMAC-SHA256 签名认证

**文件**: `tracker/engines/yuanbao.py` (重写, 17行 → 130行)

**问题**: 原代码仅继承基类，基类发送 `Bearer {api_key}` 的方式不适用腾讯云API。腾讯混元需要 TC3-HMAC-SHA256 签名认证。

**修复**:
- 实现完整的 TC3-V3 签名算法（规范请求串 → 待签字符串 → HMAC-SHA256签名 → Authorization头）
- 添加 `secret_key` 读取（`HUNYUAN_SECRET_KEY` 环境变量）
- 覆盖 `query()` 方法：构造签名 → POST到 `hunyuan.tencentcloudapi.com` → 解析 `Response.Choices`
- 错误处理：检查 `Response.Error` 字段

**配置需求**: 需在 config.yaml 补充 `region` 和 `version` 字段（已设置默认值 `ap-guangzhou` / `2023-09-01`）

---

### Fix 2: config.yaml `${VAR}` 环境变量替换

**新增文件**: `config_loader.py`

**问题**: config.yaml 中的 `${DEEPSEEK_API_KEY}` 等占位符只是纯文本字符串，虽然各模块代码中直接通过 `os.environ.get()` 读取了环境变量，但配置中的值仍为无效的 `${...}` 文本。

**修复**:
- 创建 `config_loader.py` 作为统一配置入口
- 实现 `_resolve_env_vars()` 递归函数：遍历 dict/list/str，将 `${VAR}` 和 `${VAR:-default}` 替换为环境变量值
- 支持配置缓存（`_config_cache`），避免重复加载
- 提供 `load_config()` 和 `get_config()` 两个接口

**受影响的文件**（已全部更新）:
- `main.py` — `load_config()` 改为调用 config_loader
- `content/generator.py` — `__init__` 使用 config_loader
- `tracker/tracker.py` — `__init__` 使用 config_loader

---

### Fix 3+4: tracker 引擎过滤 + 并行化

**文件**: `tracker/tracker.py` 的 `run_daily_tracking()` 方法

**问题**:
1. 方法内有 `_get_available_engines()` 但实际遍历的是 `self.engines`（全部引擎），逻辑不一致
2. 6个引擎串行执行（for循环），总耗时 = 6 × 5次查询 × ~3s = 90s

**修复**:
- 有API Key时只遍历可用引擎；无API Key时遍历全部（mock模式）
- `asyncio.gather(*tasks, return_exceptions=True)` 并行执行所有引擎
- 每个引擎独立容错——一个引擎失败不影响其他引擎收集数据
- 总耗时降为：max(单引擎耗时) ≈ 15s（6倍提速）

---

### Fix 5: adapter asyncio.gather 错误隔离

**文件**: `content/adapter.py` 的 `adapt_and_assign()` 方法

**修复**: 添加 `return_exceptions=True` + Exception类型检查，一个平台的适配失败不再导致其他平台丢失结果。

---

### Fix 6: 日报引擎权重动态读取

**文件**: `reporter/report_generator.py` 的 `_render_engine_status()` 方法

**问题**: 6个引擎的权重硬编码在列表中，与 config.yaml 可能不同步。

**修复**: 从 `self.config["engines"]` 动态读取引擎名和权重。

---

### Fix 7: 知乎发布器 headless 配置化

**文件**: `publisher/zhihu.py` + `config.yaml`

**问题**: `headless=False` 硬编码，生产环境应使用无头模式。

**修复**:
- 添加 `self._headless` 属性，从配置读取（默认 `True`）
- 配置项: `publishers.zhihu.headless: true`
- 首次登录扫码时设为 `false`，之后切回 `true`

---

### Fix 8: _fill_prompt 正则应精确化

**文件**: `content/generator.py` 的 `_fill_prompt()` 方法

**问题**: `re.sub(r"\{[^}]*\}", "", template)` 匹配任何花括号内容，可能误删 JSON-LD 等非变量内容。

**修复**: `re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", "", template)` — 只匹配合法变量名格式的 `{var_name}`。

---

### Fix 9: 内容生成并行化 + 信号量限流

**文件**: `content/generator.py` 的 `generate_daily_batch()` 方法

**问题**: 8篇文章串行生成（`await ... + await asyncio.sleep(1)`），总耗时 = 8 × (5s API + 1s 间隔) = 48s

**修复**:
- `asyncio.Semaphore(3)` 限制最多3个并发API调用
- `asyncio.gather(*tasks, return_exceptions=True)` 并行执行
- 总耗时降为：ceil(8/3) × 5s ≈ 15s（3倍提速）
- 单个文章失败不影响其他文章

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `config_loader.py` | **新增** | 统一配置加载 + ${VAR}环境变量替换 |
| `main.py` | 修改 | load_config() 改用 config_loader |
| `content/generator.py` | 修改 | config加载 + 正则修复 + 并行化 |
| `content/adapter.py` | 修改 | asyncio.gather 错误隔离 |
| `tracker/tracker.py` | 修改 | config加载 + 引擎过滤 + 并行化 |
| `tracker/engines/yuanbao.py` | **重写** | TC3签名认证完整实现 |
| `reporter/report_generator.py` | 修改 | 引擎权重动态读取 |
| `publisher/zhihu.py` | 修改 | headless配置化 |
| `config.yaml` | 修改 | 添加 zhihu.headless 配置 |
| `AUDIT_REPORT.md` | 修改 | 更正2处误报 |

---

## 性能提升

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| 追踪耗时（6引擎×5查询） | ~90s (串行) | ~15s (并行) | **6x** |
| 内容生成耗时（8篇文章） | ~48s (串行) | ~15s (并行×3) | **3x** |
| 平台适配容错 | 一个失败全挂 | 独立容错 | ✅ |
| 引擎遍历 | 全部引擎（含未配置） | 仅可用引擎 | ✅ |

---

## 已知剩余风险

1. **百度文心API未实际测试** — 代码逻辑正确（OAuth2 token + URL参数），但需真实API Key验证
2. **腾讯元宝API未实际测试** — TC3签名算法按官方文档实现，需真实 SecretId/SecretKey 验证
3. **SQLite async 环境风险** — 仍使用同步 sqlite3（`threading.local()` 线程池），在 uvicorn async 多 worker 下可能有问题。建议后续迁移到 `aiosqlite`
4. **无请求速率限制** — 高并发下可能触发API provider限流

---

## 总结

修复了审计中发现的 **9个问题**（2个高危、5个中危、2个低危），其中：
- 3个为阻断性/高危问题（配置加载、API认证）
- 6个为质量和性能优化

系统现已具备基本的生产可用性。建议在部署前用真实API Key完成一轮端到端测试。

---

*修复人：Hermes Agent (AI) · 2026-05-20*
