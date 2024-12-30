import pandas as pd
from api_lib.open_positions import get_klines_data_df
import numpy as np

class CoefficientCalculator:
    def __init__(self, atr_period=14, rsi_period=14, threshold=0.01):
        self.atr_period = atr_period  # Период для расчёта ATR
        self.rsi_period = rsi_period  # Период для расчёта RSI
        self.threshold = threshold    # Пороговое значение волатильности

    def calculate_atr(self, df):
        """Расчёт ATR на основе OHLCV данных"""
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                         abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
        return df['atr'].iloc[-1]  # Возвращаем последнее значение ATR

    def calculate_rsi(self, df):
        """Расчёт RSI на основе цен закрытия"""
        delta = df['close'].diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(self.rsi_period).mean()
        avg_loss = pd.Series(loss).rolling(self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]  # Возвращаем последнее значение RSI

    def calculate_coefficients(self, df, mark_price):
        """
        Рассчитывает коэффициенты на основе волатильности и рыночных условий.
        :param df: DataFrame с историческими данными OHLCV
        :param mark_price: Текущая рыночная цена
        :return: Коэффициенты для управления стоп-лоссом
        """
        atr = self.calculate_atr(df)
        rsi = self.calculate_rsi(df)

        # Рассчитываем относительную волатильность
        volatility = atr / mark_price

        # Логика расчёта коэффициентов
        if volatility > self.threshold:
            stop_loss_coefficient = 0.15  # Высокая волатильность
        elif rsi > 70:
            stop_loss_coefficient = 0.10  # Перекупленность
        else:
            stop_loss_coefficient = 0.20  # Нормальные условия

        return {
            "stop_loss_coefficient": stop_loss_coefficient,
            "volatility": volatility,
            "rsi": rsi,
            "atr": atr
        }

# Пример использования
if __name__ == "__main__":
    calculator = CoefficientCalculator()

    symbol = "DUSK-USDT"
    timeframe = "5m"
    limit = 1000
    df = get_klines_data_df(symbol, timeframe, limit)

    if not df.empty:
        mark_price = df['close'].iloc[-1]  # Последняя цена закрытия
        coefficients = calculator.calculate_coefficients(df, mark_price)

        print(f"Calculated coefficients: {coefficients}")
    else:
        print("Failed to retrieve data.")