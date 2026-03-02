import streamlit as st
import pandas as pd
import re, random
from datetime import datetime, timedelta # 修正時間用
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from collections import Counter
from linebot import LineBotApi
from linebot.models import TextSendMessage

# --- [1. 從 Secrets 讀取設定] ---
try:
    LINE_TOKEN = st.secrets["LINE_TOKEN"]
    USER_IDS = st.secrets["USER_IDS"]
except:
    st.error("❌ 無法讀取 Secrets 設定。")
    st.stop()

# --- [2. 台北時間專用函數] ---
def get_taipei_time():
    # 伺服器通常是 UTC，手動加 8 小時
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m/%d %H:%M:%S")

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 台北時間對獎版", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (預測 + 台北時間修正)")

# 初始化
if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_draw_data' not in st.session_state:
    st.session_state.last_draw_data = []

# 側邊欄
st.sidebar.header("📊 分析參數")
star_count = st.sidebar.slider("預測星數", 1, 10, 3)
analysis_range = st.sidebar.select_slider("分析樣本數", options=[100, 500, 1000, 2000], value=1000)

# --- [3. 抓取功能與演算法] (與之前相同) ---
def fetch_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.binary_location = "/usr/bin/chromium"
    try:
        service = Service("/usr/bin/chromedriver") 
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(TARGET_URL)
        page_text = driver.find_element("tag name", "body").text
        matches = re.findall(r'\b\d{2}\b', page_text)
        final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
        driver.quit()
        return final_nums
    except:
        return []

def advanced_analysis(all_nums, star, limit):
    target_nums = all_nums[:(limit * 20)]
    counts = Counter(target_nums)
    scores = {i: 0 for i in range(1, 81)}
    max_count = max(counts.values()) if counts else 1
    for num, count in counts.items():
        scores[num] += (count / max_count) * 50
    for num in all_nums[:20]:
        scores[num] += 15
    for num in range(1, 81):
        scores[num] += random.randint(0, 10)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [item[0] for item in sorted_scores[:15]]
    prediction = sorted(random.sample(top_candidates, star))
    return prediction

# --- [4. 主程式執行] ---
if st.button("🚀 啟動分析並自動對獎"):
    with st.spinner('數據讀取中...'):
        all_raw_data = fetch_data()
        current_20 = sorted(all_raw_data[:20]) if all_raw_data else []
        
        if current_20:
            now_time = get_taipei_time() # 使用台北時間
            
            # A. 檢查是否需要對獎
            if st.session_state.last_draw_data != current_20:
                for record in st.session_state.history:
                    if record["開獎結果"] == "等待開獎...":
                        hits = [n for n in record["預測號碼"] if n in current_20]
                        record["開獎結果"] = str(current_20)
                        record["中獎顆數"] = f"{len(hits)} 顆 ({hits})"
                
                # B. 產生下一期預測
                new_pred = advanced_analysis(all_raw_data, star_count, analysis_range)
                
                # C. 加入歷史紀錄
                st.session_state.history.insert(0, {
                    "時間": now_time,
                    "預測號碼": new_pred,
                    "開獎結果": "等待開獎...",
                    "中獎顆數": "-"
                })
                
                st.session_state.last_draw_data = current_20
                
                # LINE 推播 (包含台北時間)
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🔮 新預測：{new_pred}\n⏰ 台北時間：{now_time}\n(針對下一期開獎)"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                except:
                    pass
            else:
                st.info(f"⌛ 台北時間 {now_time}：獎號尚未更新。")

            # 顯示介面
            st.subheader(f"📟 最新開獎 (台北時間)：{current_20}")
            st.write("📜 歷史預測與對獎清單")
            st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)
        else:
            st.error("連線失敗，請稍後再試。")
