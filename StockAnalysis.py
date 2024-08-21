import json
import os
import requests

API_KEY = os.getenv('QUICKFS_API_KEY')

BASE_URL = 'https://public-api.quickfs.net/v1'

# Headers including the API Key
headers = {
    'X-QFS-API-Key': API_KEY
}

ticker = "AAPL"


def call_api_single(ticker, metric, period):
    url = f"{BASE_URL}/data/{ticker}/{metric}?period=FY-{period - 1}:FY"

    response = requests.get(url, headers=headers)

    return response.json()


revenue = call_api_single(ticker, "revenue", 10)["data"]

