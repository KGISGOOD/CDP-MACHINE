# stock_notify

## 簡介

`股票提醒` 是一個用於追蹤和通知股票價格變化的工具。通過此項目，用戶可以設置特定的股票，並在價格達到預定值時接收通知。

## 目錄

- [簡介](#簡介)
- [目錄](#目錄)
- [環境要求](#環境要求)
- [安裝](#安裝)
  - [Windows](#windows)
  - [Mac](#mac)
- [運行項目](#運行項目)
- [配置](#配置)
- [許可](#許可)

## 環境要求

- Python 版本：3.8 或更高
- pip
- Git

## 安裝

### Windows

1. **克隆倉庫**

    打開 PowerShell 並運行以下命令：
    ```powershell
    git clone https://github.com/Terrywu0208/stock_notify.git
    cd stock_notify
    ```

2. **創建虛擬環境**

    ```powershell
    python -m venv venv
    ```

3. **激活虛擬環境**

    ```powershell
    .\venv\Scripts\Activate
    ```

4. **安裝依賴**

    ```powershell
    pip install -r requirements.txt
    ```

### Mac

1. **克隆倉庫**

    打開終端並運行以下命令：
    ```sh
    git clone https://github.com/Terrywu0208/stock_notify.git
    cd stock_notify
    ```

2. **創建虛擬環境**

    ```sh
    python3 -m venv venv
    ```

3. **激活虛擬環境**

    ```sh
    source venv/bin/activate
    ```

4. **安裝依賴**

    ```sh
    pip3 install -r requirements.txt
    ```

## 運行項目

### Windows

1. **激活虛擬環境**（如果尚未激活）

    ```powershell
    .\venv\Scripts\Activate
    ```

2. **運行項目**

    ```powershell
    python StockNotify.py
    ```

### Mac

1. **激活虛擬環境**（如果尚未激活）

    ```sh
    source venv/bin/activate
    ```

2. **運行項目**

    ```sh
    python3 StockNotify.py
    ```

## 配置

1. **建立配置文件夾**

    在項目根目錄下建立一個名為 `config` 的資料夾。

2. **創建配置文件**

    在 `config` 資料夾中創建一個名為 `config.ini` 的配置文件。在此文件中添加以下內容：

    ```
    [API]
    api_key = 富果API
    line_token = Line_Notify_tone
    ```

    將 `富果API` 替換為你的富果API密鑰，將 `Line_Notify_tone` 替換為你的Line Notify令牌。

