import requests
import urllib3
urllib3.disable_warnings()

r = requests.get("https://127.0.0.1:2999/liveclientdata/allgamedata", timeout=5, verify=False)
data = r.json()

print(f"金币: {data['activePlayer']['currentGold']}") # TFT中无法获取
print(f"等级: {data['activePlayer']['level']}")