class Position:

    LONG_POSITION = 'LONG_POSITION'
    SHORT_POSITION = 'SHORT_POSITION'

    shortPositions = 0.0
    longPositions = 0.0
    stopLoss = 0.0
    takeProfit = 0.0
    entryPrice = 0.0
    entryQty = 0.0
    symbol = ''

    @classmethod
    def __init__(self, symbol, price, qty, stop_loss, take_profit):
        self.symbol = symbol
        self.entryPrice = price
        self.stopLoss = stop_loss
        self.takeProfit = take_profit
        self.entryQty = qty
