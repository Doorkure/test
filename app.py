import os
import sys

# 强制设置 Python 内部编码环境（保留这部分即可）
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

import streamlit as st
import asyncio
from dotenv import load_dotenv
from core.agent import run_agent_workflow
from core.tools import save_markdown_report  # 新增：用于自动保存报告

load_dotenv()

# ====================== 修复 Streamlit 重新运行时的 I/O 错误 ======================
# （已移除全局 sys.stdout 包装器，这是导致第二次提问崩溃的根本原因）
# =============================================================================



st.set_page_config(
    page_title="AI Research Agent - 2026 实验版",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 自动文献调研智能体")
st.markdown("""
本系统基于 **DeepSeek-V3** 与 **Agentic Workflow** 设计，具备自主规划、论文检索、网页抓取与报告生成能力。
- **技术栈**: OpenAI SDK (Async), Streamlit, aiohttp, BeautifulSoup4
""")

with st.sidebar:
    st.header("系统设置")
    api_key = st.text_input("DeepSeek API Key",
                            type="password",
                            value=os.getenv("DEEPSEEK_API_KEY", ""))
    st.info("注：建议通过 .env 文件配置 API Key 以确保安全。")

    if st.button("清理历史记录"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("输入调研主题"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        thinking_logs = []
        log_container = st.container()

        async def update_ui_status(message: str):
            thinking_logs.append(message)
            log_container.write(f"🔹 {message}")

        with st.status("🚀 智能体正在思考...", expanded=True) as status:
            try:
                task = run_agent_workflow(prompt, update_ui_status, api_key=api_key)
                final_response = asyncio.run(task)   # 使用 asyncio.run（Streamlit 环境下已安全）

                status.update(label="✅ 调研完成", state="complete", expanded=False)
            except Exception as e:
                status.update(label="❌ 执行出错", state="error")
                st.error(f"捕捉到错误: {e}")
                final_response = f"任务因环境或网络问题中断。\n\n错误信息: {e}"

        # ==================== 新增：显示完整思考过程 ====================
        with st.expander("🤔 智能体完整思考过程 (Chain of Thought)", expanded=True):
            for log in thinking_logs:
                if log.startswith("💭 **模型思考**"):
                    st.markdown(log)  # 模型的真实思考用 Markdown 高亮
                elif log.startswith("🛠️ **计划调用工具**"):
                    st.info(log)
                elif log.startswith("📤 **工具返回**"):
                    st.success(log)
                else:
                    st.write(log)
        # =============================================================

        st.markdown(final_response)
        st.session_state.messages.append({"role": "assistant", "content": final_response})

        # ==================== 新增：自动保存为 .md 文件 ====================
        if final_response and len(final_response) > 50:
            safe_prompt = prompt[:30].strip().replace(" ", "_").replace("/", "_")
            filename = f"{safe_prompt}_research_report.md"
            save_result = save_markdown_report(filename, final_response)
            st.success(f"📁 报告已自动保存至：reports/{filename}")
        # =============================================================

st.divider()
st.caption("2026 自然语言处理实验 | 开发环境: VS Code | 框架: Async-Agent-Framework")