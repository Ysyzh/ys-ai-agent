"""
=============================================================
  你的 AI Agent v5 —— 搜索升级 + 向量记忆
=============================================================

v4 → v5 变化：
  • 搜索：Bing 正则解析 → Tavily API（专为 AI Agent 设计）
  • 记忆：memory.json + 关键词匹配 → ChromaDB 向量语义搜索
  • 对话：每轮从零开始（模型每轮失忆）→ harness 手动维护对话历史

LangChain 帮你省掉的：
  • 工具 JSON Schema 手写（60行）→ @tool 装饰器（5行/个）
  • execute_tool switch 分发 → 框架自动匹配
  • Agent 循环（70行 while True）→ create_agent 一行
  • 消息历史管理 → LangGraph 内部自动处理

没变的（工具核心逻辑）：
  • 天气：Open-Meteo API
"""

import json
import os
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv
import requests
import chromadb
from tavily import TavilyClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from rich.console import Console
from rich.markdown import Markdown

console = Console()

# ============================================================
#  第一部分：初始化
# ============================================================

load_dotenv()

# 模型配置 —— 以后切 Claude 只改这里
llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    temperature=0.0,
)

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ============================================================
#  第二部分：记忆系统 —— ChromaDB 向量数据库，语义搜索
# ============================================================
# 前 v3/v4：memory.json + 关键词匹配 → 搜"辣"找不到"口味偏好"
# 现在：ChromaDB + embedding → 语义匹配，怎么问都能找到

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")  # 保留用于旧数据迁移
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="agent_memories")


def migrate_from_json():
    """一次性迁移：把旧的 memory.json 数据导入 ChromaDB"""
    if not os.path.exists(MEMORY_FILE):
        return
    if collection.count() > 0:
        return
    with open(MEMORY_FILE, "r") as f:
        data = json.load(f)
    facts = data.get("facts", [])
    if not facts:
        return
    for f in facts:
        collection.add(
            documents=[f["content"]],
            ids=[str(f["id"])],
            metadatas=[{"created_at": f["created_at"]}],
        )
    print(f"✅ 已迁移 {len(facts)} 条记忆到向量数据库")


migrate_from_json()


def save_fact(fact: str) -> dict:
    """保存记忆到 ChromaDB"""
    # 用 uuid 而不是 count()+1：删过记忆后 count 会回退，新 id 会撞上旧 id 覆盖掉旧记忆
    new_id = uuid4().hex
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    collection.add(
        documents=[fact],
        ids=[new_id],
        metadatas=[{"created_at": created_at}],
    )
    return {"id": new_id, "content": fact, "created_at": created_at}


def search_facts(query: str, n_results: int = 5) -> list[str]:
    """语义搜索记忆 — 不只是关键词匹配"""
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=n_results)
    if not results["documents"][0]:
        return []
    return results["documents"][0]


def build_memory_prompt() -> str:
    """读取全部记忆，注入 system prompt"""
    if collection.count() == 0:
        return ""
    memories = collection.get()
    if not memories["documents"]:
        return ""
    lines = ["## 关于用户的已知信息："]
    for doc, meta in zip(memories["documents"], memories["metadatas"]):
        lines.append(f"  · {doc}（{meta.get('created_at', '')}）")
    return "\n".join(lines)

# ============================================================
#  第三部分：天气 API（不变）
# ============================================================

WEATHER_CODES = {
    0: "晴天☀️", 1: "大部晴朗🌤️", 2: "多云⛅", 3: "阴天☁️",
    45: "有雾🌫️", 48: "雾凇", 51: "小毛毛雨🌧️", 53: "毛毛雨🌧️",
    55: "大毛毛雨🌧️", 61: "小雨🌧️", 63: "中雨🌧️", 65: "大雨🌧️",
    71: "小雪❄️", 73: "中雪❄️", 75: "大雪❄️", 80: "阵雨🌦️",
    82: "强阵雨🌦️", 85: "小阵雪❄️", 86: "大阵雪❄️", 95: "雷暴⛈️",
}

def geocode(city: str) -> dict | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    resp = requests.get(url, params={"name": city, "count": 1, "language": "zh"}, timeout=10)
    if resp.status_code != 200 or not resp.json().get("results"):
        return None
    r = resp.json()["results"][0]
    return {"name": r.get("name", city), "country": r.get("country", ""),
            "latitude": r["latitude"], "longitude": r["longitude"]}

def get_real_weather(city: str) -> str:
    geo = geocode(city)
    if not geo:
        return f"找不到城市'{city}'，请确认城市名称"
    resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": geo["latitude"], "longitude": geo["longitude"],
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "timezone": "Asia/Shanghai",
    }, timeout=10)
    if resp.status_code != 200:
        return "天气服务暂时不可用"
    c = resp.json()["current"]
    weather = WEATHER_CODES.get(c["weather_code"], f"未知({c['weather_code']})")
    return json.dumps({
        "城市": f"{geo['name']}, {geo['country']}", "天气": weather,
        "温度": f"{c['temperature_2m']}°C", "湿度": f"{c['relative_humidity_2m']}%",
        "风速": f"{c['wind_speed_10m']} km/h",
    }, ensure_ascii=False)

