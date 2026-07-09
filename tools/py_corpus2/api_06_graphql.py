import httpx

class GraphQLClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.client = httpx.Client()

    def query(self, document, variables=None):
        resp = self.client.post(self.endpoint, json={"query": document, "variables": variables or {}})
        payload = resp.json()
        return payload["data"]
