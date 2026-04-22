from curl_cffi import requests # 改用 curl_cffi 的 requests
import json

# 你原本挖出來的資料
cookies = {
    'tracking-preferences': '{%22version%22:1%2C%22destinations%22:{%22Actions%20Amplitude%22:true%2C%22AdWords%22:true%2C%22Braze%20Cloud%20Mode%20(Actions)%22:true%2C%22Google%20AdWords%20New%22:true%2C%22Google%20Enhanced%20Conversions%22:true%2C%22Google%20Tag%20Manager%22:true%2C%22Impact%20Partnership%20Cloud%22:true}%2C%22custom%22:{%22advertising%22:true%2C%22functional%22:true%2C%22marketingAndAnalytics%22:true}}',
    'TCG_VisitorKey': 'bf11d6d1-1b51-437e-9310-75431b8165e3',
    # ... 其餘 cookies ...
}

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://www.tcgplayer.com',
    'referer': 'https://www.tcgplayer.com/',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    # 注意：在程式中盡量不要重複傳送 cookie header，交給 cookies 參數處理即可
}

params = {'mpfev': '5061'}
json_data = {'limit': 1}

def exploit_api():
    url = 'https://mpapi.tcgplayer.com/v2/product/665194/latestsales'
    
    print("[*] 正在發動模擬攻擊：偽裝 TLS 指紋為 Chrome 120...")
    
    try:
        # 關鍵在於 impersonate 參數
        response = requests.post(
            url,
            params=params,
            cookies=cookies,
            headers=headers,
            json=json_data,
            impersonate="chrome120" # 這是突破 Cloudflare 的關鍵破甲彈
        )
        
        print(f"[*] 伺服器回應代碼: {response.status_code}")
        
        if response.status_code == 200:
            print("[+] 突破成功！JSON 數據已成功劫持：")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"[-] 還是被擋下了。回應內容：{response.text[:200]}")
            
    except Exception as e:
        print(f"[!] 程式報錯: {e}")

if __name__ == "__main__":
    exploit_api()