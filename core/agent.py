import os
import sys
import json
import asyncio
from openai import AsyncOpenAI

from core.tools import (
    search_arxiv_async,
    fetch_webpage_content,
    save_markdown_report,
    tools_schema
)
from core.prompts import SYSTEM_PROMPT


async def run_agent_workflow(user_input: str, status_callback, api_key: str = None):
    if not api_key:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        await status_callback("❌ API Key 未配置")
        return "❌ API Key 未配置，请在侧边栏输入后重试。"

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input}
    ]

    await status_callback("🚀 正在联络 DeepSeek API...")

    max_iterations = 5

    for i in range(max_iterations):
        await status_callback(f"🔄 第 {i + 1} 轮思考中...")

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools_schema,
            tool_choice="auto",
            temperature=0.3
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        # ==================== 真实思考内容显示 ====================
        if response_message.content:
            thinking = response_message.content.strip()
            await status_callback(f"💭 **模型思考**：{thinking}")
        # ========================================================

        tool_calls = response_message.tool_calls

        if not tool_calls:
            await status_callback("✅ 思考完成，正在生成最终报告...")
            return response_message.content or "调研完成。"

        # 显示工具调用计划
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
                await status_callback(f"🛠️ **计划调用工具**："
                                      f"{func_name}({json.dumps(args, ensure_ascii=False)})")
            except:
                await status_callback(f"🛠️ **计划调用工具**：{func_name}")

        await status_callback(f"🔧 开始执行 {len(tool_calls)} 个工具任务...")

        tasks = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
            except:
                function_args = {}

            if function_name == "search_arxiv_async":
                tasks.append(execute_tool(search_arxiv_async, function_args, tool_call.id))
            elif function_name == "fetch_webpage_content":
                tasks.append(execute_tool(fetch_webpage_content, function_args, tool_call.id))
            elif function_name == "save_markdown_report":
                tasks.append(execute_tool(save_markdown_report, function_args, tool_call.id))

        tool_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in tool_results:
            if isinstance(result, Exception):
                msg = f"工具执行异常: {str(result)}"
                await status_callback(f"❌ **工具返回异常**：{msg}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": "error",
                    "name": "error",
                    "content": str(result)
                })
            else:
                content_str = str(result.get("content", ""))
                short_content = content_str[:500] + "..." if len(content_str) > 500 else content_str
                await status_callback(f"📤 **工具返回**：{short_content}")
                messages.append(result)

    # 达到最大轮次时的最终强制输出
    await status_callback("⚠️ 达到最大思考轮次，基于已收集信息生成最终报告...")
    final_response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=messages + [{"role": "system", "content": "请立即基于以上所有信息，输出完整的 Markdown 调研报告，不要再调用任何工具。"}],
        tool_choice="none",
        temperature=0.3
    )
    return final_response.choices[0].message.content


# ==================== 必须的辅助函数（上一次遗漏的部分） ====================
async def execute_tool(func,     args, tool_call_id):
    """封装单个工具的执行逻辑"""
    try:
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": func.__name__,
            "content": str(result)
        }
    except Exception as e:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": func.__name__,
            "content": f"工具执行报错: {str(e)}"
        }
# ============================================================================