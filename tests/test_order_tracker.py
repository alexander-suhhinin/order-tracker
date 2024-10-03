import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from order_tracker import OrderTracker

class TestOrderTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = OrderTracker()
        self.tracker.saved_locally = pd.DataFrame()
    
    @patch('order_tracker.create_stop_order')
    @patch('order_tracker.cancel_and_set_new')
    @patch('order_tracker.close_position')
    @patch('order_tracker.get_full_orders')
    @patch('order_tracker.get_open_positions_demo')
    @patch('order_tracker.logging_config')
    def test_run_with_no_positions(
        self,
        mock_logging_config,
        mock_get_open_positions_demo,
        mock_get_full_orders,
        mock_close_position,
        mock_cancel_and_set_new,
        mock_create_stop_order,
    ):
        # Setup mock logging
        mock_log = MagicMock()
        mock_logging_config.return_value = mock_log

        # Setup mock functions to return empty data
        mock_get_open_positions_demo.return_value = pd.DataFrame()
        mock_get_full_orders.return_value = {'data': {'orders': []}}

        # Initialize OrderTracker
        self.tracker.run()

        # Assert that no actions were taken
        mock_close_position.assert_not_called()
        mock_cancel_and_set_new.assert_not_called()
        mock_create_stop_order.assert_not_called()
        self.assertTrue(self.tracker.saved_locally.empty)

    @patch('order_tracker.create_stop_order')
    @patch('order_tracker.cancel_and_set_new')
    @patch('order_tracker.close_position')
    @patch('order_tracker.get_full_orders')
    @patch('order_tracker.get_open_positions_demo')
    @patch('order_tracker.logging_config')
    def test_run_with_position_closing_condition_met_long(
        self,
        mock_logging_config,
        mock_get_open_positions_demo,
        mock_get_full_orders,
        mock_close_position,
        mock_cancel_and_set_new,
        mock_create_stop_order,
    ):
        """
        Test closing a LONG position when markPrice < avgPrice and markPrice < stopPrice * 0.8
        """
        # Setup mock logging
        mock_log = MagicMock()
        mock_logging_config.return_value = mock_log

        # Mock open positions
        positions_df = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'positionId': [1],
            'positionAmt': [0.5],
            'markPrice': [70],  # markPrice < avgPrice
            'avgPrice': [100],
        })
        mock_get_open_positions_demo.return_value = positions_df

        # Mock open orders with a stopPrice of 90
        orders_df = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'type': ['STOP_MARKET'],
            'stopPrice': [90],
            'orderId': [123],
            'status': ['NEW'],
        })
        mock_get_full_orders.return_value = {'data': {'orders': orders_df.to_dict('records')}}

        # Run the tracker
        self.tracker.run()

        # Assert close_position was called
        mock_close_position.assert_called_once()
        mock_cancel_and_set_new.assert_not_called()
        mock_create_stop_order.assert_not_called()

        # Assert saved_locally is empty
        self.assertTrue(self.tracker.saved_locally.empty)

    @patch('order_tracker.create_stop_order')
    @patch('order_tracker.cancel_and_set_new')
    @patch('order_tracker.close_position')
    @patch('order_tracker.get_full_orders')
    @patch('order_tracker.get_open_positions_demo')
    @patch('order_tracker.logging_config')
    def test_run_with_position_update_stop_loss_long(
        self,
        mock_logging_config,
        mock_get_open_positions_demo,
        mock_get_full_orders,
        mock_close_position,
        mock_cancel_and_set_new,
        mock_create_stop_order,
    ):
        """
        Test updating stop-loss for a LONG position when markPrice > avgPrice and no saved entry exists
        """
        # Setup mock logging
        mock_log = MagicMock()
        mock_logging_config.return_value = mock_log

        # Mock open positions
        positions_df = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'positionId': [1],
            'positionAmt': [0.5],
            'markPrice': [120],  # markPrice > avgPrice
            'avgPrice': [100],
        })
        mock_get_open_positions_demo.return_value = positions_df
        
        orders_df = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'type': ['TAKE_PROFIT'],
            'stopPrice': [130],
            'orderId': [123],
            'status': ['NEW'],
        })
        mock_get_full_orders.return_value = {'data': {'orders': orders_df.to_dict('records')}}


        self.tracker.run(mark="test_run_with_position_update_stop_loss_long")

        new_sl_price = 120 - ((130 - 120) * 0.15)  # 118.5

        # Assert create_stop_order was called
        mock_create_stop_order.assert_called_once_with('BTCUSDT', 'LONG', 0.5, new_sl_price)
        mock_close_position.assert_not_called()
        mock_cancel_and_set_new.assert_not_called()

        # Assert saved_locally has the new entry
        self.assertEqual(len(self.tracker.saved_locally), 1)
        self.assertEqual(self.tracker.saved_locally.iloc[0]['stopPrice'], new_sl_price)

    @patch('order_tracker.create_stop_order')
    @patch('order_tracker.cancel_and_set_new')
    @patch('order_tracker.close_position')
    @patch('order_tracker.get_full_orders')
    @patch('order_tracker.get_open_positions_demo')
    @patch('order_tracker.logging_config')
    def test_run_with_position_update_stop_loss_short(
        self,
        mock_logging_config,
        mock_get_open_positions_demo,
        mock_get_full_orders,
        mock_close_position,
        mock_cancel_and_set_new,
        mock_create_stop_order,
    ):
        """
        Test updating stop-loss for a SHORT position when markPrice < avgPrice and no saved entry exists
        """
        # Setup mock logging
        mock_log = MagicMock()
        mock_logging_config.return_value = mock_log

        # Mock open positions
        positions_df = pd.DataFrame({
            'symbol': ['ETHUSDT'],
            'positionSide': ['SHORT'],
            'positionId': [2],
            'positionAmt': [1],
            'markPrice': [80],  # markPrice < avgPrice
            'avgPrice': [100],
        })
        mock_get_open_positions_demo.return_value = positions_df

        # Mock open orders with no stop orders
        mock_get_full_orders.return_value = {'data': {'orders': []}}

        
        # Run the tracker
        self.tracker.run(mark="test_run_with_position_update_stop_loss_short")

        # Calculate expected stop-loss price
        new_sl_price = 80 + (80 * 0.15)  # 80 + 12 = 92

        mock_create_stop_order.assert_called_once()
        mock_close_position.assert_not_called()
        mock_cancel_and_set_new.assert_not_called()

        # Assert saved_locally has the new entry
        self.assertEqual(len(self.tracker.saved_locally), 1)
        self.assertEqual(self.tracker.saved_locally.iloc[0]['stopPrice'], new_sl_price)

    @patch('order_tracker.create_stop_order')
    @patch('order_tracker.cancel_and_set_new')
    @patch('order_tracker.OrderTracker.close_position_order')
    @patch('order_tracker.get_full_orders')
    @patch('order_tracker.get_open_positions_demo')
    @patch('order_tracker.logging_config')
    def test_run_with_saved_entry_higher_mark_price_long(
        self,
        mock_logging_config,
        mock_get_open_positions_demo,
        mock_get_full_orders,
        mock_close_position_order,
        mock_cancel_and_set_new,
        mock_create_stop_order,
    ):
        """
        Test that no action is taken when markPrice <= saved markPrice for LONG position
        """
        # Setup mock logging
        mock_log = MagicMock()
        mock_logging_config.return_value = mock_log

        # Mock open positions
        positions_df = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'positionId': [1],
            'positionAmt': [0.5],
            'markPrice': [105],  # markPrice <= saved markPrice
            'avgPrice': [100],
        })
        mock_get_open_positions_demo.return_value = positions_df

        # Mock open orders
        mock_get_full_orders.return_value = {'data': {'orders': []}}

        self.tracker.saved_locally = pd.DataFrame({
            'symbol': ['BTCUSDT'],
            'positionSide': ['LONG'],
            'positionId': [1],
            'markPrice': [110],  # higher than current markPrice
        })

        self.tracker.run()

        mock_create_stop_order.assert_not_called()
        mock_close_position_order.assert_not_called()
        mock_cancel_and_set_new.assert_not_called()
    

if __name__ == '__main__':
    unittest.main()