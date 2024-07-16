import asyncio
from datetime import datetime, timedelta
import configparser
import json
import requests
from fugle_marketdata import RestClient
import pandas as pd

# 創建 ConfigParser 的實例
config = configparser.ConfigParser()

# 讀取 .ini 檔案
config.read('config/config.ini')

# 從 .ini 檔案中取得 API 金鑰
api_key = config['API']['api_key']
line_token = config['API']['line_token']
temp_data = []
trade_number = 0

def previous_workday(date):
    if date.weekday() == 0:
        return date - timedelta(days=3)
    return date - timedelta(days=1)

class StockNotifier:
    def __init__(self, api_key, line_token, data_dict, stock_code_list):
        self.api_key = api_key
        self.line_token = line_token
        self.data_dict = data_dict
        self.stock_code_list = stock_code_list
        self.client = None
        self.notification_sent = False

    def line_notify_msg(self, msg, line_msg_enable_signal):
        if line_msg_enable_signal:
            url = 'https://notify-api.line.me/api/notify'
            headers = {'Authorization': 'Bearer ' + self.line_token}
            data = {'message': f'{msg}'}
            requests.post(url, headers=headers, data=data)

    def calculate_indicators(self, data_dict):
        highest_price = data_dict['data'][0]['high']
        lowest_price = data_dict['data'][0]['low']
        close_price = data_dict['data'][0]['close']
        cdp = (highest_price + lowest_price + 2 * close_price) / 4
        ah = cdp + (highest_price - lowest_price)
        nh = 2 * cdp - lowest_price
        nl = 2 * cdp - highest_price
        al = cdp - (highest_price - lowest_price)
        return cdp, ah, nh, nl, al

    def check_cdp(self, data_dict, price):
        if 'data' not in data_dict or not data_dict['data']:
            return "無有效數據", False

        if len(data_dict['data']) < 1 or data_dict['data'][0]['volume'] < 1000:
            return "數據數量不足", False

        cdp, ah, nh, nl, al = self.calculate_indicators(data_dict)
        date = data_dict['data'][0]['date']
        msg_stock_code = data_dict['symbol']
        recommendation = ""
        line_msg_enable_signal = False
        if price >= ah:
            recommendation = "建議: 開盤價接近最高值(AH)，追價買進"
            line_msg_enable_signal = True
        elif price <= al:
            recommendation = "建議: 開盤價接近最低值(AL)，追價賣出"
            line_msg_enable_signal = True
        else:
            recommendation = "建議: 根據盤中價位進行操作"
            line_msg_enable_signal = False

        message = (
            f"股票代號 : {msg_stock_code}\n"
            f"{date}的CDP指標\n"
            "============================\n"
            f"CDP: {cdp}\n"
            f"AH: {ah}\n"
            f"NH: {nh}\n"
            f"NL: {nl}\n"
            f"AL: {al}\n"
            "============================\n"
            f"昨日收盤價: {price}\n"
            "============================\n"
            f"建議: {recommendation}"
        )

        return message, line_msg_enable_signal

    async def process_stocks(self):
        count = 0
        line_msg_count = 0  # 追蹤符合CDP指標並推送到LINE的股票數量
        for k, v in self.data_dict.items():
            price = v['data'][0]['close']
            msg, line_msg_enable_signal = self.check_cdp(v, price)
            self.line_notify_msg(msg, line_msg_enable_signal)
            if line_msg_enable_signal:
                line_msg_count += 1  # 更新計數器
            print()
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            print(f"股票代號 : {k}")
            print(f"歷史數據: {v}")
            print()
            print(msg)

            count += 1
            if count % 100 == 0:
                print(f"已處理 {count} 支股票，休息 5 秒...")
                await asyncio.sleep(5)

        if line_msg_count == 0:
            self.line_notify_msg("今天沒有一個股票符合CDP指標", True)

    def main(self):
        asyncio.run(self.process_stocks())

if __name__ == '__main__':
    client = RestClient(api_key=api_key)
    stock = client.stock
    stock_code_file_path = "./stock_code_csv/stock_code.csv"
    stock_code_file = pd.read_csv(stock_code_file_path)
    stock_code_list = stock_code_file["code"]
    stock_code_list = [str(num) for num in stock_code_list if str(num) not in ['1203', '9918']]
    print(f"監控的股票代號 : {list(stock_code_list)}")

    current_date = datetime.now()
    previous_workday_date = previous_workday(current_date)
    formatted_date = previous_workday_date.strftime('%Y-%m-%d')

    print("前一個工作日的日期是:", formatted_date)

    historical_data_dict = {}
    for stock_code in stock_code_list:
        data_dict = stock.historical.candles(symbol=stock_code, from_=formatted_date, to=formatted_date, fields="open,high,low,close,volume,change")
        if 'data' in data_dict and data_dict['data']:
            symbol = data_dict['symbol']
            volume = data_dict['data'][0]['volume']
            print(f"股票代號 {symbol} 的交易量是 {volume}")
            if volume >= 1000:
                historical_data_dict[symbol] = data_dict
            else:
                print(f"股票代號 {symbol} 的交易量不足 1000")
        else:
            print(f"股票代號 {stock_code} 在 {formatted_date} 沒有有效數據。")

    print(historical_data_dict)
    print(len(historical_data_dict))

    notifier = StockNotifier(api_key=api_key, line_token=line_token, data_dict=historical_data_dict, stock_code_list=stock_code_list)
    notifier.main()
