"""联网搜索模块 - 基于DuckDuckGo"""

from duckduckgo_search import DDGS


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
