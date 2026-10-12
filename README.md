# 🤖 AI Agent 从零搭建

> 从 Java5年 → Python + AI Agent，理解 Agent 本质，手写 + LangChain 双版本。

## 项目演进

```
v1 (50行)        → v2 (80行)           → v3 (398行)      → v4 (150行)          → v5 (298行)
裸写 Agent 循环     接真实天气 + 记忆       接真实搜索          LangChain 重构        搜索/记忆/对话三项升级
DeepSeek + SDK      + Open-Meteo          + Bing 搜索         @tool + create_agent  Tavily + ChromaDB + 对话历史
                    + memory.json                                              （Bing/memory.json 已被替换）
```

> v1～v3 的代码已被 v4 覆盖，行数是当时的历史快照，现只存在于
> [AI-Agent-搭建全记录.md](AI-Agent-搭建全记录.md) 的演进记录里。

---

## 一、先理解这件事：Agent = 对话框 + harness + 模型

```
① 对话框 / CLI          chat.py 的 input()
         ↓  把「历史消息 + 你这句话」打包成 messages 数组
② harness（本项目）      agent.py 的 run_agent()
         ↓  HTTP POST，带 messages + tools 的 JSON Schema
③ 模型 API 端点          https://api.deepseek.com        ← 无状态
         ↓
④ 真模型权重             deepseek-chat
```

**模型 API 是一个无状态的纯函数**：

```
(消息数组, 工具清单) → 一段文本  或  一个「我要调工具」的请求
```

它不"记得"你上一句说了什么。所谓"连续对话"，是第 ② 层每一轮把
**完整历史重新拼一遍**再发过去。

**本项目存在的意义，就是让你看清 ② 到底做了什么。** 第 ② 层在 v5 里只有
一行 `create_agent()`（[agent.py:227](agent.py#L227)），但历史怎么攒、记忆什么时候注入、
工具怎么分发 —— 这些想明白了，换成 DSH / Claude Code 那种成熟 harness 才不会懵。

---

## 二、快速开始

```bash
# 1. 安装依赖
pip3 install python-dotenv requests rich langchain langchain-openai chromadb tavily-python

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 TAVILY_API_KEY

# 3. 运行
python3 agent.py       # 单次运行
python3 chat.py        # 交互式对话（/clear 清空对话历史，quit 退出）
```

> 首次运行 ChromaDB 会自动下载 embedding 模型（约 166 MB，缓存在
> `~/.cache/chroma/`），下载完就离线可用。这一步在国内可能较慢。

---

## 三、四个工具

| 工具 | 实现 | Key / 费用 |
|------|------|-----------|
| `get_weather` | Open-Meteo API（地理编码 + 天气预报） | 免费，无需 Key |
| `search_web` | Tavily API（专为 AI Agent 设计） | 需 `TAVILY_API_KEY`，免费 1000 次/月 |
| `remember` | 写入 ChromaDB 向量库 | 本地 |
| `recall` | 语义搜索 ChromaDB | 本地 |

---

## 四、两套"记忆"，别搞混

| | 存什么 | 存哪 | 生命周期 |
|---|---|---|---|
| **对话历史** | 本轮聊过的话 | 内存里的 `conversation` 列表 | 进程退出即丢，`/clear` 可清 |
| **长期记忆** | 关于用户的事实 | `chroma_db/` 向量库 | 永久，跨进程 |

- 对话历史 = 第 40 行那个 `MAX_HISTORY_MESSAGES` 限制的列表，**只活在内存里**。
- 长期记忆 = `remember` 工具写进 ChromaDB 的内容，**重启也在**。
- `memory.json` 是 v4 的遗留文件，现在只当**一次性迁移源**用
  （`migrate_from_json()` 把老数据搬进 ChromaDB），搬完就没用了。

---

## 五、关键认知

1. **Agent = 提示词 + 代码**：平台（Dify）只是把代码封装了
2. **模型无状态**：连续对话不是模型的能力，是 harness 每轮重发历史的结果
3. **LangChain 不给你新能力**：它只是省样板代码 —— v3 手写 398 行 → v5 298 行
4. **工具逻辑是核心**：框架换多少代，工具的业务代码不变（80 行一行没改）
5. **先裸写再框架**：理解本质才能用好工具
