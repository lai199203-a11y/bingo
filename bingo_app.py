import streamlit as st
import pandas as pd
import time, re, random
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
except Exception as e:
    st.error("❌ 無法讀取 Secrets，請確認後台設定。")
    st.stop()

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 雲端預測對獎版", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (預測 + 自動對獎版)")

# --- [2. 初始化 Session State] ---
if 'history' not in st.session_state:
    st.session_state.history = []  # 格式: [{"時間": t, "預測": p, "結果": r, "中獎": h}]
if 'last_draw_data' not in st.session_state:
    st.session_state.last_draw_data = [] # 儲存最近一次抓到的 20 個號碼

# 側邊欄
st.sidebar.header("📊 分析參數")
star_count = st.sidebar.slider("預測星數", 1, 10, 3)
analysis_range = st.sidebar.select_slider("分析樣本數 (期數)", options=[100, 500, 1000, 2000], value=1000)

# --- [3. 雲端抓取功能] ---
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
        time.sleep(3) 
        page_text = driver.find_element("tag name", "body").text
        matches = re.findall(r'\b\d{2}\b', page_text)
        final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
        driver.quit()
        return final_nums
    except:
        return []

# --- [4. 分析演算法] ---
def advanced_analysis(all_nums, star, limit):
    target_nums = all_nums[:(limit * 20)]
    counts = Counter(target_nums)
    scores = {i: 0 for i in range(1, 81)}
    max_count = max(counts.values()) if counts else 1
    
    for num, count in counts.items():
        scores[num] += (count / max_count) * 50
    for num in all_nums[:20]: # 針對最近一期加權
        scores[num] += 15
    for num in range(1, 81):
        scores[num] += random.randint(0, 10)

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [item[0] for item in sorted_scores[:15]]
    prediction = sorted(random.sample(top_candidates, star))
    return prediction, sorted_scores

# --- [5. 主程式邏輯] ---
if st.button("🚀 啟動分析並自動對獎"):
    with st.spinner('連線中...'):
        all_raw_data = fetch_data()
        current_20 = sorted(all_raw_data[:20]) if all_raw_data else []
        
        if current_20:
            # A. 檢查是否開出了「新的一期」來對獎
            if st.session_state.last_draw_data != current_20:
                # 遍歷歷史紀錄，找出還在「等待開獎」的項目進行比對
                updated = False
                for record in st.session_state.history:
                    if record["開獎結果"] == "等待開獎...":
                        hits = [n for n in record["預測號碼"] if n in current_20]
                        record["開獎結果"] = str(current_20)
                        record["中獎"] = f"{len(hits)} 顆 ({hits})"
                        updated = True
                
                if updated:
                    st.success("🎯 偵測到新獎號，已完成歷史對獎！")
                
                # B. 產生「針對下一期」的預測
                new_pred, full_scores = advanced_analysis(all_raw_data, star_count, analysis_range)
                
                # C. 新增一筆預測紀錄
                st.session_state.history.insert(0, {
                    "時間": time.strftime("%H:%M:%S"),
                    "預測號碼": new_pred,
                    "開獎結果": "等待開獎...",
                    "中獎": "-"
                })
                
                # 更新最後抓取狀態
                st.session_state.last_draw_data = current_20
                
                # LINE 推播新預測
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🔮 新預測：{new_pred}\n(針對下一期)\n⏰ 時間：{time.strftime('%H:%M:%S')}"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                except:
                    pass
            else:
                st.info("⌛ 目前獎號尚未更新，請等 5 分鐘後開獎再試。")

            # --- 顯示介面 ---
            st.subheader(f"📟 目前最新獎號：{current_20}")
            
            col_left, col_right = st.columns([1, 2])
            with col_left:
                if st.session_state.history:
                    latest = st.session_state.history[0]
                    st.metric("本次推薦 (下一期)", str(latest["預測號碼"]))
            
            with col_right:
                st.write("📊 數據分析戰鬥力")
                # 這裡需要傳入預先算好的 scores，為了簡化介面，我們只顯示前 10 名
                pass # 畫圖邏輯可自行保留
            
            st.write("📜 預測與對獎紀錄")
            st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)
            
        else:
            st.error("無法抓取資料，請檢查網路。")
