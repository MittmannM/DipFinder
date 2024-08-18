import json
import os
import requests

API_KEY = os.getenv('QUICKFS_API_KEY')

BASE_URL = 'https://public-api.quickfs.net/v1'

# Headers including the API Key
headers = {
    'X-QFS-API-Key': API_KEY
}

ticker = "O"


def call_api(ticker, metric, call_single_stock):

    if call_single_stock:
        url = f"{BASE_URL}/data/{ticker}/{metric}?period=FY-0:FY"
    else:
        url = f"{BASE_URL}/data/all-data{ticker}"

    response = requests.get(url, headers=headers)
    return response.json()


def calc_fcf_yield_myself(ticker):

    fcf = call_api(ticker, "fcf", True)["data"][0]
    market_cap = call_api(ticker, "market_cap", True)["data"][0]

    print(fcf, market_cap)

    return (fcf / market_cap) * 100


def calc_fcf_yield_metric(ticker):

    price_to_fcf = call_api(ticker, "price_to_fcf", True)["data"][0]

    return round((1/price_to_fcf) * 100, 2)


#def calc_pe_ratio_myself(ticker):




def calc_pe_ratio_metric(ticker):

    pe_ratio = call_api(ticker, "price_to_earnings", True)

    return pe_ratio


print(calc_fcf_yield_myself(ticker))
print(calc_fcf_yield_metric(ticker))
print(calc_pe_ratio_metric(ticker))