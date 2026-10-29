"""Locust 壓力測試：搜尋 100 位併發使用者；同時段搶訂。

執行（系統需先啟動並已 seed）：
    locust -f tests/load/locustfile.py --host http://localhost:8080 --users 100 --spawn-rate 20
"""

import random
from datetime import UTC, datetime, timedelta

from locust import HttpUser, between, task

PASSWORD = "Passw0rd!"


class Searcher(HttpUser):
    """搜尋與瀏覽（NFR-04：95 百分位 < 500 ms）。"""

    wait_time = between(0.5, 2)

    @task(5)
    def search(self):
        params = random.choice(
            [{"city": "桃園市"}, {"people": 8}, {"max_price": 500}, {"sort": "price_asc"}, {}]
        )
        self.client.get("/api/v1/spaces", params=params, name="/spaces")

    @task(2)
    def detail_and_slots(self):
        space_id = random.randint(1, 9)
        self.client.get(f"/api/v1/spaces/{space_id}", name="/spaces/:id")
        day = (datetime.now(UTC) + timedelta(days=random.randint(1, 30))).date()
        self.client.get(
            f"/api/v1/spaces/{space_id}/availability",
            params={"date": day.isoformat()},
            name="/spaces/:id/availability",
        )


class SlotRacer(HttpUser):
    """同時段搶訂：所有使用者嘗試同一個時段，預期只有 1 筆成功，其餘為 409 SLOT_TAKEN。"""

    wait_time = between(1, 3)
    weight = 1

    def on_start(self):
        self.csrf = self.client.get("/api/v1/auth/csrf").json()["csrf_token"]
        self.client.post(
            "/api/v1/auth/login",
            json={
                "email": random.choice(["user1@judian.local", "user2@judian.local"]),
                "password": PASSWORD,
            },
            headers={"X-CSRFToken": self.csrf},
        )
        self.csrf = self.client.get("/api/v1/auth/csrf").json()["csrf_token"]

    @task
    def race(self):
        start = (datetime.now(UTC) + timedelta(days=45)).replace(
            hour=2, minute=0, second=0, microsecond=0
        )
        body = {
            "space_id": 4,
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=2)).isoformat(),
            "attendees": 2,
        }
        with self.client.post(
            "/api/v1/bookings",
            json=body,
            headers={"X-CSRFToken": self.csrf},
            name="/bookings (race)",
            catch_response=True,
        ) as res:
            if res.status_code in (201, 409):
                res.success()
            else:
                res.failure(f"非預期狀態 {res.status_code}")
            if res.status_code == 201:
                booking_id = res.json()["booking_id"]
                self.client.post(
                    f"/api/v1/bookings/{booking_id}/cancel",
                    headers={"X-CSRFToken": self.csrf},
                    name="/bookings/:id/cancel",
                )
