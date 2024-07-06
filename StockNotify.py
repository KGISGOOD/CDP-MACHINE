#引入 asyncio 模組，用於實現異步操作。
import asyncio
#引入 datetime 和 timedelta 類，用於處理日期和時間。
from datetime import datetime, timedelta
#引入 configparser 模組，用於讀取配置文件。
import configparser
import json
import requests
from datetime import datetime, timezone, timedelta
#引入 fugle_marketdata 模組中的 WebSocketClient 和 RestClient 類，用於與 Fugle 的市場數據服務進行交互。
from fugle_marketdata import WebSocketClient, RestClient
import pandas as pd

# 創建 ConfigParser 的實例
# 建立 ConfigParser 物件，用來讀取 .ini 檔案中的設定。
config = configparser.ConfigParser()

# 讀取 .ini 檔案
config.read('config/config.ini')

# 從 .ini 檔案中取得 API 金鑰
api_key = config['API']['api_key']
line_token = config['API']['line_token']
temp_data = []
trade_number = 0

#定義 previous_workday 函式，回傳輸入日期的前一個工作日。如果輸入日期是星期一，則回推到上週五，否則回推一天。
def previous_workday(date):
    """
    回傳前一個工作日的日期。
    Args:
        date (datetime): 輸入日期。
    Returns:
        datetime: 前一個工作日的日期。
    """
    # 星期一是0，星期日是6
    # 如果今天是星期一，則回推到上週五
    if date.weekday() == 0:
        return date - timedelta(days=3)
    # 如果今天是星期二至星期日，則回推一天，直到回推到星期五

    return date - timedelta(days=1)

class StockNotifier:
    """
    股票通知器類別，用於監視股票價格並發送通知。
    """
    def __init__(self, api_key, line_token, data_dict, stock_code_list):
        self.api_key = api_key
        self.line_token = line_token
        self.data_dict = data_dict
        self.stock_code_list = stock_code_list
        self.client = None
        self.notification_sent = False # 設置標誌以確保僅發送一次通知

    def line_notify_msg(self, msg):
        """
        以 LINE 通知訊息。
        Args:
            msg (str): 要發送的訊息。
        """
        url = 'https://notify-api.line.me/api/notify'
        headers = {
            'Authorization': 'Bearer ' + self.line_token    # 設定權杖
        }
        data = {
            'message': f'{msg}'     # 設定要發送的訊息
        }
        requests.post(url, headers=headers, data=data)   # 使用 POST 方法

    #定義 calculate_indicators 方法，用來計算股票的技術指標，包括 CDP、AH、NH、NL 和 AL。這些指標是根據股票的最高價、最低價和收盤價計算得出的。
    def calculate_indicators(self, data_dict):
        """
        計算技術指標。
        Args:
            data_dict (dict): 包含股票數據的字典。
        Returns:
            tuple: 包含計算的技術指標。
        """
        highest_price = data_dict['data'][0]['high']
        lowest_price = data_dict['data'][0]['low']
        close_price = data_dict['data'][0]['close']
        cdp = (highest_price + lowest_price + 2 * close_price) / 4
        ah = cdp + (highest_price - lowest_price)
        nh = 2 * cdp - lowest_price
        nl = 2 * cdp - highest_price
        al = cdp - (highest_price - lowest_price)
        return cdp, ah, nh, nl, al

    #check_cdp 方法檢查CDP指標並生成相關消息。
    def check_cdp(self, data_dict, price):
        """
        檢查 CDP 指標並生成相應的消息。
        Args:
            data_dict (dict): 包含股票數據的字典。
            price (float): 最新價格。
        Returns:
            str: 生成的消息。
        """
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

    #_on_new_price 方法處理新的價格更新，並在收到足夠的數據後斷開WebSocket連接並發送通知。
    def _on_new_price(self, message):
        global trade_number
        """
        處理新的價格更新。
        Args:
            message (str): 收到的消息。
        """
        json_data = json.loads(message)
        is_trial = json_data.get('data', {}).get('isTrial')

        temp_data.append(json_data)
        trade_number += 1
        if trade_number == len(self.stock_code_list[:5]) + 1:
            print("========= final ==========")
            self.client.stock.disconnect()

            for data in temp_data[1::]:
                print(data)
                if is_trial is None: # 避免用到試撮資料並且僅發送一次
                    # 取最新成交價
                    stock_code = data['data']['symbol']
                    latest_price = data['data']['price']
                    msg = self.check_cdp(self.data_dict[stock_code], latest_price)
                    self.line_notify_msg(f'{msg}')

    #處理WebSocket連接、斷開和錯誤事件。
    def handle_connect(self):
        """
        stock webhook : connected
        """
        print('connected')

    def handle_disconnect(self, code, message):
        """
        stock webhook : disconnect
        """
        print(f'disconnect: {code}, {message}')

    def handle_error(self, error):
        """
        stock webhook : error
        """
        print(f'error: {error}')

    #check_time 方法檢查當前時間並計算需要等待的秒數。
    def check_time(self, date):
        target_times = {
            9: (9, 0),
            11: (11, 0)
        }
        check_hour = date.hour
        if check_hour in target_times:
            target_hour, target_minute = target_times[check_hour]
            target_time = date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
            if date < target_time:
                delta_time = target_time - date
                seconds_to_wait = delta_time.total_seconds()
                print(f"Waiting {seconds_to_wait} seconds until {target_time.strftime('%H:%M')}...")
                return int(seconds_to_wait)
        else:
            return 0

    #main 方法設置並運行WebSocket連接，並訂閱股票交易信息。
    async def main(self, date):
        """
        主要方法，設定並運行 WebSocket 連接。
        """
        # seconds_to_wait = self.check_time(date)
        # await asyncio.sleep(seconds_to_wait)

        self.client = WebSocketClient(api_key=self.api_key)
        stock = self.client.stock
        stock.on('message', self._on_new_price)
        stock.on("connect", self.handle_connect)
        stock.on("disconnect", self.handle_disconnect)
        stock.on("error", self.handle_error)

        await stock.connect()

        stock.subscribe({
            'channel': 'trades',
            'symbols': self.stock_code_list[:5] # 若要使用多檔股票可改用 symbols 參數
        })

