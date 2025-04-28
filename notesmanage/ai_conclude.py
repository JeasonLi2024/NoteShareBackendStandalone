import os, json, requests
from dotenv import load_dotenv

load_dotenv()
SPARK_API_TOKEN = os.getenv('Spark_Lite_API')

class SparkLiteClient:
    """封装对 Spark Lite API 的调用"""
    API_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"

    @classmethod
    def summarize(cls, prompt: str) -> str:
        payload = {
            "model": "lite",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SPARK_API_TOKEN}"
        }
        resp = requests.post(cls.API_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # 直接抛异常让调用方处理 KeyError / JSON 错误
        return data["choices"][0]["message"]["content"]
