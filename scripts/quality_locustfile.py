"""Minimal local-only liveness load profile for FAC-074."""

from locust import HttpUser, between, task


class LocalHealthUser(HttpUser):
    wait_time = between(0.5, 1.0)

    @task
    def readiness(self) -> None:
        self.client.get("/health/live", name="GET /health/live")
