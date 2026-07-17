"""
=============================================================
  你的 AI Agent v4 —— LangChain 重构版
=============================================================

对比：
  v3：398行，Agent 循环手写，工具定义 JSON 手写
  v4：~150行，LangChain 框架接管所有样板代码

LangChain 帮你省掉的：
  • 工具 JSON Schema 手写（60行）→ @tool 装饰器（5行/个）
  • execute_tool switch 分发 → 框架自动匹配
  • Agent 循环（70行 while True）→ create_agent 一行
  • 消息历史管理 → LangGraph 内部自动处理

没变的（工具核心逻辑，和 v3 一模一样）：
  • 天气：Open-Meteo API
  • 搜索：Bing 搜索
  • 记忆：memory.json 持久化
"""

import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import requests
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool

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

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

# ============================================================
#  第二部分：记忆系统（和 v3 一样，跨会话持久化）
# ============================================================

def load_memory() -> list[dict]:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f).get("facts", [])

def save_fact(fact: str) -> dict:
    facts = load_memory()
    new_fact = {
        "id": len(facts) + 1,
        "content": fact,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    facts.append(new_fact)
    with open(MEMORY_FILE, "w") as f:
        json.dump({"facts": facts}, f, ensure_ascii=False, indent=2)
    return new_fact

def search_facts(keyword: str) -> list[dict]:
    return [f for f in load_memory() if keyword in f["content"]]

def build_memory_prompt() -> str:
    facts = load_memory()
    if not facts:
        return ""
    lines = ["## 关于用户的已知信息："]
    for f in facts:
        lines.append(f"  {f['id']}. {f['content']}（{f['created_at']}）")
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

def search_bing(query: str, max_results: int = 5) -> str:
    try:
        resp = requests.get("https://www.bing.com/search",
            params={"q": query, "count": max_results},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=15)
        pattern = r'<li class="b_algo".*?<h2>.*?<a.*?href="(.*?)".*?>(.*?)</a>.*?<p.*?>(.*?)</p>'
        matches = re.findall(pattern, resp.text, re.DOTALL)
        if not matches:
            pattern2 = r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>'
            matches = re.findall(pattern2, resp.text, re.DOTALL)
        if not matches:
            return "未找到相关信息"
        formatted = []
        for url, title, snippet in matches[:max_results]:
            clean = lambda s: re.sub(r'<.*?>', '', re.sub(r'&[a-z]+;', '', s)).strip()
            formatted.append({"标题": clean(title), "摘要": clean(snippet)[:300], "链接": url})
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
    return search_bing(query)

@tool
def remember(fact: str) -> str:
    """记住一条关于用户的重要信息。用户说了将来可能用到的信息时主动调用。"""
    saved = save_fact(fact)
    return f"已记住 ✅ — {fact}"

@tool
def recall(keyword: str) -> str:
    """搜索长期记忆。需要回忆用户之前说过的信息时调用。"""
    results = search_facts(keyword)
    if not results:
        return "没有找到相关记忆"
    return json.dumps({"相关记忆": [r["content"] for r in results]}, ensure_ascii=False)

tools = [get_weather, search_web, remember, recall]

# ============================================================
#  第六部分：创建 Agent —— 一行替代 v3 的 70 行 while 循环
# ============================================================

# System Prompt 里放 {{memory_context}}，每次调用前替换
SYSTEM_PROMPT = """你是一个友好的AI助手。当需要实时信息时请调用工具。
用户可能说一些个人信息（名字、工作等），请主动调用 remember 保存。
当你需要确认用户的已知信息时，调用 recall 搜索记忆。
用中文回复，语气自然亲切。
{memory_context}"""

# create_agent 内部是 LangGraph 状态图，自动处理 Agent 循环
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT.format(memory_context=""),
)

# ============================================================
#  第七部分：运行入口
# ============================================================

def run_agent(user_message: str) -> str:
    """
    v3: 70 行 while 循环 + 手动消息管理
    v4: 动态注入记忆，一行 invoke，LangGraph 自动跑完整个循环
    """
    memory_prompt = build_memory_prompt()
    system_prompt = SYSTEM_PROMPT.format(memory_context=memory_prompt)

    messages = [{"role": "user", "content": user_message}]
    if memory_prompt:
        # 有记忆时，在前面加上系统消息提供上下文
        messages.insert(0, {"role": "system", "content": memory_prompt})

    result = agent.invoke({"messages": messages})

    # 提取最后一条 AI 消息
    for msg in reversed(result["messages"]):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            print(f"✅ {msg.content}")
            return msg.content

    return ""


if __name__ == "__main__":
    run_agent("北京今天天气怎么样？另外搜索一下人工智能最新进展")
