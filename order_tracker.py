import json
import pandas as pd
import os
import sys
import time
import traceback

try:
    import redis
except ImportError:
    redis = None
    
from dotenv import load_dotenv

from api_lib.open_positions import (
    get_open_positions_demo,
    close_position,
    get_full_orders,
    cancel_and_set_new,
    create_stop_order,
)

from utils.log_config import logging_config

load_dotenv()
sleep_interval = int(os.getenv('SLEEP_INTERVAL', 120))

class OrderTracker:
    def __init__(self):
        self.run_with_mark = None
        self.open_orders = None
        self.open_positions = None
        
        # Initialize logging
        self.log = logging_config()
        self.m = "Order tracking: "

        # Initialize Redis if available
        self.redis_client = None
        if redis:
            try:
                self.redis_client = redis.Redis(
                    host=os.getenv('REDIS_HOST'), port=os.getenv('REDIS_PORT')
                )
                self.redis_client.ping()
                self.log.info(f"{self.m}Connected to Redis")
            except redis.RedisError as e:
                self.log.error(f"{self.m}Redis error: {e}")
                self.redis_client = None

        # Load saved_locally data
        self.saved_locally = self.load_saved_locally()

    def load_saved_locally(self):
        if self.redis_client:
            # Load from Redis
            saved_data = self.redis_client.get('saved_locally')
            if saved_data:
                data = json.loads(saved_data)
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()
        else:
            # Load from JSON file
            if os.path.exists('saved_locally.json'):
                with open('saved_locally.json', 'r') as f:
                    return pd.read_json(f)
            else:
                return pd.DataFrame()

    def save_saved_locally(self):
        if self.redis_client:
            # Save to Redis
            self.redis_client.set('saved_locally', self.saved_locally.to_json())
        else:
            # Save to JSON file
            with open('saved_locally.json', 'w') as f:
                self.saved_locally.to_json(f)

    def get_open_positions(self):
        return get_open_positions_demo()

    def get_open_orders(self):
        response = get_full_orders(limit=30)
        orders = response['data']['orders']

        # Attach positionId to orders
        open_positions = self.open_positions
        if len(orders) > 0 and open_positions.shape[0] > 0:
            for order in orders:
                filtered_position = open_positions[
                    (open_positions['symbol'] == order['symbol'])
                    & (open_positions['positionSide'] == order['positionSide'])
                ]
                if not filtered_position.empty:
                    order['positionId'] = filtered_position.iloc[0]['positionId']

        df = pd.DataFrame(orders)
        if df.shape[0] > 0:
            df = df[(df['status'] != 'CANCELLED') & (df['status'] != 'FILLED')]

        return df

    def close_position_order(self, position_row):
        self.log.info(
            f"{self.m}Trying to close {position_row['symbol']}, {position_row['positionSide']}, amount: {position_row['positionAmt']}"
        )
        order = close_position(position_row)
        self.log.info(f"{self.m}Closed position with order {order}")

    def run(self, re_raise_exception=False, mark=None):
        if not mark is None:
            self.run_with_mark = mark
        try:
            self.open_positions = self.get_open_positions()
            self.open_orders = self.get_open_orders()
            for index, position in self.open_positions.iterrows():
                self.process_position(position)

            self.save_saved_locally()
        except Exception as e:
            self.log.error(f"{self.m}Exception occurred: {e}\n{traceback.format_exc()}")
            if re_raise_exception:
                raise

    def process_position(self, position):
        positionSide = position['positionSide']
        positionId = position['positionId']
        self.log.info(f"{self.m}Processing {position['symbol']}, {positionSide}")
        # Find associated orders
        stop_order, stopPrice = self.get_stop_order(position)
        # Get saved_locally entry for this position
        saved_entry = self.get_saved_entry(positionId)

        # Process based on positionSide
        if positionSide == 'SHORT':
            self.process_short_position(position, stop_order, stopPrice, saved_entry)
        elif positionSide == 'LONG':
            self.process_long_position(position, stop_order, stopPrice, saved_entry)
        else:
            self.log.error(
                f"{self.m}Unknown positionSide {positionSide} for position {positionId}"
            )

    def get_stop_order(self, position):
        symbol = position['symbol']
        positionSide = position['positionSide']
        avgPrice = float(position['avgPrice'])
        if self.open_orders is None or self.open_orders.shape[0] == 0:
            return None, 0
            
        stop_orders = self.open_orders[
            (self.open_orders['symbol'] == symbol)
            & (self.open_orders['positionSide'] == positionSide)
            & (self.open_orders['type'].isin(['STOP', 'STOP_MARKET']))
        ]

        if not stop_orders.empty:
            stop_order = stop_orders.iloc[0]
            stopPrice = float(stop_order['stopPrice'])
        else:
            stop_order = None
            # Assume a default stopPrice for calculations
            if positionSide == 'LONG':
                stopPrice = avgPrice * 0.985  # 1.5% below avgPrice
            elif positionSide == 'SHORT':
                stopPrice = avgPrice * 1.015  # 1.5% above avgPrice
            else:
                self.log.error(f"{self.m}Unknown positionSide {positionSide}")
                stopPrice = avgPrice  # Fallback

        return stop_order, stopPrice

    def get_take_profit_price(self, position, avgPrice):
        symbol = position['symbol']
        positionSide = position['positionSide']

        if self.open_orders is None or self.open_orders.shape[0] == 0:
            return 0
        
        take_profit_orders = self.open_orders[
            (self.open_orders['symbol'] == symbol)
            & (self.open_orders['positionSide'] == positionSide)
            & (self.open_orders['type'] == 'TAKE_PROFIT')
        ]

        if not take_profit_orders.empty:
            take_profit_price = float(take_profit_orders.iloc[0]['stopPrice'])
        else:
            # If no TAKE_PROFIT order, suppose take_profit_price is avgPrice * 1.015
            take_profit_price = avgPrice * 1.015

        return take_profit_price

    def get_saved_entry(self, positionId):
        if self.saved_locally.shape[0] == 0:
            return None
        saved_entry = self.saved_locally[
            self.saved_locally['positionId'] == positionId
        ]
        if not saved_entry.empty:
            return saved_entry.iloc[0]
        else:
            return None

    def process_short_position(self, position, stop_order, stopPrice, saved_entry):
        symbol = position['symbol']
        positionId = position['positionId']
        markPrice = float(position['markPrice'])
        avgPrice = float(position['avgPrice'])

        # Get the take profit price
        take_profit_price = self.get_take_profit_price(position, avgPrice)

        # Condition 1: Close position if criteria met
        difference = avgPrice + stopPrice
        stopThreshold = avgPrice + (difference * 0.2)        
        if markPrice > avgPrice and markPrice > stopThreshold:
            self.log.info(
                f"{self.m}Closing SHORT position {symbol} as markPrice > avgPrice and markPrice > 120% of stopPrice"
            )
            self.close_position_order(position)
            # Remove from saved_locally
            self.remove_saved_entry(positionId)
        elif markPrice < avgPrice:
            # Determine if we should update the stop loss
            update_stop_loss = False
            if saved_entry is None:
                update_stop_loss = True
            else:
                saved_markPrice = float(saved_entry['markPrice'])
                if markPrice < saved_markPrice:
                    update_stop_loss = True

            if update_stop_loss:
                # Calculate new stop loss
                potential_profit = markPrice - take_profit_price
                sl_adjustment = potential_profit * 0.15
                new_sl_price = markPrice + sl_adjustment
                self.log.info(
                    f"{self.m}Setting new stop loss for SHORT position {symbol} at {new_sl_price}"
                )
                self.update_stop_loss(position, new_sl_price, stop_order)
                self.update_saved_entry(position, new_sl_price, stop_order, markPrice)
            else:
                self.log.info(
                    f"{self.m}SHORT position {symbol} markPrice {markPrice} >= saved_markPrice {saved_markPrice}, doing nothing"
                )

    def process_long_position(self, position, stop_order, stopPrice, saved_entry):
        symbol = position['symbol']
        positionId = position['positionId']
        markPrice = float(position['markPrice'])
        avgPrice = float(position['avgPrice'])
        take_profit_price = self.get_take_profit_price(position, avgPrice)

        # Condition 1: Close position if criteria met
        difference = avgPrice - stopPrice
        stopThreshold = avgPrice - (difference * 0.2)
        if markPrice < avgPrice and markPrice < stopThreshold:
            self.log.info(
                f"{self.m}Closing LONG position {symbol} as markPrice < avgPrice and markPrice < 80% of stopPrice"
            )
            self.close_position_order(position)
            # Remove from saved_locally
            self.remove_saved_entry(positionId)
        elif markPrice > avgPrice:
            # Determine if we should update the stop loss
            update_stop_loss = False
            if saved_entry is None:
                update_stop_loss = True
            else:
                saved_markPrice = float(saved_entry['markPrice'])
                if markPrice > saved_markPrice:
                    update_stop_loss = True

            if update_stop_loss:
                # Calculate new stop loss
                potential_profit = take_profit_price - markPrice
                sl_adjustment = potential_profit * 0.15
                new_sl_price = markPrice - sl_adjustment
                self.log.info(
                    f"{self.m}Setting new stop loss for LONG position {symbol} at {new_sl_price}"
                )
                self.update_stop_loss(position, new_sl_price, stop_order)
                self.update_saved_entry(position, new_sl_price, stop_order, markPrice)
            else:
                self.log.info(
                    f"{self.m}LONG position {symbol} markPrice {markPrice} <= saved_markPrice {saved_markPrice}, doing nothing"
                )    

    def update_stop_loss(self, position, new_sl_price, stop_order):
        
        symbol = position['symbol']
        positionSide = position['positionSide']
        positionAmt = float(position['positionAmt'])
        
        if stop_order is not None:
            # Cancel and set new stop order
            cancel_and_set_new(
                symbol,
                positionSide,
                positionAmt,
                new_sl_price,
                stop_order,
            )
        else:
            # Create new stop order
            create_stop_order(
                symbol, positionSide, positionAmt, new_sl_price
            )

    def update_saved_entry(self, position, new_sl_price, stop_order, markPrice):
        positionId = position['positionId']
        symbol = position['symbol']
        positionSide = position['positionSide']

        # Remove existing entry
        self.remove_saved_entry(positionId)

        new_saved_entry = {
            'symbol': symbol,
            'orderId': stop_order['orderId'] if stop_order is not None else None,
            'positionSide': positionSide,
            'type': stop_order['type'] if stop_order is not None else 'STOP_MARKET',
            'stopPrice': new_sl_price,
            'positionId': positionId,
            'markPrice': markPrice,
            'time': int(time.time() * 1000),
        }

        new_row_df = pd.DataFrame([new_saved_entry])
        self.saved_locally = pd.concat([self.saved_locally, new_row_df], ignore_index=True)

    def remove_saved_entry(self, positionId):
        if self.saved_locally.shape[0] == 0:
            return None
        self.saved_locally = self.saved_locally[
            self.saved_locally['positionId'] != positionId
        ]
        
if __name__ == '__main__':
    order_manager = OrderTracker()
    if len(sys.argv) > 1 and sys.argv[1] == 'loop':
        while True:
            order_manager.run()
            time.sleep(sleep_interval)
    else:
        order_manager.run()