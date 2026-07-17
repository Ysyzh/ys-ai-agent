"""
交互式对话入口 —— LangChain 版

运行: python3 chat.py
退出: 输入 quit / exit / 退出
"""
from agent import run_agent

print("=" * 60)
print("  🤖 AI Agent v4 - LangChain 重构版")
print("  398行 → 150行，Agent 循环由框架管理")
print("=" * 60)
print()

while True:
    user_input = input("👤 你: ").strip()
    if not user_input:
        continue
    if user_input.lower() in ("quit", "exit", "退出"):
        print("👋 再见！")
        break
    run_agent(user_input)
    print()
