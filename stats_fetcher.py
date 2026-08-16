import os
import requests

API_KEY = os.getenv("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"

def _api_get(endpoint, params):
    if not API_KEY:
        print("未设置 API_FOOTBALL_KEY，跳过历史数据获取")
        return {}
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST
    }
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API 请求失败: {e}")
        return {}

def search_team(team_name):
    """根据英文名搜索球队，返回球队信息字典（含 id）"""
    data = _api_get("teams", {"search": team_name})
    teams = data.get("response", [])
    if teams:
        # 取第一个结果，实际使用时可以精确匹配
        return teams[0]["team"]
    return None

def get_team_recent(team_id, last=5):
    """获取最近 N 场比赛"""
    data = _api_get("fixtures", {"team": team_id, "last": last})
    fixtures = data.get("response", [])
    result = []
    for fx in fixtures:
        result.append({
            "date": fx["fixture"]["date"][:10],
            "home": fx["teams"]["home"]["name"],
            "away": fx["teams"]["away"]["name"],
            "score": f"{fx['goals']['home']}-{fx['goals']['away']}"
        })
    return result

def get_team_stats(team_id, league_id, season="2025"):
    """获取球队赛季统计（胜率、场均进球、失球）"""
    data = _api_get("teams/statistics", {
        "team": team_id,
        "league": league_id,
        "season": season
    })
    stats = data.get("response", {})
    if not stats:
        return {}
    fixtures = stats.get("fixtures", {})
    played = int(fixtures.get("played", {}).get("total", 0))
    wins = int(fixtures.get("wins", {}).get("total", 0))
    goals_for = float(stats.get("goals", {}).get("for", {}).get("average", {}).get("total", 0))
    goals_against = float(stats.get("goals", {}).get("against", {}).get("average", {}).get("total", 0))
    return {
        "win_rate": wins / played if played > 0 else 0,
        "avg_goals_scored": goals_for,
        "avg_goals_conceded": goals_against
    }

def get_h2h(team1_id, team2_id, last=5):
    """获取双方历史交锋"""
    data = _api_get("fixtures/headtohead", {
        "h2h": f"{team1_id}-{team2_id}",
        "last": last
    })
    fixtures = data.get("response", [])
    result = []
    for fx in fixtures:
        result.append({
            "date": fx["fixture"]["date"][:10],
            "home": fx["teams"]["home"]["name"],
            "away": fx["teams"]["away"]["name"],
            "score": f"{fx['goals']['home']}-{fx['goals']['away']}"
        })
    return result

def get_injuries(team_id, season="2025"):
    """获取球队伤停名单"""
    data = _api_get("injuries", {"team": team_id, "season": season})
    injuries = data.get("response", [])
    return [
        {
            "player": inj["player"]["name"],
            "type": inj["player"]["type"],  # "injury" 或 "suspension"
            "reason": inj["player"]["reason"]
        }
        for inj in injuries
    ]
