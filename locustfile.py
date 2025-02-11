from locust import HttpUser, task, between
import json

class FastAPITestUser(HttpUser):
    wait_time = between(1, 2)  # Simulate real-world traffic
    
    def on_start(self):
        """Initialize storage for moderation task IDs"""
        self.moderation_ids = []

    @task(2)
    def test_moderate_text(self):
        """Load test for text moderation endpoint"""
        response = self.client.post("/api/v1/moderate/text", json={"text": "This is a Test Sentence."})
        if response.status_code == 200:
            try:
                data = response.json()
                if "id" in data:
                    self.moderation_ids.append(data["id"])
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON responses

    @task(1)
    def test_moderate_image(self):
        """Load test for image moderation endpoint"""
        response = self.client.post("/api/v1/moderate/image", 
                                   json={"image_url": "https://static.toiimg.com/thumb/msid-57888835,imgsize-54725,width-400,resizemode-4/57888835.jpg"})
        if response.status_code == 200:
            try:
                data = response.json()
                if "id" in data:
                    self.moderation_ids.append(data["id"])
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON responses

    @task(1)
    def test_get_moderation_result(self):
        """Load test for fetching moderation results using stored IDs"""
        if self.moderation_ids:
            moderation_id = self.moderation_ids.pop(0)  # Get and remove the first stored ID
            self.client.get(f"/api/v1/moderation/{moderation_id}")
    