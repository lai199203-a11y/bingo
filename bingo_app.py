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
    if "LINE_TOKEN" in st.secrets and "USER_IDS" in st.secrets:
        LINE_TOKEN = st.secrets["LINE_TOKEN"]
        USER_IDS = st.secrets["USER_IDS"]
    else:
        st.error(f"❌ Secrets 設定不完全！目前標籤有：{list(st.secrets.keys())}")
        st.stop()
except Exception as e:
    st.error(f"❌ 讀取 Secrets 發生錯誤: {e}")
    st.stop()

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 雲端最強分析儀", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (雲端正式版)")

# 初始化歷史紀錄
if 'history' not in st.session_state:
    st.session_state.history = []

# --- [2. 側邊欄控制區] ---
st.sidebar.header("📊 分析參數設定")
star_count = st.sidebar.slider("預測星數 (要選幾個號碼)", 1, 10, 3)
analysis_range = st.sidebar.select_slider(
    "分析樣本數 (期數)", 
    options=[100, 500, 1000, 2000], 
    value=1000
)
st.sidebar.info(f"💡 目前設定：分析最近 {analysis_range} 期數據，並推薦 {star_count} 個號碼。")

# --- [3. 雲端專用數據抓取邏輯] ---
def fetch_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.binary_location = "/usr/bin/chromium"
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        # 優先使用雲端路徑
        service = Service("/usr/bin/chromedriver") 
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(TARGET_URL)
        time.sleep(5) 
        
        page_text = driver.find_element("tag name", "body").text
        matches = re.findall(r'\b\d{2}\b', page_text)
        final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
        driver.quit()
        return final_nums
    except Exception as e:
        st.warning(f"⚠️ 優先路徑失敗，嘗試備用方案... ({e})")
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(TARGET_URL)
            page_text = driver.find_element("tag name", "body").text
            matches = re.findall(r'\b\d{2}\b', page_text)
            final_nums = [int(n) for n in matches if 1 <= int(n) <= 80]
            driver.quit()
            return final_nums
        except Exception as e2:
            st.error(f"❌ 數據抓取徹底失敗: {e2}")
            return []

# --- [4. ABC 綜合加權演算法] ---
def advanced_analysis(all_nums, star, limit):
    # 根據使用者選取的期數限制樣本 (一期 20 個號碼)
    target_nums = all_nums[:(limit * 20)]
    counts = Counter(target_nums)
    latest_20 = target_nums[:20]
    
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

# --- [5. 主程式畫面與執行] ---
if st.button("🚀 啟動最強分析並推播"):
    with st.spinner(f'正在分析最近 {analysis_range} 期大數據...'):
        all_raw_data = fetch_data()
        
        if all_raw_data:
            prediction, full_scores, current_nums = advanced_analysis(all_raw_data, star_count, analysis_range)
            
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
            st.subheader(f"🔥 最新開獎號碼：{sorted(current_nums)}")
            if last_pred:
                if hit_nums:
                    st.warning(f"🎯 上次預測 ({len(last_pred)}星) 中獎 {len(hit_nums)} 顆：{hit_nums}")
                else:
                    st.info("☹️ 上次預測未中獎，大數據調整中...")
            
            st.markdown("---")
            col_pred, col_chart = st.columns([1, 2])
            with col_pred:
                st.metric(label=f"本次推薦 {star_count} 星組合", value=str(prediction))
                # LINE 同步推播
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🎯 賓果最強預測：{prediction}\n📊 樣本：最近 {analysis_range} 期\n⏰ 時間：{time.strftime('%H:%M:%S')}"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    st.toast("✅ LINE 訊息已成功推播！")
                except Exception as e:
                    st.error(f"LINE 推送失敗: {e}")

            with col_chart:
                st.write("📊 本次加權戰鬥力 Top 20")
                score_df = pd.DataFrame(full_scores[:20], columns=['號碼', '分數']).set_index('號碼')
                st.bar_chart(score_df)

            st.write("📜 歷史紀錄 (最新在最上面)")
            st.dataframe(pd.DataFrame(st.session_state.history).iloc[::-1], use_container_width=True)
        else:
            st.error("無法抓取資料。請確認 GitHub 的 packages.txt 是否正確安裝了 chromium 與 chromium-driver。")
