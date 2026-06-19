"""联网搜索模块 - 双源自动降级 + 快捷数据源

搜索策略：
  1. 快捷数据源：天气/金价等高频需求直接请求权威站API，不走搜索引擎
  2. Bing HTML 搜索（通用搜索主源，国内直连）
  3. DuckDuckGo（降级源，海外/代理用户）
"""

import logging
import re

import requests
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


# ── 快捷数据源：直接请求权威站，不走搜索引擎 ──────────────

# 关键词 → 快捷数据源的匹配规则
_QUICK_SOURCE_PATTERNS = [
    # (关键词列表, 处理函数)
    (["天气", "气温", "下雨", "温度", "风力"], "_quick_weather"),
    (["金价", "黄金价格", "黄金", "足金", "金条", "AU9999"], "_quick_gold_price"),
    (["汇率", "美元", "欧元", "日元", "英镑", "人民币兑换"], "_quick_exchange_rate"),
    (["热搜", "新闻排行", "热门新闻", "头条"], "_quick_hot_news"),
]


def _match_quick_source(query: str) -> str | None:
    """判断query是否匹配某个快捷数据源，返回函数名或None"""
    for keywords, func_name in _QUICK_SOURCE_PATTERNS:
        for kw in keywords:
            if kw in query:
                return func_name
    return None


def _quick_weather(query: str) -> list[dict]:
    """直接请求 wttr.in 获取天气（全球免费天气API，无需Key，国内可达）"""
    # 从query中提取城市名
    city = ""
    for candidate in re.split(r"[天气气温温度下雨风力预报明天后天]", query):
        candidate = candidate.strip()
        if candidate and len(candidate) >= 2:
            city = candidate
            break
    if not city:
        city = "Beijing"

    try:
        # wttr.in 支持中文城市名，format=j1 返回JSON
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

        # 当前天气
        cur_desc = current.get("lang_zh", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", ""))
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

        # 未来3天预报
        forecasts = data.get("weather", [])
        for day in forecasts[:3]:
            date = day.get("date", "")
            max_t = day.get("maxtempC", "?")
            min_t = day.get("mintempC", "?")
            desc = day.get("hourly", [{}])[4].get("lang_zh", [{}])[0].get("value",
                    day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""))
            body += f"\n📅 {date}: {desc}, {min_t}°C ~ {max_t}°C"

        return [{
            "title": f"{city_name}天气实时数据 (wttr.in)",
            "body": body,
            "href": f"https://wttr.in/{city}?lang=zh"
        }]
    except Exception as e:
        logger.warning("快捷天气源失败: %s", e)
        return []  # 降级到通用搜索


def _quick_gold_price(query: str) -> list[dict]:
    """直接请求东方财富API获取实时金价（国内可达，无需Key）"""
    try:
        # 东方财富行情API - 现货黄金(AU)和黄金T+D
        # AU9999: auci, 黄金T+D: autd, 国际现货: XAU
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
                # 东方财富数据 ÷100 得实际价格（部分品种）
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
            return []

        return [{
            "title": "实时黄金价格 (东方财富)",
            "body": "\n".join(body_parts),
            "href": "https://quote.eastmoney.com/gjs/qhau.html"
        }]
    except Exception as e:
        logger.warning("快捷金价源失败: %s", e)
        return []


def _quick_exchange_rate(query: str) -> list[dict]:
    """直接请求中国银行外汇牌价（权威数据源，无需Key）"""
    try:
        url = "https://www.boc.cn/sourcedb/whpj/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        # 解析HTML中的汇率表格
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
            return []

        return [{
            "title": "中国银行外汇牌价",
            "body": "\n".join(rates[:15]),
            "href": "https://www.boc.cn/sourcedb/whpj/"
        }]
    except Exception as e:
        logger.warning("快捷汇率源失败: %s", e)
        return []


def _quick_hot_news(query: str) -> list[dict]:
    """直接请求百度热搜API获取热点新闻（无需Key）"""
    try:
        url = "https://top.baidu.com/board?tab=realtime"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        # 从HTML中提取热搜数据
        items = re.findall(r'"word":"([^"]+)".*?"desc":"([^"]*)".*?"url":"([^"]*)"', resp.text)
        if not items:
            # 尝试更宽松的匹配
            items = re.findall(r'"query":"([^"]+)"', resp.text)
            if items:
                return [{
                    "title": "百度热搜榜",
                    "body": "\n".join(f"🔥 {i+1}. {w}" for i, w in enumerate(items[:20])),
                    "href": "https://top.baidu.com/board?tab=realtime"
                }]
            return []

        return [{
            "title": "百度热搜榜",
            "body": "\n".join(f"🔥 {i+1}. {word}\n   {desc}" for i, (word, desc, _) in enumerate(items[:20])),
            "href": "https://top.baidu.com/board?tab=realtime"
        }]
    except Exception as e:
        logger.warning("快捷热搜源失败: %s", e)
        return []

