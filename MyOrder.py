#!/usr/bin/python
from gevent import thread

TESTING = False
ACTIVE = False

import json
from binance.client import Client
from position import Position
import sys
from twisted.internet import reactor
from binance.websockets import BinanceSocketManager
from bcolors import bcolors
import websocket
from threading import Thread
import asyncio

# import websockets

# client = Client(api_key, api_secret)


client = Client("",
                "")

bm = BinanceSocketManager(client)

priceFormat = '{:1.8f}'

lastPrice = 0.0

symbolOrig = sys.argv[1]
# risk = float(sys.argv[2])
qty = float(sys.argv[2])
loss = float(sys.argv[3])
profit = float(sys.argv[4])
side = sys.argv[5]

commision = 0.0005
assets = symbolOrig.split('/')
assetMajor = assets[1]
assetMinor = assets[0]
symbol = assetMinor + assetMajor
start = "1 Dec, 2017"
end = "1 feb, 2018"
interval = Client.KLINE_INTERVAL_1MINUTE

trading = True

# klines = client.get_historical_klines(symbol, interval, start, end)


exchangeInfo = client.get_exchange_info()

# Lets get the rules of the game
symbolInfo = client.get_symbol_info(symbol)
tickSize = symbolInfo['filters'][0]['tickSize']
minQty = symbolInfo['filters'][1]['minQty']
minNotional = symbolInfo['filters'][2]['minNotional']
stepSize = float(symbolInfo['filters'][1]['stepSize'])

# Lets get our assets free balances
assetMajorBalance = float(client.get_asset_balance(assetMajor)['free'])
assetMinorBalance = float(client.get_asset_balance(assetMinor)['free'])
if (assetMajor != 'BNB'):
    bnbBalance = float(client.get_asset_balance('BNB')['free'])

# Lets decide our entry price
# for now lets meet the market at the middle ask/bid price
orderbook = client.get_order_book(symbol=symbol, limit=5)
price = round((float(orderbook['bids'][0][0]) + float(orderbook['asks'][0][0])) / 2, 8)
if (assetMajor != 'BNB'):
    bnbTicker = client.get_symbol_ticker(symbol='BNB' + assetMajor)
    bnbPrice = round(float(bnbTicker['price']), 8)
    minorBnb = price / bnbPrice

# Lets decide how much we bid this time and if we have enough balance for that
# qty = max({float(assetMajorBalance)*float(risk)/price,float(minNotional)/price})
qty = max({qty, float(minNotional) / price})
adj = 0 if round(qty % stepSize) == 0 else 1 - round(qty % stepSize)
qty = qty + adj

if ACTIVE and ((side == 'LONG' and assetMajorBalance < qty * price) or (side == 'SHORT' and assetMinorBalance <= qty)):
    print('not enough balance')
    exit(1)

# Lets decide our stop and profit targets
if side == 'LONG':
    lossPrice = round(price * (1 - loss), 8)
    profitPrice = round(price * (1 + profit), 8)
elif side == 'SHORT':
    lossPrice = round(price * (1 + loss), 8)
    profitPrice = round(price * (1 - profit), 8)

print(bcolors.BOLD + '{:1.8f}{}  {:1.8f}{}'.format(assetMajorBalance, assetMajor, assetMinorBalance,
                                                   assetMinor) + bcolors.ENDC)
print(side + ' Price:{:1.8f} Loss:{:1.8f} Profit:{:1.8f}'.format(price, lossPrice, profitPrice))

MyPosition = Position(symbol, price, qty, lossPrice, profitPrice)

order = {}
if TESTING or not ACTIVE:
    order = client.create_test_order(symbol=MyPosition.symbol,
                                     side=Client.SIDE_BUY if side == 'LONG' else Client.SIDE_SELL,
                                     type=Client.ORDER_TYPE_LIMIT,
                                     timeInForce=Client.TIME_IN_FORCE_GTC,
                                     quantity=MyPosition.entryQty,
                                     price='{:1.8f}'.format(MyPosition.entryPrice)
                                     )
else:
    order = client.create_order(symbol=MyPosition.symbol,
                                side=Client.SIDE_BUY if side == 'LONG' else Client.SIDE_SELL,
                                type=Client.ORDER_TYPE_LIMIT,
                                timeInForce=Client.TIME_IN_FORCE_GTC,
                                quantity=MyPosition.entryQty,
                                price='{:1.8f}'.format(MyPosition.entryPrice)
                                )
# orderId = order['orderId']
print(order)
assetMajorBalance = assetMajorBalance - MyPosition.entryQty * price if side == 'LONG' else assetMajorBalance + MyPosition.entryQty * price
assetMinorBalance = assetMinorBalance + MyPosition.entryQty if side == 'LONG' else assetMinorBalance - MyPosition.entryQty


#####  defs ####

