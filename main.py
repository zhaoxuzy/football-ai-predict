import json
import os
from fetcher import fetch_matches_from_csv
from stats_fetcher import (
    search_team, get_team_recent, get_team_stats,
    get_h2h, get_injuries
)
from predictor import predict
from notifier import send_dingtalk

# 加载球队中文名→英文名映射（如果存在）
def load_name_map():
    map_file = "team_name_map.json"
    if os.path.exists(map_file):
        with open(map_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def enrich_match(match, name_map):
    """为单场比赛补充历史数据"""
    home_cn = match["home_team"]
    away_cn = match["away_team"]

    # 将中文名转换为英文名（如果映射表里有）
    home_en = name_map.get(home_cn, home_cn)
    away_en = name_map.get(away_cn, away_cn)

    # 搜索球队 ID
    home_team = search_team(home_en)
    away_team = search_team(away_en)

    enriched = match.copy()

    if home_team and away_team:
        home_id = home_team["id"]
        away_id = away_team["id"]

        # 近期战绩
        enriched["home_recent"] = get_team_recent(home_id)
        enriched["away_recent"] = get_team_recent(away_id)

        # 赛季统计（这里需要联赛 ID，我们暂时不获取，后续可扩展）
        # 可以通过 match["league"] 映射到 API-Football 的 league_id
        league_id = get_league_id(match["league"])
        season = "2025"
        enriched["home_stats"] = get_team_stats(home_id, league_id, season) if league_id else {}
        enriched["away_stats"] = get_team_stats(away_id, league_id, season) if league_id else {}

        # 历史交锋
        enriched["h2h"] = get_h2h(home_id, away_id)

        # 伤停
        enriched["injuries"] = {
            "home": get_injuries(home_id),
            "away": get_injuries(away_id)
        }
    else:
        enriched["note"] = "未找到球队数据，可能因中文名映射缺失"

    return enriched

def get_league_id(league_name):
    """根据竞彩联赛名称映射到 API-Football 的 league_id"""
    # 这里只列出常见联赛，用户可根据需要扩展
    mapping = {
        "英超": 39,
        "西甲": 140,
        "意甲": 135,
        "德甲": 78,
        "法甲": 61,
        "欧冠": 2,
        "欧联": 3,
        "日职": 98,
        "韩K联": 292,
        "澳超": 188,
        "瑞典超": 113,
        "挪超": 103,
        "美职联": 253,
        "巴甲": 71,
    }
    return mapping.get(league_name)

def format_result(predictions):
    """将预测结果格式化为钉钉 Markdown 文本"""
    if not predictions:
        return "## 今日竞彩足球 AI 预测\n\n暂无预测结果，请检查日志。"
    text = "## 今日竞彩足球 AI 预测\n\n"
    for p in predictions:
        text += f"**{p.get('match_id', '')} {p.get('league', '')} {p.get('home_team', '')} vs {p.get('away_team', '')}**\n"
        text += f"- 推荐：**{p.get('recommendation', '未知')}**\n"
        text += f"- 置信度：{p.get('confidence', 0):.2f}\n"
        prob = p.get('probability', {})
        text += f"- 预测概率：主胜 {prob.get('home', 0):.2f} / 平 {prob.get('draw', 0):.2f} / 客胜 {prob.get('away', 0):.2f}\n"
        text += f"- 理由：{p.get('reasoning', '无')}\n\n"
    return text

def main():
    print("开始获取比赛数据...")
    matches = fetch_matches_from_csv("data/matches.csv")
    if not matches:
        print("没有比赛数据，请检查 data/matches.csv")
        return

    print(f"共 {len(matches)} 场比赛，开始补充历史数据...")
    name_map = load_name_map()
    enriched_matches = [enrich_match(m, name_map) for m in matches]

    print("开始调用 DeepSeek 预测...")
    predictions = predict(enriched_matches)

    print("准备发送钉钉消息...")
    markdown = format_result(predictions)
    send_dingtalk(markdown)

    print("流程结束")

if __name__ == "__main__":
    main()
