from locust import HttpUser, TaskSet, task, between
import random

# 加载所有 token
with open("loadtest_tokens.txt", "r") as f:
    tokens = [line.strip() for line in f if line.strip()]

class UserBehavior(TaskSet):
    def on_start(self):
        # 随机选择一个 token
        self.token = random.choice(tokens)

    @task(5)
    def list_notes(self):
        with self.client.get(
                "/notesmanage/notes/Top/",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
                catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"错误码: {response.status_code}, 内容: {response.text}")
            else:
                # 成功
                response.success()

    # @task(1)
    # def publish_note(self):
    #     self.client.post("/api/notes/publish/", json={"draft_id": 1},
    #                      headers={"Authorization": f"Bearer {self.token}"})

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 3)
