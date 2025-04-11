# 提供调用大模型的接口，输入prompt，返回result
import os
import requests

from dotenv import load_dotenv

load_dotenv()
spark_api_token=os.getenv('Spark_Lite_API')

def spark_lite(prompt):
    url = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    data = {
        "model": "lite",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }
    header = {
        "Authorization": f"Bearer {spark_api_token}"
    }
    response = requests.post(url, headers=header, json=data, stream=False)

    return response.json()["choices"][0]["message"]["content"]
