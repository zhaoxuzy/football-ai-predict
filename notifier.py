import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests

def send_dingtalk(markdown_text):
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")

    if not webhook or not secret:
        print("钉钉 Webhook 或 Secret 未设置，跳过发送")
        return

    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    url = f"{webhook}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "今日竞彩足球 AI 预测",
            "text": markdown_text
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"钉钉发送状态: {resp.status_code}, {resp.text}")
    except Exception as e:
        print(f"钉钉发送失败: {e}")
