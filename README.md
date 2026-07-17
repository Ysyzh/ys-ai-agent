# 🤖 AI Agent 从零搭建

> 从 Java5年 → Python + AI Agent，理解 Agent 本质，手写 + LangChain 双版本。

## 项目演进

```
v1 (50行)      → v2 (80行)         → v3 (398行)        → v4 (150行)
裸写 Agent 循环    接真实天气 + 记忆     接真实搜索          LangChain 重构
```

## 快速开始

```bash
# 1. 安装依赖
pip3 install openai python-dotenv requests langchain langchain-openai

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key

# 3. 运行
python3 agent.py       # 单次运行
python3 chat.py        # 交互式对话
```

## 四个工具

| 工具 | 实现 | 费用 |
|------|------|------|
| `get_weather` | Open-Meteo API | 免费 |
| `search_web` | Bing 搜索 | 免费 |
| `remember` | memory.json 持久化 | 本地 |
| `recall` | memory.json 搜索 | 本地 |

## 关键认知

1. **Agent = 提示词 + 代码**：平台只是封装
2. **LangChain 不给你新能力**：它只是省样板代码
3. **工具逻辑是核心**：框架怎么换，业务代码不变
4. **先裸写再框架**：理解本质才能用好工具
