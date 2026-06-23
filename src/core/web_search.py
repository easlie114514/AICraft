"""联网搜索模块 — 模型原生 server-side web_search + 快捷数据源

搜索策略：
  1. Server-side web_search（模型平台执行搜索，DeepSeek/Claude/OpenAI 原生支持）
  2. 快捷数据源：天气/金价/汇率/热搜 — 客户端 function calling，直接请求权威站API

Bing HTML 爬虫和 DuckDuckGo 已废弃 — server-side 搜索质量远超客户端爬虫。
"""

import logging
import re

import requests

logger = logging.getLogger(__name__)


# ── HTML 辅助 ──────────────────────────────────────────

def _strip_html(text: str) -> str:
    """移除 HTML 标签并清理多余空白，不依赖第三方解析库"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ════════════════════════════════════════════════════════
# 快捷数据源 — 客户端 function calling 工具
# ════════════════════════════════════════════════════════

def _quick_weather(city: str) -> str:
    """直接请求 wttr.in 获取天气（全球免费天气API，无需Key，国内可达）"""
    if not city or not city.strip():
        city = "Beijing"
    city = city.strip()

    try:
        url = f"https://wttr.in/{city}?format=j1&lang=zh"
        headers = {"User-Agent": "curl/7.68.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]
        city_name = area.get("areaName", [{}])[0].get("value", city)
        region = area.get("region", [{}])[0].get("value", "")
        country = area.get("country", [{}])[0].get("value", "")

        cur_desc = current.get("lang_zh", [{}])[0].get("value",
                   current.get("weatherDesc", [{}])[0].get("value", ""))
        cur_temp = current.get("temp_C", "?")
        cur_feels = current.get("FeelsLikeC", "?")
        cur_humidity = current.get("humidity", "?")
        cur_wind = current.get("windspeedKmph", "?")
        cur_wind_dir = current.get("winddir16Point", "")

        body = (
            f"📍 {city_name}, {region}, {country}\n"
            f"🌤 当前天气: {cur_desc}\n"
            f"🌡 温度: {cur_temp}°C (体感 {cur_feels}°C)\n"
            f"💧 湿度: {cur_humidity}%\n"
            f"🌬 风速: {cur_wind}km/h {cur_wind_dir}\n"
        )

        forecasts = data.get("weather", [])
        for day in forecasts[:3]:
            date = day.get("date", "")
            max_t = day.get("maxtempC", "?")
            min_t = day.get("mintempC", "?")
            desc = day.get("hourly", [{}])[4].get("lang_zh", [{}])[0].get("value",
                   day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""))
            body += f"\n📅 {date}: {desc}, {min_t}°C ~ {max_t}°C"

        return body
    except Exception as e:
        logger.warning("快捷天气源失败: %s", e)
        return f"天气查询失败: {e}"


def _quick_gold_price() -> str:
    """直接请求东方财富API获取实时金价（国内可达，无需Key）"""
    try:
        urls = [
            ("https://push2.eastmoney.com/api/qt/stock/get?secid=113.auci&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170",
             "AU9999"),
            ("https://push2.eastmoney.com/api/qt/stock/get?secid=113.autd&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170",
             "黄金T+D"),
            ("https://push2.eastmoney.com/api/qt/stock/get?secid=101.XAUUSD&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170",
             "国际现货黄金"),
        ]
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

        body_parts = []
        for api_url, name in urls:
            try:
                resp = requests.get(api_url, headers=headers, timeout=8)
                d = resp.json().get("data", {})
                if not d:
                    continue
                price = d.get("f43", "?")
                high = d.get("f44", "?")
                low = d.get("f45", "?")
                open_p = d.get("f46", "?")
                change_pct = d.get("f170", "?")
                if isinstance(price, (int, float)) and price > 100000:
                    price = round(price / 100, 2)
                    high = round(high / 100, 2) if isinstance(high, (int, float)) else high
                    low = round(low / 100, 2) if isinstance(low, (int, float)) else low
                    open_p = round(open_p / 100, 2) if isinstance(open_p, (int, float)) else open_p
                    change_pct = round(change_pct / 100, 2) if isinstance(change_pct, (int, float)) else change_pct
                body_parts.append(
                    f"💰 {name}: 当前 {price} | 最高 {high} | 最低 {low} | 开盘 {open_p} | 涨跌 {change_pct}%"
                )
            except Exception:
                continue

        if not body_parts:
            return "金价查询失败：数据源暂不可用"

        return "\n".join(body_parts)
    except Exception as e:
        logger.warning("快捷金价源失败: %s", e)
        return f"金价查询失败: {e}"


def _quick_exchange_rate() -> str:
    """直接请求中国银行外汇牌价（权威数据源，无需Key）"""
    try:
        url = "https://www.boc.cn/sourcedb/whpj/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        rows = re.findall(r'<tr>(.*?)</tr>', resp.text, re.DOTALL)
        rates = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 6:
                currency = _strip_html(cells[0]).strip()
                if not currency:
                    continue
                buy_rate = _strip_html(cells[1]).strip()
                sell_rate = _strip_html(cells[3]).strip()
                mid_rate = _strip_html(cells[4]).strip()
                if mid_rate and mid_rate != "0.0000":
                    rates.append(f"💱 {currency}: 现汇买入 {buy_rate} | 现汇卖出 {sell_rate} | 中行折算价 {mid_rate}")

        if not rates:
            return "汇率查询失败：数据源暂不可用"

        return "\n".join(rates[:15])
    except Exception as e:
        logger.warning("快捷汇率源失败: %s", e)
        return f"汇率查询失败: {e}"


def _quick_hot_news() -> str:
    """直接请求百度热搜API获取热点新闻（无需Key）"""
    try:
        url = "https://top.baidu.com/board?tab=realtime"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        items = re.findall(r'"word":"([^"]+)".*?"desc":"([^"]*)".*?"url":"([^"]*)"', resp.text)
        if not items:
            items_simple = re.findall(r'"query":"([^"]+)"', resp.text)
            if items_simple:
                return "\n".join(f"🔥 {i+1}. {w}" for i, w in enumerate(items_simple[:20]))
            return "热搜查询失败：数据源暂不可用"

        return "\n".join(f"🔥 {i+1}. {word}\n   {desc}" for i, (word, desc, _) in enumerate(items[:20]))
    except Exception as e:
        logger.warning("快捷热搜源失败: %s", e)
        return f"热搜查询失败: {e}"


# ── 快捷数据源工具调度 ──────────────────────────────────

_QUICK_SOURCE_EXECUTORS = {
    "quick_weather": _quick_weather,
    "quick_gold_price": _quick_gold_price,
    "quick_exchange_rate": _quick_exchange_rate,
    "quick_hot_news": _quick_hot_news,
}


def execute_quick_source(tool_name: str, tool_args: dict) -> str:
    """执行快捷数据源工具，返回结果文本"""
    executor = _QUICK_SOURCE_EXECUTORS.get(tool_name)
    if not executor:
        return f"未知工具: {tool_name}"

    try:
        if tool_name == "quick_weather":
            return executor(tool_args.get("city", "Beijing"))
        elif tool_name in ("quick_gold_price", "quick_exchange_rate", "quick_hot_news"):
            return executor()
        else:
            return executor(**tool_args) if tool_args else executor()
    except Exception as e:
        return f"工具执行失败: {e}"


# ════════════════════════════════════════════════════════
# 工具定义
# ════════════════════════════════════════════════════════

# Anthropic 格式（用于 DeepSeek Anthropic 端点 / Claude）
QUICK_SOURCE_TOOLS_ANTHROPIC = [
    {
        "name": "quick_weather",
        "description": "查询指定城市的实时天气和未来预报。当用户询问天气、气温、下雨、温度、风力等天气相关问题时使用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，中文或英文，例如：北京、上海、Tokyo",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "quick_gold_price",
        "description": "查询实时黄金价格，包括AU9999、黄金T+D、国际现货黄金的当前价、最高最低价和涨跌幅。当用户询问金价、黄金价格、足金、金条等黄金相关问题时使用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "quick_exchange_rate",
        "description": "查询中国银行外汇牌价，获取各主要货币的现汇买入价、卖出价和折算价。当用户询问汇率、美元、欧元、日元等外汇相关问题时使用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "quick_hot_news",
        "description": "查询百度实时热搜榜，获取当前最热门新闻话题。当用户询问热搜、新闻排行、热门新闻、头条等新闻热点问题时使用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# OpenAI 格式（用于 openai_completion 路径，非 DeepSeek 模型）
QUICK_SOURCE_TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "quick_weather",
            "description": "查询指定城市的实时天气和未来预报。当用户询问天气、气温、下雨、温度、风力等天气相关问题时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，中文或英文，例如：北京、上海、Tokyo",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_gold_price",
            "description": "查询实时黄金价格，包括AU9999、黄金T+D、国际现货黄金的当前价、最高最低价和涨跌幅。当用户询问金价、黄金价格、足金、金条等黄金相关问题时使用此工具。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_exchange_rate",
            "description": "查询中国银行外汇牌价，获取各主要货币的现汇买入价、卖出价和折算价。当用户询问汇率、美元、欧元、日元等外汇相关问题时使用此工具。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_hot_news",
            "description": "查询百度实时热搜榜，获取当前最热门新闻话题。当用户询问热搜、新闻排行、热门新闻、头条等新闻热点问题时使用此工具。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def get_server_search_tools(provider: str, search_enabled: bool = False) -> list[dict]:
    """根据模型 provider 返回 server-side web_search 工具声明

    仅在 search_enabled=True 且 provider 支持时返回搜索工具。
    支持的 provider: deepseek, anthropic, openai
    """
    if not search_enabled:
        return []

    if provider == "deepseek":
        return [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]
    elif provider == "anthropic":
        return [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
            "user_location": {
                "type": "approximate",
                "city": "Beijing",
                "country": "CN",
                "timezone": "Asia/Shanghai",
            },
        }]
    elif provider == "openai":
        return [{
            "type": "web_search",
            "search_content_types": ["text"],
        }]
    else:
        return []


# ════════════════════════════════════════════════════════
# 向后兼容 - 旧 API 存根（aicraft.py / search.py 仍引用）
# ════════════════════════════════════════════════════════

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """[已废弃] 客户端搜索已被 server-side web_search 取代。

    此函数仅作为向后兼容存根。新代码应使用 server-side web_search。
    """
    logger.warning("web_search() 已废弃 — 联网搜索已升级为模型原生搜索，请使用新版本应用。")
    return [{
        "title": "搜索功能已升级",
        "body": "联网搜索已升级为模型原生 server-side 搜索。请通过 DeepSeek/Claude 模型的原生搜索能力进行联网搜索。",
        "href": "",
    }]


def format_search_results(results: list[dict]) -> str:
    """[已废弃] 格式化搜索结果"""
    if not results:
        return ""
    parts = ["\n\n# 联网搜索结果\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"\n{i}. {r['title']}\n   {r['body']}\n   来源: {r['href']}\n")
    return "\n".join(parts)
