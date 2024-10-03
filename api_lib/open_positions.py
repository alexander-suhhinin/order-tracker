from hashlib import sha256
import hmac
import os
import pandas as pd
import requests
import time
from dotenv import load_dotenv
from utils.log_config import logging_config

log = logging_config()
load_dotenv()
APIURL = os.getenv('APIURL')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
POST='POST'
GET='GET'

def get_open_positions_demo():
    payload = {}
    path = '/openApi/swap/v2/user/positions'
    method = GET
    paramsMap = {
        "startTime": int((pd.Timestamp.now() - pd.Timedelta(days=1)).timestamp() * 1000),
        "endTime": int(pd.Timestamp.now().timestamp() * 1000),
        "limit": "1000",
        "timestamp": str(int(time.time() * 1000))
    }
    paramsStr = parseParam(paramsMap)
    try:
        response = send_request_demo(method, path, paramsStr, payload)
        df = pd.DataFrame(response['data'])
        return df
    except:
        log.error("Error retrieving income data")
        return pd.DataFrame([])
    

def close_position(position):
    positionId = position['positionId']
    symbol = position['symbol']
    position_side = position['positionSide']
    positionAmt = position['positionAmt']
    payload = {}
    path = '/openApi/swap/v1/trade/closePosition'
    method = POST
    paramsMap = {
        "positionId": positionId
    }
    paramsStr = parseParam(paramsMap)
    log.info(f'Close position {symbol}, {position_side}, {positionAmt}')

    response = send_request_demo(method, path, paramsStr, payload)
    if (response['code'] != 0):
        log.error(response)
    return response       

def get_full_orders(limit=500):
    payload = {}
    path = '/openApi/swap/v1/trade/fullOrder'
    method = GET
    paramsMap = {
        "timestamp": str(int(time.time() * 1000)),
        "limit": limit
    }
    paramsStr = parseParam(paramsMap)

    orders = send_request_demo(method, path, paramsStr, payload)
    if (orders['code'] != 0):
        log.error(orders)
    return orders

def cancel_and_set_new(symbol, position_side, amount, sl_price, cancel_order):
    payload = {}
    path = '/openApi/swap/v1/trade/cancelReplace'
    method = POST
    paramsMap = {
        "cancelReplaceMode": "STOP_ON_FAILURE",
        "cancelOrderId": cancel_order['orderId'],
        "cancelRestrictions": "ONLY_NEW",
        "symbol": symbol,
        "side": "SELL" if position_side=="SHORT" else "BUY",
        "positionSide": position_side,
        "type": cancel_order['type'],
        "quantity": amount,
        "stopPrice": sl_price
    }
    paramsStr = parseParam(paramsMap)
    log.info(f'Replace STOP order {symbol}, {position_side}, {amount}, SL: {sl_price} ')

    response = send_request_demo(method, path, paramsStr, payload)
    if (response['code'] != 0):
        log.error(response)
    return response     

def create_stop_order(symbol, position_side, amount, sl_price):

    payload = {}
    path = '/openApi/swap/v2/trade/order'
    method = POST
    paramsMap = {
        "symbol": symbol,
        "side": "BUY" if position_side == "SHORT" else "SELL",
        "positionSide": position_side,
        "type": "STOP_MARKET",
        "quantity": amount,
        "stopPrice": sl_price
    }
    paramsStr = parseParam(paramsMap)
    log.info(f'Create STOP order {symbol}, {position_side}, {amount}, SL: {sl_price} ')

    response = send_request_demo(method, path, paramsStr, payload)

    if (response['code'] != 0):
        log.error(response)
    return response    

def get_price(symbol):
    payload = {}
    path = '/openApi/swap/v1/ticker/price'
    method = GET

    paramsMap = {
        "symbol": symbol,
        "timestamp": str(int(time.time() * 1000))
    }

    paramsStr = parseParam(paramsMap)
    try:
        response = send_request_demo(method, path, paramsStr, payload)
        return float(response['data']['price'])
    except Exception:
        return 0

def send_request_demo(method, path, urlpa, payload):
    url = "%s%s?%s&signature=%s" % (APIURL, path, urlpa, get_sign(API_SECRET, urlpa))
    headers = {
        'X-BX-APIKEY': API_KEY,
    }
    response = requests.request(method, url, headers=headers, data=payload)
    return response.json()

def get_sign(api_secret, payload):
    signature = hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), digestmod=sha256).hexdigest()
    
    return signature

def parseParam(paramsMap):
    sortedKeys = sorted(paramsMap)
    paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
    if paramsStr != "": 
     return paramsStr+"&timestamp="+str(int(time.time() * 1000))
    else:
     return paramsStr+"timestamp="+str(int(time.time() * 1000))