# ============================================================
#  第四部分：搜索 API（不变）
# ============================================================

def search_tavily(query: str, max_results: int = 5) -> str:
    """使用 Tavily API 搜索，返回结构化结果"""
    try:
        result = tavily.search(query=query, max_results=max_results)
        if not result.get("results"):
            return "未找到相关信息"
        formatted = []
        for r in result["results"]:
            formatted.append({
                "标题": r.get("title", ""),
                "摘要": r.get("content", "")[:300],
                "链接": r.get("url", ""),
            })
        return json.dumps(formatted, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"搜索失败: {e}"

# ============================================================
#  第五部分：工具定义 —— @tool 装饰器，Schema 自动生成
# ============================================================
# 对比 v3 手写 JSON（每个工具 20 行），现在每个 5 行

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。city 是城市名，如'北京'、'深圳'。"""
    return get_real_weather(city)

@tool
def search_web(query: str) -> str:
    """搜索互联网获取最新信息。需要实时数据时使用。"""
    return search_tavily(query)

@tool
def remember(fact: str) -> str:
    """记住一条关于用户的重要信息。用户说了将来可能用到的信息时主动调用。"""
    saved = save_fact(fact)
    return f"已记住 ✅ — {fact}"

@tool
def recall(query: str) -> str:
    """搜索长期记忆，支持语义匹配。需要回忆用户之前说过的信息时调用。"""
    results = search_facts(query)
    if not results:
        return "没有找到相关记忆"
    return json.dumps({"相关记忆": results}, ensure_ascii=False)

tools = [get_weather, search_web, remember, recall]

# ============================================================
#  第六部分：创建 Agent —— 一行替代 v3 的 70 行 while 循环
# ============================================================

# System Prompt 只写「行为规则」，长期记忆不写死在这里
# （记忆每轮都可能变，靠 run_agent 动态额外注入一条 system 消息）
SYSTEM_PROMPT = """你是一个友好的AI助手。当需要实时信息时请调用工具。
用户可能说一些个人信息（名字、工作等），请主动调用 remember 保存。
当你需要确认用户的已知信息时，调用 recall 搜索记忆。
用中文回复，语气自然亲切。"""

# create_agent 内部是 LangGraph 状态图，自动处理 Agent 循环
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)

# ============================================================
#  第七部分：对话历史 —— harness 真正在替你做的事
# ============================================================
# 关键认知：模型 API 是无状态的纯函数
#
#     (消息数组, 工具清单) → 一段文本  或  一个「我要调工具」的请求
#
# 它不"记得"你上一句说了什么。所谓"连续对话"，是 harness 每一轮把
# 【完整历史】重新拼一遍再发过去。
#
# v5 之前这里每轮只发当前这一句 → 模型每轮失忆，只有 remember 存进
# ChromaDB 的"事实"能跨轮带过去，本轮聊过什么它转头就忘。
#
# DSH / Claude Code 做的就是下面这件小事，只是工程化得更好：
# 会话落盘到 ~/.dsh/sessions/、超长自动压缩、多会话隔离。

MAX_HISTORY_MESSAGES = 40  # 保留最近 40 条消息（约 20 轮），防止上下文无限增长

conversation: list[dict] = []


def reset_conversation() -> None:
    """清空对话历史（只影响本轮聊天，不动 ChromaDB 里的长期记忆）"""
    conversation.clear()


# ============================================================
#  第八部分：运行入口
# ============================================================

def run_agent(user_message: str) -> str:
    """
    v3: 70 行 while 循环 + 手动消息管理
    v5: 一行 invoke，LangGraph 自动跑完整个循环
        + 手动维护对话历史（因为模型无状态，历史必须每轮重发）
    """
    # 1. 把用户这句话追加进历史，并裁掉过老的部分
    conversation.append({"role": "user", "content": user_message})
    if len(conversation) > MAX_HISTORY_MESSAGES:
        conversation[:] = conversation[-MAX_HISTORY_MESSAGES:]
        if conversation[0]["role"] != "user":
            conversation.pop(0)  # 保证历史以 user 开头，别裁出半截对话

    # 2. 复制一份发给模型 —— 注意发出去的是【整段历史】，不是只发当前这句
    messages = list(conversation)

    # 3. 长期记忆（ChromaDB 里的事实）每轮重新注入一次
    memory_prompt = build_memory_prompt()
    if memory_prompt:
        messages.insert(0, {"role": "system", "content": memory_prompt})

    # 4. 一行搞定 Agent 循环：模型要调工具就调，结果自动塞回，直到给出最终答复
    result = agent.invoke({"messages": messages})

    # 5. 提取最后一条 AI 消息，并写回历史 —— 下一轮模型才看得到自己说过什么
    for msg in reversed(result["messages"]):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            console.print(Markdown(msg.content))
            conversation.append({"role": "assistant", "content": msg.content})
            return msg.content

    return ""


if __name__ == "__main__":
    run_agent("北京今天天气怎么样？另外搜索一下人工智能最新进展")
