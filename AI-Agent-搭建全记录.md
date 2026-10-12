# AI Agent 从零搭建全记录

> 2026-07-17 初稿 · 2026-10-12 补充 v5 · 袁振皓 · Java 5年 → Python + AI Agent

## 背景

- Java 5年开发经验，无 Python/AI 背景
- 目标：理解 AI Agent 原理，快速搭建自己的 Agent
- 已有：DeepSeek API Key（从 TradingAgents-CN 项目复用）

---

## 1. 技术选型决策

| 决策点 | 选项 | 选择 | 理由 |
|--------|------|------|------|
| 语言 | Python vs Java | Python | AI 生态 99% 在 Python |
| 平台 | Dify vs 自己写 | 自己写 | Java 5年不需要低代码 |
| 框架 | 裸写 vs LangChain | 先裸写后 LangChain | 理解本质再用框架 |
| 模型 | Claude vs DeepSeek | DeepSeek | 已有 Key，工具调用够用 |
| Claude Code 后端 | Anthropic vs DeepSeek | DeepSeek | 配置在 settings.json |

### Java → Python 5分钟速查

| Java | Python |
|------|--------|
| `String name = "hello";` | `name = "hello"` |
| `List<String> list = new ArrayList<>();` | `list = []` |
| `public void foo(String s) {}` | `def foo(s):` |
| `for (int i = 0; i < 10; i++)` | `for i in range(10):` |
| `class Dog extends Animal {}` | `class Dog(Animal):` |
| `null` | `None` |
| `{}` 花括号 | 缩进 |

---

## 2. 项目演进历史

```
v1 (50行)          v2 (80行)          v3 (398行)         v4 (150行)          v5 (298行)
裸写 Agent 循环 →  接真实天气 + 记忆 →  接真实搜索 →    LangChain 重构  →   搜索/记忆/对话升级

DeepSeek +         + Open-Meteo       + Bing 搜索         @tool + create_agent  Tavily + ChromaDB
OpenAI SDK          + memory.json     全工具真实化         代码量减少 62%        + 手动维护对话历史
```

### v1：理解 Agent 循环本质

Agent 循环就四步：
```
用户消息 → 调 LLM → LLM 说"调工具X" → 执行工具 → 结果返回 LLM → 循环直到 LLM 给出最终答案
```

核心代码就是 `while True` + 判断 `tool_calls` + 把结果塞回 `messages`。

### v2：真实天气 + 记忆系统

- **天气 API**：Open-Meteo（免费，无需 Key）
  - 流程：城市名 → Geocoding API → 经纬度 → Weather API
- **记忆系统**：`memory.json` 文件持久化
  - `remember` 工具：LLM 自动保存重要信息
  - `recall` 工具：LLM 搜索已有记忆
  - 启动时自动注入 system prompt

### v3：真实搜索

- **搜索**：Bing 搜索（正则解析 HTML，国内可用，免费）
- DuckDuckGo 和 SearXNG 国内均不可用
- 三个工具全部真实化：天气、搜索、记忆

### v4：LangChain 重构

| 对比 | v3 手写 | v4 LangChain |
|------|---------|-------------|
| 工具定义 | 60行 JSON Schema | 20行 @tool 装饰器 |
| 工具分发 | 30行 match-case | 自动匹配 |
| Agent 循环 | 70行 while True | `create_agent()` + `invoke()` |
| 消息管理 | 散落3处手动 append | 框架内部处理 |
| 工具逻辑 | 80行 | 80行（**一行没改**） |
| **总计** | **398行** | **~150行（省62%）** |

### v5：搜索、记忆、对话三项升级

v4 完成后暴露出三个问题，v5 一次解决：

| 问题 | v4 的做法 | v5 的做法 |
|------|-----------|-----------|
| 搜索质量差 | Bing 正则解析 HTML，容易被改版打断 | **Tavily API**（专为 AI Agent 设计的搜索） |
| 记忆搜不到 | `memory.json` + 关键词匹配（搜"辣"匹配不到"口味偏好"） | **ChromaDB 向量库 + 语义搜索** |
| **模型每轮失忆** | `messages` 每轮只发当前这一句 | **harness 手动维护对话历史**，每轮重发完整历史 |

#### 关于「模型每轮失忆」这件事（v5 最重要的认知）

之前的 `run_agent()` 是这样的：

```python
memory_prompt = build_memory_prompt()
system_prompt = SYSTEM_PROMPT.format(memory_context=memory_prompt)  # ← 算了却没用，死代码
messages = [{"role": "user", "content": user_message}]              # ← 只有当前这一句
result = agent.invoke({"messages": messages})
```

**为什么这会导致失忆**：模型 API 是无状态的纯函数 ——

```
(消息数组, 工具清单) → 一段文本  或  一个「我要调工具」的请求
```

它每次都像第一次看到这段对话，**自己没有任何记忆**。所以"连续对话"这件事
必须由调用方负责：每轮把完整历史重新拼一遍再发过去。

v5 改成：

```python
conversation.append({"role": "user", "content": user_message})   # 1. 追加进历史
messages = list(conversation)                                     # 2. 发整段历史
messages.insert(0, {"role": "system", "content": memory_prompt})  # 3. 注入长期记忆
result = agent.invoke({"messages": messages})                     # 4. 一行跑完 Agent 循环
conversation.append({"role": "assistant", "content": msg.content})# 5. 回答也写回历史
```

外加 `MAX_HISTORY_MESSAGES = 40` 做裁剪（防止上下文无限增长），
`reset_conversation()` 供 `/clear` 清空。

#### 这就是 DSH / Claude Code 替你做的事