# Function-calling 工具定义（OpenAI 兼容格式）
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取实时信息。当你需要最新新闻、当前事件、实时数据（如金价、股价、天气）、"
            "事实核验等任何超出你训练数据截止日期或需要实时信息的问题时，必须调用此工具。"
            "query必须用2-5个关键词组合，禁止自然语言问句。"
            "正确：'今日金价 黄金价格'，错误：'昨晚金价多少'；"
            "正确：'百度热搜 今日新闻'，错误：'当前百度新闻TOP3分别是什么'。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "2-5个搜索关键词，用空格分隔。"
                        "只用名词和核心词，去掉'的''了''吗''什么''多少'等口语词。"
                        "示例：'金价 今日' '世界杯 C罗' '黄金价格 6月'"
                    ),
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


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """
    通过 Bing HTML 页面搜索（国内直连可用，无需 API Key）。

    从 cn.bing.com 的搜索结果页 HTML 中正则提取 <li class="b_algo"> 块，
    解析标题、链接和摘要。
    """
    url = "https://cn.bing.com/search"
    params = {"q": query, "count": str(max_results)}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    results: list[dict] = []

    # 匹配每个 <li class="b_algo"> 块（每个搜索结果一个）
    algo_re = re.compile(r'<li class="b_algo"[^>]*>(.*?)</li>', re.DOTALL)
    for match in algo_re.finditer(resp.text):
        if len(results) >= max_results:
            break
        block = match.group(1)

        # 提取链接和标题（<a> 标签内）
        link_match = re.search(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL
        )
        if not link_match:
            continue

        href = link_match.group(1)
        title = _strip_html(link_match.group(2))

        # 提取摘要：优先 <div class="b_caption">，其次 <p>
        caption_match = re.search(
            r'<(?:p|div)[^>]*class="[^"]*b_caption[^"]*"[^>]*>(.*?)</(?:p|div)>',
            block,
            re.DOTALL,
        )
        if not caption_match:
            caption_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.DOTALL)

        body = _strip_html(caption_match.group(1)) if caption_match else ""

        if title:
            results.append({"title": title, "body": body, "href": href})

    return results


def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """
    通过 DuckDuckGo 搜索（海外用户或配置了代理时可用，作为降级源）。
    """
    results: list[dict] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "href": r.get("href", ""),
            })
    return results


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    智能搜索入口：快捷数据源优先 → Bing → DuckDuckGo 降级

    策略：
      0. 如果query匹配快捷数据源（天气/金价/汇率/热搜），直接请求权威站API
      1. 否则走 Bing HTML 搜索（国内直连可用）
      2. Bing 失败 → 降级到 DuckDuckGo（海外/代理用户）
      3. 都失败 → 返回友好错误提示
    """
    # 0. 快捷数据源优先（直接请求权威站，不走搜索引擎）
    quick_func_name = _match_quick_source(query)
    if quick_func_name:
        quick_func = globals().get(quick_func_name)
        if quick_func:
            try:
                logger.info("快捷数据源=%s, query=%s", quick_func_name, query)
                results = quick_func(query)
                if results:
                    logger.info("快捷数据源成功, 返回%d条结果", len(results))
                    return results
                logger.info("快捷数据源返回0条结果，降级到通用搜索")
            except Exception as e:
                logger.warning("快捷数据源失败: %s，降级到通用搜索", e)

    # 1. 通用搜索：优先 Bing（国内直连）
    try:
        logger.info("搜索源=Bing, query=%s, max_results=%d", query, max_results)
        results = _search_bing(query, max_results)
        if results:
            logger.info("Bing搜索成功, 返回%d条结果", len(results))
            return results
        logger.info("Bing搜索返回0条结果，降级到DuckDuckGo")
    except Exception as e:
        logger.warning("Bing搜索失败: %s，降级到DuckDuckGo", e)

    # 2. 降级 DuckDuckGo（海外/代理用户）
    try:
        logger.info("搜索源=DuckDuckGo(降级), query=%s, max_results=%d", query, max_results)
        results = _search_duckduckgo(query, max_results)
        if results:
            logger.info("DuckDuckGo搜索成功, 返回%d条结果", len(results))
            return results
        logger.info("DuckDuckGo搜索返回0条结果")
    except Exception as e:
        logger.warning("DuckDuckGo搜索失败: %s", e)

    # 3. 全部失败
    logger.error("所有搜索源均不可用, query=%s", query)
    return [{"title": "搜索失败", "body": "搜索服务暂不可用，请检查网络", "href": ""}]


def format_search_results(results: list[dict]) -> str:
    """将搜索结果格式化为可注入prompt的文本"""
    if not results:
        return ""
    parts = ["\n\n# 联网搜索结果\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"\n{i}. {r['title']}\n   {r['body']}\n   来源: {r['href']}\n")
    return "\n".join(parts)
