# AI Agent 从零搭建全记录

> 2026-07-17 · 袁振皓 · Java 5年 → Python + AI Agent

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
v1 (50行)          v2 (80行)          v3 (398行)         v4 (150行)
裸写 Agent 循环 →  接真实天气 + 记忆 →  接真实搜索 →    LangChain 重构

DeepSeek +         + Open-Meteo       + Bing 搜索         @tool + create_agent
OpenAI SDK          + memory.json     全工具真实化         代码量减少 62%
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

---

## 3. 当前项目结构

```
aiworkspace/my-first-agent/
├── agent.py              # v4 LangChain 重构版，150行
├── chat.py               # 交互式对话入口
├── memory.json           # 持久化记忆存储
├── .env                  # DeepSeek API Key
└── AI-Agent-搭建全记录.md  # 本文件
```

### 四个工具

| 工具 | 实现 | Key |
|------|------|-----|
| `get_weather` | Open-Meteo API（地理编码+天气预报） | 免费 |
| `search_web` | Bing 搜索（正则解析HTML） | 免费 |
| `remember` | 写入 memory.json | 本地 |
| `recall` | 搜索 memory.json | 本地 |

### 运行方式

```bash
cd ~/aiworkspace/my-first-agent

# 单次运行
python3 agent.py

# 交互式对话
python3 chat.py
```

---

## 4. 关键认知

1. **Agent = 提示词 + 代码**：平台（Dify）只是把代码封装了
2. **LangChain 不给你新能力**：它能做的你手写也能做，它只是省样板代码
3. **工具逻辑是核心**：框架换多少代，工具的业务代码不变
4. **理解本质再用框架**：先裸写理解循环，再用 LangChain 省事

---

## 5. Claude Code VS Code 扩展

- 终端版和扩展版**共享配置**（`~/.claude/settings.json`）
- 配置了 DeepSeek 后端（`api.deepseek.com/anthropic`，模型 `deepseek-v4-pro`）
- VS Code 扩展已安装（`anthropic.claude-code` v2.1.212）
- 打开方式：`Cmd+Shift+P` → `Claude Code: Open`

---

## 6. 依赖清单

```bash
pip3 install openai           # DeepSeek API（OpenAI 兼容）
pip3 install python-dotenv    # .env 环境变量
pip3 install requests         # HTTP 请求
pip3 install langchain        # LangChain 框架
pip3 install langchain-openai # LangChain OpenAI 集成
```

### Python 版本

- Python 3.14.2（macOS）

---

## 7. 下一步可做

| 方向 | 说明 |
|------|------|
| 接真实搜索增强 | Tavily API（专为 AI Agent 设计，免费1000次/月） |
| 向量记忆 | 语义搜索记忆（"喜欢辣"能匹配"口味偏好"） |
| 多 Agent 协作 | LangGraph 编排多个 Agent 分工 |
| 部署 | FastAPI + Docker 部署为 HTTP 服务 |
| 工具市场 | 接入更多现成工具（发邮件、查数据库、操作文件） |
