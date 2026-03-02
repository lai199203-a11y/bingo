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
# 請確保你在 Streamlit Cloud 的 Advanced settings > Secrets 裡有填寫這兩項
try:
    LINE_TOKEN = st.secrets["32WenhP+Pr7gQ5gO8cUg+ORNy87erfNkHOPLT7gouLOxFhpK1Clh4dbRcYxdKim5MhJX6xvHVGm+PJGeZ0f2/oK+dan8Lm3uYK6yC020g7IwlxmKsq8DcUI/vhIdiIbpLBg3fHRmAg/HMAqETyDjBgdB04t89/1O/w1cDnyilFU="]
    USER_IDS = st.secrets["U24ac173c5c7a23d72e1018161191957a", "U1015df09c4cebecf4187b98ecc9ce00c"] # 格式需為 ["ID1", "ID2"]
except:
    st.error("❌ 偵測不到 Secrets 設定！請在 Streamlit 後台設定 LINE_TOKEN 與 USER_IDS。")
    st.stop()

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 雲端最強分析儀", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (雲端穩定版)")

if 'history' not in st.session_state:
    st.session_state.history = []

star_count = st.sidebar.slider("預測星數", 1, 10, 3)
analysis_range = st.sidebar.select_slider("分析樣本數", options=[500, 1000, 2000], value=1000)

# --- [2. 雲端專用數據抓取邏輯] ---
def fetch_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # 隱藏自動化控制特徵，避免被網站封鎖
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(TARGET_URL)
        time.sleep(5) 
        
        page_text = driver.find_element("tag name", "body").text
        matches = re.findall(r'\b\d{2}\b', page_text)
        final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
        driver.quit()
        return final_nums
    except Exception as e:
        st.error(f"❌ 雲端瀏覽器啟動失敗: {e}")
        return []

# --- [3. ABC 綜合加權演算法] ---
def advanced_analysis(all_nums, star):
    counts = Counter(all_nums)
    latest_20 = all_nums[:20]
    scores = {i: 0 for i in range(1, 81)}
    
    max_count = max(counts.values()) if counts else 1
    for num, count in counts.items():
        scores[num] += (count / max_count) * 50 # A. 熱門度
    for num in latest_20:
        scores[num] += 15 # B. 連莊感
    for num in range(1, 81):
        scores[num] += random.randint(0, 10) # C. 隨機擾動

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [item[0] for item in sorted_scores[:15]]
    prediction = sorted(random.sample(top_candidates, star))
    return prediction, sorted_scores, latest_20

# --- [4. 主程式頁面] ---
if st.button("🚀 啟動最強分析並推播"):
    with st.spinner('正在分析大數據...'):
        all_nums = fetch_data()
        
        if all_nums:
            prediction, full_scores, current_nums = advanced_analysis(all_nums, star_count)
            
            # --- 對獎邏輯 ---
            last_pred = None
            hit_nums = []
            if st.session_state.history:
                last_pred = st.session_state.history[-1]['推薦號碼']
                hit_nums = [n for n in last_pred if n in current_nums]
            
            st.session_state.history.append({
                "時間": time.strftime("%H:%M:%S"),
                "推薦號碼": prediction,
                "開獎結果": sorted(current_nums)
            })

            # --- UI 顯示 ---
            st.subheader(f"🔥 最新開獎：{sorted(current_nums)}")
            if last_pred:
                if hit_nums:
                    st.warning(f"🎯 上次預測中獎 {len(hit_nums)} 顆：{hit_nums}")
                else:
                    st.info("☹️ 上次預測未中獎。")
            
            st.markdown("---")
            col1, col2 = st.columns([1, 2])
            with col1:
                st.metric(label="本次最強推薦", value=str(prediction))
                # LINE 推播
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🎯 賓果最強預測：{prediction}\n📊 模式：ABC加權\n⏰ 時間：{time.strftime('%H:%M:%S')}"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    st.toast("✅ LINE 已通知所有人！")
                except Exception as e:
                    st.error(f"LINE 推送錯誤: {e}")

            with col2:
                score_df = pd.DataFrame(full_scores[:20], columns=['號碼', '戰鬥力']).set_index('號碼')
                st.bar_chart(score_df)

            st.dataframe(pd.DataFrame(st.session_state.history).iloc[::-1], use_container_width=True)