#這部分代碼是程式的入口。它從配置檔案中讀取API金鑰，讀取股票代碼，計算前一個工作日的日期，獲取每個股票的歷史數據，然後實例化 StockNotifier 並運行其主方法。
if __name__ == '__main__':

    client = RestClient(api_key=api_key)
    stock = client.stock  # Stock REST API client
    stock_code_file_path = "./stock_code_csv/stock_code.csv"
    stock_code_file = pd.read_csv(stock_code_file_path)
    stock_code_list = stock_code_file["code"]
    stock_code_list = [str(num) for num in stock_code_list]
    print(list(stock_code_list))

    # 獲取當前日期
    current_date = datetime.now()

    # 計算前一個工作日的日期
    previous_workday_date = previous_workday(current_date)

    # 格式化日期為所需形式
    formatted_date = previous_workday_date.strftime('%Y-%m-%d')

    print("前一個工作日的日期是:", formatted_date)
    # formatted_date = '2023-03-15'
    # 獲取指定股票的歷史數據
    historical_data_dict = {}
    for stock_code in stock_code_list:
        data_dict = stock.historical.candles(**{"symbol": f"{stock_code}", "from": f"{formatted_date}", \
                                                "to": f"{formatted_date}", \
                                                "fields": "open,high,low,close,volume,change"})
        symbol = data_dict['symbol']
        historical_data_dict[symbol] = data_dict
    print(historical_data_dict)

    # 訂定單量
    notifier = StockNotifier(api_key=api_key, line_token=line_token, data_dict=historical_data_dict, stock_code_list=stock_code_list)
    asyncio.run(notifier.main(current_date)) # command line 等環境用這個
