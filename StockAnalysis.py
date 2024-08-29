import json
import os
import requests

API_KEY = os.getenv('QUICKFS_API_KEY')

BASE_URL = 'https://public-api.quickfs.net/v1/data/'

# Headers including the API Key
headers = {
    'X-QFS-API-Key': API_KEY
}

ticker = "AAPL"


def call_api(ticker, metrics, period):
    url = f"{BASE_URL}/data/{ticker}/{metrics}?period=FY-{period - 1}:FY"

    response = requests.get(url, headers=headers)

    return response.json()


def call_api_batch(query):
    # Construct the URL with the batch query
    url = f"{BASE_URL}/batch?keys={query}"

    # Make the API request
    response = requests.get(url, headers=headers)
    print(response)
    # Return the JSON response
    return response