| | 本项目的做法 | DSH / Claude Code |
|---|---|---|
| 历史存哪 | 内存 `conversation` 列表 | 落盘 `~/.dsh/sessions/` |
| 超长怎么办 | 粗暴裁掉最老的 | 自动压缩 / 摘要 |
| 多会话 | 无 | 会话隔离、可恢复 |

**结论：这些"像人一样记得"的能力，全在 harness 里，不在模型里。**

#### v5 顺带修的两个隐患

1. `save_fact()` 原来用 `collection.count() + 1` 当记忆 id —— 删过记忆后
   `count()` 会回退，新 id 撞上旧 id 就把旧记忆覆盖了。改为 `uuid4().hex`。
2. `SYSTEM_PROMPT` 里原来有个 `{memory_context}` 占位符，但记忆实际是通过
   额外插一条 system 消息注入的，占位符从没被真正使用。已拆掉，避免两套机制并存。

---

## 3. 当前项目结构

```
aiworkspace/my-first-agent/
├── agent.py               # v5 主逻辑，298行（模型/记忆/工具/Agent/对话历史）
├── chat.py                # 交互式对话入口，32行（quit 退出、/clear 清空历史）
├── memory.json            # ⚠️ v4 遗留，只作一次性迁移源
├── chroma_db/             # v5 向量记忆库（已 gitignore）
├── .env                   # DeepSeek + Tavily API Key（已 gitignore）
├── .env.example           # 只放占位符
├── .gitignore
├── .github/
│   └── copilot-instructions.md   # 给 AI 编码助手看的项目约定
└── AI-Agent-搭建全记录.md   # 本文件
```

### 四个工具

| 工具 | 实现 | Key |
|------|------|-----|
| `get_weather` | Open-Meteo API（地理编码+天气预报） | 免费 |
| `search_web` | **Tavily API**（专为 AI Agent 设计） | `TAVILY_API_KEY`，免费 1000 次/月 |
| `remember` | 写入 **ChromaDB 向量库** | 本地 |
| `recall` | **语义搜索** ChromaDB | 本地 |

### 两套「记忆」的区别（容易混）

| | 存什么 | 存哪 | 生命周期 |
|---|---|---|---|
| 对话历史 | 本轮聊过的话 | 内存 `conversation` 列表 | 进程退出即丢，`/clear` 可清 |
| 长期记忆 | 关于用户的事实 | `chroma_db/` 向量库 | 永久，跨进程 |

### 运行方式

```bash
cd ~/aiworkspace/my-first-agent

# 单次运行
python3 agent.py

# 交互式对话（quit 退出，/clear 清空对话历史）
python3 chat.py
```

首次运行会下载 ChromaDB 的 embedding 模型（约 166MB → `~/.cache/chroma/`）。

---

## 4. 关键认知

1. **Agent = 提示词 + 代码**：平台（Dify）只是把代码封装了
2. **模型无状态**：模型 API 是纯函数，没有记忆、没有"正在对话"这个状态。
   连续对话、长期记忆全是 harness 每轮重发历史/注入上下文的结果 —— 这是 v5 最大的认知
3. **LangChain 不给你新能力**：它能做的你手写也能做，它只是省样板代码
4. **工具逻辑是核心**：框架换多少代，工具的业务代码不变
5. **理解本质再用框架**：先裸写理解循环，再用 LangChain 省事

---

## 5. Claude Code VS Code 扩展

- 终端版和扩展版**共享配置**（`~/.claude/settings.json`）
- 配置了 DeepSeek 后端（`api.deepseek.com/anthropic`，模型 `deepseek-v4-pro`）
- VS Code 扩展已安装（`anthropic.claude-code` v2.1.212）
- 打开方式：`Cmd+Shift+P` → `Claude Code: Open`

---

## 6. 依赖清单

```bash
# ── v1～v3 时期 ──
pip3 install openai           # DeepSeek API（OpenAI 兼容），v4 起由 langchain-openai 传递依赖
pip3 install python-dotenv    # .env 环境变量
pip3 install requests         # HTTP 请求（Open-Meteo 天气）

# ── v4 起 ──
pip3 install langchain        # LangChain 框架
pip3 install langchain-openai # LangChain OpenAI 集成

# ── v5 新增 ──
pip3 install chromadb         # 向量记忆库（自带本地 embedding，首次约下载 166MB）
pip3 install tavily-python    # Tavily 搜索 API 客户端
pip3 install rich             # 终端 Markdown 渲染
```

一行装完（v5 现状）：

```bash
pip3 install python-dotenv requests rich langchain langchain-openai chromadb tavily-python
```

### Python 版本

- Python 3.14.2（macOS）

---

## 7. 下一步可做

| 方向 | 说明 | 状态 |
|------|------|------|
| 接真实搜索增强 | Tavily API（专为 AI Agent 设计，免费1000次/月） | ✅ v5 已完成 |
| 向量记忆 | 语义搜索记忆（"喜欢辣"能匹配"口味偏好"） | ✅ v5 已完成 |
| 对话历史 | harness 手动维护 messages，修掉"每轮失忆" | ✅ v5 已完成 |
| **RAG（检索增强）** | 文档切片 + Retriever + 带引用回答 | ⬜ 待做（候选方向） |
| **LangGraph 拆解** | 用显式状态图复刻 `create_agent` 内部，看清 Agent 循环 | ⬜ 待做（候选方向） |
| **多 Agent 协作** | 调研 Agent + 写作 Agent + 审阅 Agent 分工 | ⬜ 待做（候选方向） |
| 部署 | FastAPI + Docker 部署为 HTTP 服务 | ⬜ 待做 |
| 工具市场 | 接入更多现成工具（发邮件、查数据库、操作文件） | ⬜ 待做 |
