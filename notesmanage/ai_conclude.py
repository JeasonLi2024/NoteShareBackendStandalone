# 提供调用大模型的接口，输入prompt，返回result
import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv

load_dotenv()
spark_api_token = os.getenv('Spark_Lite_API')

@csrf_exempt
@require_http_methods(["POST"])  # 限制只接受 POST 请求
def spark_lite(request):
    try:
        # 从 POST 请求体中获取 prompt
        data = json.loads(request.body)
        prompt = data.get('prompt', '默认提示')

        url = "https://spark-api-open.xf-yun.com/v1/chat/completions"
        payload = {
            "model": "lite",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {spark_api_token}"
        }

        response = requests.post(url, headers=headers, json=payload, stream=False)
        response.raise_for_status()  # 检查请求是否成功

        result = response.json()
        return JsonResponse({
            'success': True,
            'content': result["choices"][0]["message"]["content"]
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'success': False,
            'error': f'API 请求失败: {str(e)}'
        }, status=500)
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        return JsonResponse({
            'success': False,
            'error': f'数据处理错误: {str(e)}'
        }, status=400)
