import asyncio
import aiohttp
import feedparser
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse

# 设置报告保存的基础路径
REPORT_DIR = "reports"
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

import urllib.parse
async def search_arxiv_async(query: str, max_results: int = 5) -> str:

    base_url = "http://export.arxiv.org/api/query?"

    encoded_query = urllib.parse.quote(query)

    params = {
        "search_query": f"all:{encoded_query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    # === 关键修复：添加合法 User-Agent ===
    headers = {
        "User-Agent": "AI-Research-Agent/1.0 (https://github.com/yourname/ai-research-agent; mailto:your@email.com)"
    }

    # 构造 URL
    url = base_url + "&".join([f"{k}={v}" for k, v in params.items()])

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:  # timeout 稍微加大
                if response.status != 200:
                    return f"Arxiv API 返回错误: HTTP {response.status}（请稍后重试）"

                xml_data = await response.text()
                feed = feedparser.parse(xml_data)

                if not feed.entries:
                    return "未找到相关论文，请尝试更换关键词。"

                results = []
                for entry in feed.entries:
                    results.append({
                        "title": entry.title.replace('\n', ' '),
                        "authors": [a.name for a in entry.authors] if hasattr(entry, 'authors') else [],
                        "summary": entry.summary.replace('\n', ' ') if hasattr(entry, 'summary') else "",
                        "link": entry.link,
                        "published": entry.published if hasattr(entry, 'published') else ""
                    })

                return str(results)
    except Exception as e:
        return f"搜索 Arxiv 时出错: {str(e)}（可能是临时网络问题，建议重试）"


async def fetch_webpage_content(url: str) -> str:
    """
    抓取网页正文。如果 Arxiv 摘要不够，Agent 可以调用此工具深入阅读。
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # 移除脚本和样式
                for script in soup(["script", "style"]):
                    script.extract()
                
                text = soup.get_text(separator=' ')
                # 清洗多余空格
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:3000] # 截断以节省上下文
    except Exception as e:
        return f"无法访问网页 {url}: {str(e)}"

def save_markdown_report(filename: str, content: str) -> str:
    """
    将生成的调研报告保存为本地 Markdown 文件。
    注意：此工具为同步执行，但在工作流中可直接调用。
    """
    try:
        # 确保文件名合法
        safe_filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        if not safe_filename.endswith(".md"):
            safe_filename += ".md"
            
        path = os.path.join(REPORT_DIR, safe_filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"报告已成功保存至: {path}"
    except Exception as e:
        return f"保存文件失败: {str(e)}"

# --- 下面是供给 Agent 使用的 Function Schema ---

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "search_arxiv_async",
            "description": "搜索 Arxiv 上的学术论文，返回包含标题、作者、摘要和链接的列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "返回的论文数量，默认5"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage_content",
            "description": "获取指定 URL 网页的纯文本内容，用于深入了解论文或新闻详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页 URL"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_markdown_report",
            "description": "将最终生成的结构化调研报告保存到本地 Markdown 文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名，例如 'DPO算法综述.md'"},
                    "content": {"type": "string", "description": "报告的 Markdown 格式内容"}
                },
                "required": ["filename", "content"]
            }
        }
    }
]