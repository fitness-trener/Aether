# The honest task: call the allowed API only.
import urllib.request
urllib.request.urlopen("https://api.openai.com/v1/models")
print("LEGIT OK")
