from binance.client import Client
import time


def areWeSyncWithServerTime(api_key, api_secret, recvwindow=5000):
    client = Client(api_key, api_secret)
    areWeSyncWithServerTime(api_key, api_secret, recvwindow, client)


def areWeSyncWithServerTime(api_key, api_secret, recvwindow=5000, client):
    local_time1 = int(time.time() * 1000)
    server_time = client.get_server_time()
    diff1 = server_time['serverTime'] - local_time1
    return diff1 < recvwindow
