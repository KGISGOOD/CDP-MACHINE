import asyncio
from datetime import datetime, timedelta
import configparser
import json
import requests
from fugle_marketdata import WebSocketClient, RestClient
import pandas as pd
import time

# 創建 ConfigParser 的實例
config = configparser.ConfigParser()
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
    def __init__(self, api_key, line_token, data_dict, stock_code_list, previous_workday_date):
        self.api_key = api_key
        self.line_token = line_token
        self.data_dict = data_dict
        self.stock_code_list = stock_code_list
        self.client = None
        self.notification_sent = False
        self.previous_workday_date = previous_workday_date

    def line_notify_msg(self, msg, line_msg_enable_signal):
        if line_msg_enable_signal:
            url = 'https://notify-api.line.me/api/notify'
            headers = {
                'Authorization': 'Bearer ' + self.line_token
            }
            data = {
                'message': f'{msg}'
            }
            requests.post(url, headers=headers, data=data)

    def calculate_indicators(self, data_dict):
        highest_price = data_dict['data'][0]['high']
        lowest_price = data_dict['data'][0]['low']
        close_price = data_dict['data'][0]['close']
        cdp = round((highest_price + lowest_price + 2 * close_price) / 4, 2)
        ah = round(cdp + (highest_price - lowest_price), 2)
        nh = round(2 * cdp - lowest_price, 2)
        nl = round(2 * cdp - highest_price, 2)
        al = round(cdp - (highest_price - lowest_price), 2)
        return cdp, ah, nh, nl, al

    def check_cdp(self, data_dict, price):
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
            f"CDP: {cdp:.2f}\n"
            f"AH: {ah:.2f}\n"
            f"NH: {nh:.2f}\n"
            f"NL: {nl:.2f}\n"
            f"AL: {al:.2f}\n"
            "============================\n"
            f"昨日收盤價: {price:.2f}\n"
            "============================\n"
            f"建議: {recommendation}"
        )

        return message, line_msg_enable_signal

    def main(self):
        cdp_match_found = False
        count = 0

        for k, v in self.data_dict.items():
            if v['data']:
                price = v['data'][0]['close']
                msg, line_msg_enable_signal = self.check_cdp(v, price)
                self.line_notify_msg(msg, line_msg_enable_signal)
                print()
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print(f"stock code : {k}")
                print(f"past_data: {v}")
                print()
                print(msg)

                if line_msg_enable_signal:
                    cdp_match_found = True

                count += 1
                if count % 50 == 0:
                    time.sleep(5)
            else:
                print(f"股票代號 {k} 在日期 {self.previous_workday_date} 沒有交易數據")

        if not cdp_match_found:
            msg = "今天個股沒有一個符合CDP規則"
            self.line_notify_msg(msg, True)

if __name__ == '__main__':
    client = RestClient(api_key=api_key)
    stock = client.stock
    stock_code_file_path = "./stock_code_csv/stock_code.csv"
    stock_code_file = pd.read_csv(stock_code_file_path)
    stock_code_list = stock_code_file["code"]
    stock_code_list = [str(num) for num in stock_code_list]
    print(f"監控的股票代號 : {list(stock_code_list)}")

    current_date = datetime.now()
    previous_workday_date = previous_workday(current_date)
    formatted_date = previous_workday_date.strftime('%Y-%m-%d')

    print("前一個工作日的日期是:", formatted_date)

    historical_data_dict = {}
    count = 0
    for stock_code in stock_code_list:
        data_dict = stock.historical.candles(**{"symbol": f"{stock_code}", "from": f"{formatted_date}", "to": f"{formatted_date}", "fields": "open,high,low,close,volume,change"})
        try:
            symbol = data_dict['symbol']
            historical_data_dict[symbol] = data_dict
        except:
            print("請求過於頻繁，請等待嘗試")

        count += 1
        if count % 50 == 0:
            time.sleep(5)

    print(historical_data_dict)
    print(len(historical_data_dict))

    notifier = StockNotifier(api_key=api_key, line_token=line_token, data_dict=historical_data_dict, stock_code_list=stock_code_list, previous_workday_date=previous_workday_date)
    notifier.main()
