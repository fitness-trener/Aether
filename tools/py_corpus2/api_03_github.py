import requests
import os

def list_repos(org):
    token = os.environ["GITHUB_TOKEN"]
    headers = {"Authorization": "token " + token}
    repos = []
    url = "https://api.github.com/orgs/" + org + "/repos"
    while url:
        resp = requests.get(url, headers=headers)
        repos.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return repos
