import os
import json
import csv
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from openai import OpenAI

# ==================== 第一部分：自动抓取竞彩官网比赛数据 ====================

def fetch_matches_from_sporttery():
    """自动抓取中国竞彩网足球计算器页面，返回比赛列表"""
    url = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry"
    params = {"poolCode": "had", "channel": "c"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.sporttery.cn/jc/jsq/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        match_list = data.get("value", {}).get("matchList", [])
        if not match_list:
            match_list = data.get("data", {}).get("list", [])
        matches = []
        for item in match_list:
            had = item.get("had", {})
            if not had:
                continue
            matches.append({
                "match_id": item.get("matchNumStr", ""),
                "league": item.get("leagueAbbName", ""),
                "home_team": item.get("homeTeamAbbName", ""),
                "away_team": item.get("awayTeamAbbName", ""),
                "had_odds": {
                    "win": float(had.get("h", 0)),
                    "draw": float(had.get("d", 0)),
                    "lose": float(had.get("a", 0)),
                }
            })
        return matches
    except Exception as e:
        print(f"抓取竞彩官网失败: {e}")
        return []

def fetch_matches_from_csv(filepath="data/matches.csv"):
    """备用：从 CSV 文件读取比赛数据"""
    if not os.path.exists(filepath):
        print(f"备用 CSV 文件 {filepath} 不存在")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        matches = []
        for row in reader:
            matches.append({
                "match_id": row["match_id"].strip(),
                "league": row["league"].strip(),
                "home_team": row["home_team"].strip(),
                "away_team": row["away_team"].strip(),
                "had_odds": {
                    "win": float(row["had_win"]),
                    "draw": float(row["had_draw"]),
                    "lose": float(row["had_lose"]),
                }
            })
        return matches

# ==================== 第二部分：获取历史数据（API-Football） ====================

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_FOOTBALL_HOST = "v3.football.api-sports.io"

TEAM_NAME_MAP = {
    "曼城": "Manchester City", "阿森纳": "Arsenal", "利物浦": "Liverpool",
    "切尔西": "Chelsea", "曼联": "Manchester United", "热刺": "Tottenham",
    "皇马": "Real Madrid", "巴萨": "Barcelona", "马竞": "Atletico Madrid",
    "拜仁": "Bayern Munich", "多特蒙德": "Borussia Dortmund",
    "尤文图斯": "Juventus", "国际米兰": "Inter", "AC米兰": "AC Milan",
    "巴黎圣日耳曼": "Paris Saint Germain",
}

def api_football(endpoint, params):
    if not API_FOOTBALL_KEY:
        return {}
    headers = {
        "x-rapidapi-key": API_FOOTBALL_KEY,
        "x-rapidapi-host": API_FOOTBALL_HOST
    }
    try:
        resp = requests.get(f"https://{API_FOOTBALL_HOST}/{endpoint}", headers=headers, params=params, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"API-Football 请求失败: {e}")
        return {}

def search_team(team_name):
    data = api_football("teams", {"search": team_name})
    teams = data.get("response", [])
    if teams:
        return teams[0]["team"]
    return None

def get_team_recent(team_id, last=5):
    data = api_football("fixtures", {"team": team_id, "last": last})
    return [{
        "date": fx["fixture"]["date"][:10],
        "home": fx["teams"]["home"]["name"],
        "away": fx["teams"]["away"]["name"],
        "score": f"{fx['goals']['home']}-{fx['goals']['away']}"
    } for fx in data.get("response", [])]

def get_h2h(team1_id, team2_id, last=5):
    data = api_football("fixtures/headtohead", {"h2h": f"{team1_id}-{team2_id}", "last": last})
    return [{
        "date": fx["fixture"]["date"][:10],
        "home": fx["teams"]["home"]["name"],
        "away": fx["teams"]["away"]["name"],
        "score": f"{fx['goals']['home']}-{fx['goals']['away']}"
    } for fx in data.get("response", [])]

def get_injuries(team_id):
    data = api_football("injuries", {"team": team_id, "season": "2025"})
    return [{
        "player": inj["player"]["name"],
        "type": inj["player"]["type"],
        "reason": inj["player"]["reason"]
    } for inj in data.get("response", [])]

def enrich_match(match):
    home_en = TEAM_NAME_MAP.get(match["home_team"], match["home_team"])
    away_en = TEAM_NAME_MAP.get(match["away_team"], match["away_team"])
    home_team = search_team(home_en)
    away_team = search_team(away_en)
    if home_team and away_team:
        home_id = home_team["id"]
        away_id = away_team["id"]
        match["home_recent"] = get_team_recent(home_id)
        match["away_recent"] = get_team_recent(away_id)
        match["h2h"] = get_h2h(home_id, away_id)
        match["injuries"] = {
            "home": get_injuries(home_id),
            "away": get_injuries(away_id)
        }
    else:
        match["note"] = "历史数据不可用（未找到球队）"
    return match

# ==================== 第三部分：调用 DeepSeek ====================

SYSTEM_PROMPT = """你是一名拥有二十年经验的职业足球量化竞彩分析师，专精于市场定价偏差挖掘。请针对以下比赛完成决策推演。

【强制执行规则】
1. 矛盾驱动：必须从数据中寻找矛盾，在矛盾中构建逻辑，在逻辑上形成预测，且全程逻辑自洽。
2. 严禁编造：只使用已提供或可验证的数据；数据缺失必须标注【数据缺失】并评估对结论的影响，不得虚构。
3. 逐场独立：必须对每一场比赛单独执行完整分析，不得跳过、合并、简化或省略。
4. 强制输出：不必展示六步分析过程，但必须严格按照指定格式输出汇总表、每场核心预测逻辑和全局风险总结。

【比赛数据】
数据由系统提供，可能包含：胜平负赔率、球队近期战绩、历史交锋、伤停名单。其他数据（如xG、盘口时间线、天气、裁判风格等）未提供，请标注【数据缺失】并基于可用数据继续分析，不得编造。

【输出格式】
完成推演后，必须输出以下三部分：

1. **汇总表**（Markdown表格，每场比赛一行）
| 场次 | 比赛 | 胜平负 | 让球胜平负 | 半全场① | 半全场② | 比分① | 比分② | 比分③ | 总进球① | 总进球② | 信心 |
（信心可用高/中/低，若各玩法信心不同可注明）

2. **每场核心预测逻辑**（每场不少于180字）
必须围绕“矛盾-推理-结论”链条展开，结构：
核心矛盾：……
由此推断：……
最终结论：
**胜平负**：……
**半全场**：……
**比分**（不少于2个）：……
末尾单独标注【综合置信度】，格式：**综合置信度：高/中/低（或百分比）**，并简要说明依据。

3. **全局风险总结**（一段话）

【自检清单】
- 每场是否都有独立完整分析？
- 汇总表是否无遗漏、无格式错误？
- 每场逻辑段落是否≥180字且围绕矛盾展开？
- 每场是否明确写出胜平负、半全场、比分（≥2个）的逻辑？
- 每场是否标注综合置信度及依据？
- 是否没有编造任何信息？
- 是否逻辑自洽？
若未满足，输出视为无效，必须重新生成。"""

def predict_with_deepseek(matches):
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )
    user_prompt = json.dumps(matches, ensure_ascii=False, indent=2)
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=4096
        )
        content = resp.choices[0].message.content
        return content.strip()
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return ""

