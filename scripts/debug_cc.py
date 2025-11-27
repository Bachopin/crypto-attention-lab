
import requests
import json

def test_cryptocompare():
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    
    # Test 1: General fetch
    print("--- Test 1: General Fetch ---")
    params = {"lang": "EN"}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        print(f"Status: {data.get('Message')}")
        print(f"Count: {len(data.get('Data', []))}")
        if data.get('Data'):
            print(f"Sample: {data['Data'][0]['title']}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Category Fetch (BTC)
    print("\n--- Test 2: Category Fetch (BTC) ---")
    params = {"lang": "EN", "categories": "BTC"}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        print(f"Status: {data.get('Message')}")
        print(f"Count: {len(data.get('Data', []))}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 3: Category Fetch (ZEC)
    print("\n--- Test 3: Category Fetch (ZEC) ---")
    params = {"lang": "EN", "categories": "ZEC"}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        print(f"Status: {data.get('Message')}")
        print(f"Count: {len(data.get('Data', []))}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_cryptocompare()
