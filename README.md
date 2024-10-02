# order-tracker

### Script for tracking open positions.

This script tracks open positions at Bingx exchange, but could be easy refactored to use other exchanges.
Implemented the next algorythm:
- In case of Short position:
	IF Position.markPrice > Position.avgPrice and Position.markPrice is greater than 20% of StopOrder.stopPrice then close position.
	if Position.markPrice < Position.avgPrice:
		if Position.markPrice > SavedLocally.markPrice - do nothing
		set stop loss greater than Position.markPrice for 15%. This means Position.markPrice + (Position.markPrice * 0.15)

- In case of Long position:

	IF Position.markPrice < Position.avgPrice and Position.markPrice is less than 20% of StopOrder.stopPrice then close position. e.g. - avgPrice = 100, stopLoss = 80, markPrice = 97.99 - we should close this order
	if Position.markPrice < Position.avgPrice:
		if Position.markPrice < SavedLocally.markPrice - do nothing
		set stop loss lesst than Position.markPrice for 15%. This means Position.markPrice - (Position.markPrice * 0.15)

Percent values is hardcoded, but easy could be extracted to variables.

### install

- clone repository git clone https://github.com/aleksandr-suhhinin/order-tracker.git order_tracker
- cd into order_tracker
- install dependencies: `pip install -r requirements.txt`
- create .env file or `cp env.example .env` and set API_KEY,  API_SECRET and if necessary set APIURL, currently set for using Bingx demo account.
- run script `python order_tracker.py` - for checking once or `python order_tracker.py loop` for run in loop every `getenv('SLEEP_INTERVAL')` seconds.

