import requests

class UserAPIClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "Bearer " + token})

    def get_user(self, user_id):
        resp = self.session.get(self.base_url + "/users/" + str(user_id))
        resp.raise_for_status()
        return resp.json()

    def create_user(self, payload):
        resp = self.session.post(self.base_url + "/users", json=payload)
        return resp.json()
