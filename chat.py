"""
交互式对话入口 —— LangChain 版

运行: python3 chat.py
退出: 输入 quit / exit / 退出
清空: 输入 /clear / 清空 / 重置
"""
from agent import run_agent, reset_conversation
from rich.console import Console

console = Console()
console.print("🤖 AI 助手已就绪（quit 退出 / /clear 清空对话历史）\n")

EXIT_WORDS = {"quit", "exit", "退出", "eixt", "exir", "exitt", "quitt", "quite"}
CLEAR_WORDS = {"/clear", "clear", "清空", "重置", "/reset", "reset"}

while True:
    user_input = input("👤 你: ").strip()
    if not user_input:
        continue
    lower = user_input.lower()
    # 短输入 + 匹配退出关键词（包含常见 typo）→ 直接退出，不发给 LLM
    if " " not in lower and lower in EXIT_WORDS:
        console.print("👋 再见！")
        break
    # 清空对话历史（ChromaDB 里的长期记忆不动）
    if " " not in lower and lower in CLEAR_WORDS:
        reset_conversation()
        console.print("🧹 对话历史已清空，模型不再记得刚才聊过什么（长期记忆保留）\n")
        continue
    run_agent(user_input)
    print()
