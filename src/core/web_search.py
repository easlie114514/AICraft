"""联网搜索模块 - 基于DuckDuckGo"""

from duckduckgo_search import DDGS

# Function-calling 工具定义（OpenAI 兼容格式）
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取实时信息。当你需要最新新闻、当前事件、实时数据（如金价、股价、天气）、"
            "事实核验等任何超出你训练数据截止日期或需要实时信息的问题时，必须调用此工具。"
            "搜索查询应使用关键词形式（而非自然语言问题），以获取最佳结果。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，使用关键词组合获取最佳结果",
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认5条",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """执行联网搜索，返回结果列表"""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href", ""),
                })
    except Exception as e:
        results.append({"title": "搜索失败", "body": str(e), "href": ""})
    return results


def format_search_results(results: list[dict]) -> str:
    """将搜索结果格式化为可注入prompt的文本"""
    if not results:
        return ""
    parts = ["\n\n# 联网搜索结果\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"\n{i}. {r['title']}\n   {r['body']}\n   来源: {r['href']}\n")
    return "\n".join(parts)
