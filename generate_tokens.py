#!/usr/bin/env python3
# generate_tokens.py

#!/usr/bin/env python3
import requests

# ——————————————————————————————————————————————————————————————————————————
# 配置部分
BASE_URL = "http://127.0.0.1:8000"
# 注意：你的登录路由就是 /login/
LOGIN_URL = f"{BASE_URL}/login/"

USER_PREFIX = "loadtest"       # 用户名前缀，比如 loadtest1, loadtest2 ...
PASSWORD    = "loadtestpass"   # 这些测试账号的统一密码
COUNT       = 500               # 共生成多少个 token
OUT_FILE    = "loadtest_tokens.txt"
# ——————————————————————————————————————————————————————————————————————————

def get_token(username: str, password: str) -> str:
    """
    调用你的 /login/ 接口，返回 access token。
    LoginView 返回格式：
      {
        "code": 200,
        "message": "success",
        "data": {
          "refresh": "...",
          "access": "...",
          "user_id": 123
        }
      }
    """
    resp = requests.post(
        LOGIN_URL,
        json={
            "username_or_email_or_phone": username,
            "password": password
        },
        timeout=5
    )
    # 如果非 200 会直接抛出异常
    resp.raise_for_status()

    payload = resp.json()
    if payload.get("code") != 200:
        raise ValueError(f"登录失败: {payload.get('message') or payload}")

    data = payload.get("data", {})
    access = data.get("access")
    if not access:
        raise ValueError(f"No access token in response: {payload}")

    return access

def main():
    tokens = []
    for i in range(1, COUNT + 1):
        username = f"{USER_PREFIX}{i}"
        try:
            token = get_token(username, PASSWORD)
            tokens.append(token)
            print(f"[{i}] 用户 {username} 拿到 access token: {token[:8]}…")
        except Exception as e:
            print(f"[{i}] 用户 {username} 登录失败: {e}")

    # 写入文件
    with open(OUT_FILE, "w") as f:
        for t in tokens:
            f.write(t + "\n")
    print(f"完成：已写入 {len(tokens)} 个 token 到 {OUT_FILE}")

if __name__ == "__main__":
    main()
