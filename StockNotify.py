import asyncio
from datetime import datetime, timedelta
import configparser
import json
import requests
from fugle_marketdata import WebSocketClient, RestClient
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

    def line_notify_msg(self, msg):
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
        cdp, ah, nh, nl, al = self.calculate_indicators(data_dict)
        date = data_dict['data'][0]['date']
        msg_stock_code = data_dict['symbol']

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
            f"Price: {price}\n"
            "============================"
        )
        return message

    def _on_new_price(self, message):
        global trade_number
        json_data = json.loads(message)
        is_trial = json_data.get('data', {}).get('isTrial')
        temp_data.append(json_data)
        trade_number += 1
        if trade_number == len(self.stock_code_list[:5]) + 1:
            print("========= final ==========")
            self.client.stock.disconnect()
            for data in temp_data[1::]:
                print(data)
                if is_trial is None:
                    stock_code = data['data']['symbol']
                    latest_price = data['data']['price']
                    msg = self.check_cdp(self.data_dict[stock_code], latest_price)
                    self.line_notify_msg(f'{msg}')

    def handle_connect(self):
        print('connected')

    def handle_disconnect(self, code, message):
        print(f'disconnect: {code}, {message}')

    def handle_error(self, error):
        print(f'error: {error}')

    async def main(self, date):
        self.client = WebSocketClient(api_key=self.api_key)
        stock = self.client.stock
        stock.on('message', self._on_new_price)
        stock.on("connect", self.handle_connect)
        stock.on("disconnect", self.handle_disconnect)
        stock.on("error", self.handle_error)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, stock.connect)
        
        stock.subscribe({'channel': 'trades', 'symbols': self.stock_code_list[:5]})

if __name__ == '__main__':
    client = RestClient(api_key=api_key)
    stock = client.stock
    stock_code_file_path = "./stock_code_csv/stock_code.csv"
    stock_code_file = pd.read_csv(stock_code_file_path)
    stock_code_list = stock_code_file["code"]
    stock_code_list = [str(num) for num in stock_code_list]
    print(list(stock_code_list))

    current_date = datetime.now()
    previous_workday_date = previous_workday(current_date)
    formatted_date = previous_workday_date.strftime('%Y-%m-%d')
    print("前一個工作日的日期是:", formatted_date)

    historical_data_dict = {}
    for stock_code in stock_code_list:
        try:
            data_dict = stock.historical.candles(**{"symbol": f"{stock_code}", "from": f"{formatted_date}", "to": f"{formatted_date}", "fields": "open,high,low,close,volume,change"})
            print(f"data_dict for {stock_code}: {data_dict}")
            if 'symbol' in data_dict:
                symbol = data_dict['symbol']
                historical_data_dict[symbol] = data_dict
            else:
                print(f"缺少 symbol 鍵: {data_dict}")
        except Exception as e:
            print(f"獲取數據時出錯：{e}")

    print(historical_data_dict)
    notifier = StockNotifier(api_key=api_key, line_token=line_token, data_dict=historical_data_dict, stock_code_list=stock_code_list)
    asyncio.run(notifier.main(current_date))