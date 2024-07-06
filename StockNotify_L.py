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

#定義 StockNotifier 類別，該類別用於監控股票價格並發送通知。在初始化方法中，設置 API 金鑰、Line 通知權杖、股票數據字典和股票代碼列表，並初始化一些變數。
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

    #定義 line_notify_msg 方法，用來通過 LINE 發送通知訊息。當 line_msg_enable_signal 為 True 時，構建請求並使用 POST 方法發送訊息。
    def line_notify_msg(self, msg, line_msg_enable_signal):
        """
        以 LINE 通知訊息。
        Args:
            msg (str): 要發送的訊息。
        """
        if line_msg_enable_signal:
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

    #定義 check_cdp 方法，檢查 CDP 指標並生成相應的消息。
    #根據最新價格和計算出的技術指標，給出操作建議。如果價格接近最高值（AH）或最低值（AL），則啟用 Line 通知。
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
            line_msg_enable_signal = False  # 不推播訊息

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

    #定義 main 方法，遍歷 data_dict 中的股票數據，檢查每個股票的 CDP 指標並發送通知，然後打印相關信息。
    def main(self):
        cdp_match_found = False  # 標誌是否找到符合 CDP 規則的股票

        for k, v in self.data_dict.items():
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

        # 如果沒有找到符合 CDP 規則的股票，發送一則訊息說明今天沒有符合規則的股票
        if not cdp_match_found:
            msg = "今天個股沒有一個符合CDP規則"
            self.line_notify_msg(msg, True)  # 強制推播訊息


#在主程序中，使用 API 金鑰建立 RestClient 並讀取股票代碼。
#計算前一個工作日的日期並格式化，然後獲取每個股票的歷史數據並存入 historical_data_dict。最後，實例化 StockNotifier 並運行其主方法。
if __name__ == '__main__':
    client = RestClient(api_key=api_key)
    stock = client.stock  # Stock REST API client
    stock_code_file_path = "./stock_code_csv/stock_code.csv"
    stock_code_file = pd.read_csv(stock_code_file_path)
    stock_code_list = stock_code_file["code"]
    stock_code_list = [str(num) for num in stock_code_list]
    print(f"監控的股票代號 : {list(stock_code_list)}")

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
        try:
            symbol = data_dict['symbol']
            historical_data_dict[symbol] = data_dict
        except:
            print("請求過於頻繁，請等待嘗試")
    print(historical_data_dict)
    print(len(historical_data_dict))

    # 訂定單量
    notifier = StockNotifier(api_key=api_key, line_token=line_token, data_dict=historical_data_dict, stock_code_list=stock_code_list)
    notifier.main()    
    
