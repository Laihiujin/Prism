import requests
import json
import time

BASE_URL = "http://127.0.0.1:7000/api/v1"

def test_create_campaign():
    print("\n=== Testing Create Campaign ===")
    
    # 1. Get Accounts (to use valid IDs)
    try:
        res = requests.get(f"{BASE_URL}/accounts/?limit=10")
        if res.status_code != 200:
            print(f"Failed to get accounts: {res.text}")
            return
        accounts = res.json().get("items", [])
        if not accounts:
            print("No accounts found, skipping test")
            return
        
        account_ids = [acc.get('account_id') or acc.get('id') for acc in accounts[:2]]
        platforms = list(set([acc.get('platform') for acc in accounts[:2]]))
        
        # 2. Get Materials (Mock)
        material_ids = ["mat_001", "mat_002", "mat_003"] 
        
        payload = {
            "name": f"Test Campaign {int(time.time())}",
            "platforms": platforms,
            "account_ids": account_ids,
            "material_ids": material_ids,
            "schedule_type": "immediate",
            "remark": "Automated test"
        }
        
        print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        res = requests.post(f"{BASE_URL}/campaigns/create", json=payload)
        print(f"Create Response: {res.status_code} - {res.text}")
        
        if res.status_code == 200:
            data = res.json()
            campaign_id = data['result']['campaign_id']
            print(f"Created Campaign ID: {campaign_id}")
            return campaign_id
    except Exception as e:
        print(f"Error: {e}")
    return None

def test_get_campaign(campaign_id):
    print(f"\n=== Testing Get Campaign {campaign_id} ===")
    res = requests.get(f"{BASE_URL}/campaigns/{campaign_id}")
    print(f"Get Response: {res.status_code}")
    if res.status_code == 200:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))

def test_get_campaign_tasks(campaign_id):
    print(f"\n=== Testing Get Campaign Tasks {campaign_id} ===")
    res = requests.get(f"{BASE_URL}/campaigns/{campaign_id}/tasks")
    print(f"Tasks Response: {res.status_code}")
    if res.status_code == 200:
        tasks = res.json()['result']['items']
        print(f"Found {len(tasks)} tasks")
        if tasks:
            print(f"Sample Task: {tasks[0]}")

if __name__ == "__main__":
    cid = test_create_campaign()
    if cid:
        test_get_campaign(cid)
        test_get_campaign_tasks(cid)
