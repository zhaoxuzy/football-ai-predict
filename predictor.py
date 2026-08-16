import os
import json
from openai import OpenAI

def predict(matches_json):
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    prompt = f"""你是一名专业的足球竞彩分析师。以下是今日竞彩足球比赛数据（包含赔率、近期战绩、历史交锋、伤停等）：

{json.dumps(matches_json, ensure_ascii=False, indent=2)}

请对每场比赛进行分析，输出 JSON 数组，每项包含以下字段：
- match_id: 比赛编号（字符串）
- league: 联赛名称
- home_team: 主队
- away_team: 客队
- recommendation: 推荐结果，只能是 胜/平/负
- confidence: 置信度，0 到 1 之间的小数
- probability: 预测概率，格式 {{"home": 0.50, "draw": 0.28, "away": 0.22}}
- reasoning: 简短分析理由，50字以内

要求：
1. 只输出 JSON 数组，不要有其他文字
2. 结合赔率、球队状态、历史交锋、伤停信息综合判断
3. 如果某些信息缺失，请注明并在分析中忽略
"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是足球分析专家，只输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        # 尝试解析 JSON
        data = json.loads(content)
        # 如果返回的是包含数组的对象，提取数组
        if isinstance(data, dict) and "predictions" in data:
            return data["predictions"]
        elif isinstance(data, list):
            return data
        else:
            return []
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return []