def proces_accountInfo(accountInfo):
    global assetMajorBalance, assetMinorBalance
    for asset in accountInfo['B']:
        f = float(asset['f'])
        if (asset['a'] == assetMajor):
            assetMajorBalance = float(f)
        elif (asset['a'] == assetMinor):
            assetMinorBalance = float(f)

    print(bcolors.BOLD + '{:1.8f}{}  {:1.8f}{}'.format(assetMajorBalance, assetMajor, assetMinorBalance,
                                                       assetMinor) + bcolors.ENDC)


def process_executionReport(executionReport):
    global assetMajorBalance, assetMinorBalance
    print(executionReport)
    if executionReport['s'] == symbol:
        if executionReport['S'] == 'BUY':
            assetMajorBalance -= float(executionReport['l']) * float(executionReport['p'])
            assetMinorBalance += float(executionReport['l'])
        else:
            assetMajorBalance += float(executionReport['l']) * float(executionReport['p'])
            assetMinorBalance -= float(executionReport['l'])


def process_kline(kline):
    if TESTING:
        print(kline)
    global trading
    closePosition = False
    if trading:
        global lastPrice
        global assetMajorBalance
        global assetMinorBalance
        global side
        close = float(kline['k']['c'])

        if (close != lastPrice):
            lastPrice = close
        if side == 'LONG':
            if MyPosition.stopLoss > lastPrice:
                closePosition = True
                trading = False
                print(bcolors.FAIL + 'loss at ' + priceFormat.format(close) + bcolors.ENDC)
            elif MyPosition.takeProfit < lastPrice:
                closePosition = True
                trading = False
                print(bcolors.OKBLUE + 'profit at ' + priceFormat.format(close) + bcolors.ENDC)
        else:
            if MyPosition.takeProfit > lastPrice:
                closePosition = True
                trading = False
                print(bcolors.OKBLUE + 'profit at ' + priceFormat.format(close) + bcolors.ENDC)
            elif MyPosition.stopLoss < lastPrice:
                closePosition = True
                trading = False
                print(bcolors.FAIL + 'loss at ' + priceFormat.format(close) + bcolors.ENDC)

    if closePosition:
        maxbal = 0
        newSide=side;
        if side == 'SHORT':
            maxbal = assetMajorBalance / close
            newSide = 'LONG'
        elif side == 'LONG':
            maxbal = assetMinorBalance
            newSide = 'SHORT'
        qty = min({maxbal, MyPosition.entryQty})
        qty = qty - qty % stepSize
        if TESTING:
            order = client.create_test_order(symbol=MyPosition.symbol,
                                             side=Client.SIDE_SELL if side == 'LONG' else Client.SIDE_BUY,
                                             type=Client.ORDER_TYPE_MARKET,
                                             quantity=qty
                                             )
        else:
            order = client.create_order(symbol=MyPosition.symbol,
                                        side=Client.SIDE_SELL if side == 'LONG' else Client.SIDE_BUY,
                                        type=Client.ORDER_TYPE_MARKET,
                                        quantity=qty
                                        )
        print(order)
        if order != {}:
            bm.close()
            reactor.stop()
            import subprocess as sp
            process = sp.Popen('MyOrder.py {} {} {} {} {}'.format(symbolOrig, qty, loss, profit, newSide), shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
            out, err = process.communicate()  # The output and error streams.


# start trade websocket

def process_message(msg):
    msgType = msg['e']
    if msgType == 'kline':
        process_kline(msg)
    elif msgType == 'outboundAccountInfo':
        proces_accountInfo(msg)
    elif msgType == 'executionReport':
        process_executionReport(msg)


# print("message type: {}".format(msg['e']))
# print(msg)
# do something


bm.start_kline_socket(symbol=symbol, callback=process_message)
bm.start_user_socket(process_message)
bm.start()

''''
async def binanceWS(symbol):
    address = 'wss://stream.binance.com:9443/ws/%s@kline_1m' % symbol
    print(address)
    async with websockets.connect(address) as websocket:
        await websocket.send()

        msg = await websocket.recv()
        process_message(msg)

asyncio.get_event_loop().run_until_complete(binanceWS(symbol))


def on_message(ws, message):
    data = json.loads(message)
    if 'k' in data :
        closePrice = float(data['k']['c'])
        openPrice = float(data['k']['o'])
        currentPrice = closePrice
        print(closePrice)

def on_error(ws, error):
    print(error)


def on_close(ws):
    #print "Successes: %s, Fails %s" % (sucesses, fails)
    print("### closed ###")


def on_open(ws):
    ws.send(json.dumps({"action": "subscribe", "book": symbol, "type": "trades"}));

ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws/%s@kline_1m" % symbol,
                            #ws = websocket.WebSocketApp("wss://ws.bitso.com",
                            on_message=process_message,
                            on_error=on_error,
                            on_close=on_close,
                            on_open=on_open)

thread1 = thread.start_new_thread ( ws.run_forever, ())

'''