# ==================== 第四部分：推送钉钉 ====================

def send_dingtalk(markdown_text):
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    if not webhook or not secret:
        print("缺少钉钉配置")
        return
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "今日竞彩 AI 预测",
            "text": markdown_text
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"钉钉发送状态: {r.status_code}, {r.text}")
    except Exception as e:
        print(f"钉钉发送失败: {e}")

# ==================== 主流程 ====================

def main():
    print("【1/4】获取比赛数据...")
    matches = fetch_matches_from_sporttery()
    if not matches:
        print("自动抓取失败，尝试备用 CSV...")
        matches = fetch_matches_from_csv("data/matches.csv")
    if not matches:
        msg = "## 今日竞彩 AI 预测\n\n获取比赛数据失败，请检查日志。"
        send_dingtalk(msg)
        print("无比赛数据，程序结束")
        return
    # 限制最多5场
    matches = matches[:5]
    print(f"共 {len(matches)} 场比赛")

    print("【2/4】补充历史数据...")
    enriched = [enrich_match(m) for m in matches]

    print("【3/4】调用 DeepSeek 预测...")
    result = predict_with_deepseek(enriched)
    if not result:
        msg = "## 今日竞彩 AI 预测\n\nDeepSeek 预测失败，请检查日志。"
        send_dingtalk(msg)
        print("预测失败")
        return

    print("【4/4】推送结果到钉钉...")
    send_dingtalk(result)
    print("流程结束")

if __name__ == "__main__":
    main()
