import requests
import json


class CompletionClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def generate_json_completion(self, prompt: str, stream: bool = False, temperature: float = 1.0):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": stream,
            "options": {
                "temperature": temperature
            }
        }
        response = requests.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        return json.loads(response.json().get("response"))

    def generate_text_completion(self, prompt: str, stream: bool = False, temperature: float = 1.0):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature
            }
        }
        response = requests.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        return response.json().get("response")
