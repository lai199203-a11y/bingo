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
# 程式會去你的 Streamlit "Secrets" 櫃子裡找標籤名稱為 LINE_TOKEN 與 USER_IDS 的東西
try:
    if "LINE_TOKEN" in st.secrets and "USER_IDS" in st.secrets:
        LINE_TOKEN = st.secrets["LINE_TOKEN"]
        USER_IDS = st.secrets["USER_IDS"]
    else:
        st.error(f"❌ Secrets 設定不完全！目前只偵測到：{list(st.secrets.keys())}。請確保 Secrets 裡有 LINE_TOKEN 與 USER_IDS。")
        st.stop()
except Exception as e:
    st.error(f"❌ 讀取 Secrets 發生錯誤: {e}")
    st.stop()

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 雲端最強分析儀", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (雲端正式版)")

if 'history' not in st.session_state:
    st.session_state.history = []

# 側邊欄
star_count = st.sidebar.slider("預測星數", 1, 10, 3)

# --- [2. 雲端專用數據抓取邏輯] ---
def fetch_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # 避免被網站偵測為機器人
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(TARGET_URL)
        time.sleep(5) 
        
        page_text = driver.find_element("tag name", "body").text
        # 抓取所有 01-80 的數字
        matches = re.findall(r'\b\d{2}\b', page_text)
        final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
        driver.quit()
        return final_nums
    except Exception as e:
        st.error(f"❌ 數據抓取失敗: {e}")
        return []

# --- [3. ABC 綜合加權演算法] ---
def advanced_analysis(all_nums, star):
    counts = Counter(all_nums)
    latest_20 = all_nums[:20]
    scores = {i: 0 for i in range(1, 81)}
    
    max_count = max(counts.values()) if counts else 1
    for num, count in counts.items():
        scores[num] += (count / max_count) * 50 # A. 頻率
    for num in latest_20:
        scores[num] += 15 # B. 手感
    for num in range(1, 81):
        scores[num] += random.randint(0, 10) # C. 擾動

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [item[0] for item in sorted_scores[:15]]
    prediction = sorted(random.sample(top_candidates, star))
    return prediction, sorted_scores, latest_20

# --- [4. 主程式畫面與執行] ---
if st.button("🚀 啟動最強分析並推播"):
    with st.spinner('數據計算中...'):
        all_nums = fetch_data()
        
        if all_nums:
            prediction, full_scores, current_nums = advanced_analysis(all_nums, star_count)
            
            # --- 對獎與歷史紀錄 ---
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

            # --- 顯示結果 ---
            st.subheader(f"🔥 最新開獎號碼：{sorted(current_nums)}")
            if last_pred:
                if hit_nums:
                    st.warning(f"🎯 上次預測 ({len(last_pred)}星) 中獎 {len(hit_nums)} 顆：{hit_nums}")
                else:
                    st.info("☹️ 上次預測未中獎。")
            
            st.markdown("---")
            col_pred, col_chart = st.columns([1, 2])
            with col_pred:
                st.metric(label=f"本次推薦 {star_count} 星組合", value=str(prediction))
                # LINE 推播給所有人
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🎯 賓果預測：{prediction}\n📊 模式：ABC綜合分析\n⏰ 時間：{time.strftime('%H:%M:%S')}"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    st.toast("✅ LINE 訊息已同步發送給兩位！")
                except Exception as e:
                    st.error(f"LINE 發送失敗: {e}")

            with col_chart:
                st.write("📊 前 20 名熱門戰鬥力")
                score_df = pd.DataFrame(full_scores[:20], columns=['號碼', '分數']).set_index('號碼')
                st.bar_chart(score_df)

            st.write("📜 歷史分析紀錄")
            st.dataframe(pd.DataFrame(st.session_state.history).iloc[::-1], use_container_width=True)
        else:
            st.error("無法抓取資料，請檢查網路或 pilio 網站狀態。")
