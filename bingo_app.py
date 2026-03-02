import streamlit as st
import pandas as pd
import re, random, time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from collections import Counter
from linebot import LineBotApi
from linebot.models import TextSendMessage

# --- [1. 讀取 Secrets] ---
try:
    LINE_TOKEN = st.secrets["LINE_TOKEN"]
    USER_IDS = st.secrets["USER_IDS"]
except:
    st.error("❌ 讀取 Secrets 失敗，請確認 Streamlit 後台設定。")
    st.stop()

# --- [2. 台北時間工具] ---
def get_taipei_time():
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%m/%d %H:%M:%S")

TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO AI 模擬對獎版", layout="wide")
st.title("🛡️ BINGO 賓果最強分析儀 (欄位修正版)")

# 初始化與修正舊資料
if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_draw_data' not in st.session_state:
    st.session_state.last_draw_data = []

# --- [3. 側邊欄] ---
st.sidebar.header("📊 參數設定")
star_count = st.sidebar.slider("預測星數", 1, 10, 3)
analysis_range = st.sidebar.select_slider("分析樣本數 (期數)", options=[100, 500, 1000, 2000], value=1000)

if st.sidebar.button("🗑️ 清除所有歷史紀錄"):
    st.session_state.history = []
    st.session_state.last_draw_data = []
    st.rerun()

# --- [4. 核心功能] ---
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

def run_backtest(all_nums, star, limit):
    sim_rounds = 100
    hits_count = {i: 0 for i in range(star + 1)}
    if len(all_nums) < (sim_rounds + limit) * 20:
        sim_rounds = (len(all_nums) // 20) - limit
        if sim_rounds <= 0: return None, 0
    bar = st.progress(0)
    for i in range(sim_rounds, 0, -1):
        cut_idx = i * 20
        past_data = all_nums[cut_idx : cut_idx + (limit * 20)]
        real_outcome = all_nums[cut_idx - 20 : cut_idx]
        pred = advanced_analysis(past_data, star, limit)
        hits = len([n for n in pred if n in real_outcome])
        hits_count[hits] += 1
        bar.progress((sim_rounds - i + 1) / sim_rounds)
    return hits_count, sim_rounds

# --- [5. 執行邏輯] ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 啟動預測並自動對獎"):
        with st.spinner('抓取數據中...'):
            all_raw = fetch_data()
            current_20 = sorted(all_raw[:20]) if all_raw else []
            if current_20:
                now_t = get_taipei_time()
                # 檢查是否需要更新對獎
                if st.session_state.last_draw_data != current_20:
                    for record in st.session_state.history:
                        if record.get("開獎結果") == "等待開獎...":
                            pred_nums = record.get("預測號碼")
                            hits = [n for n in pred_nums if n in current_20]
                            record["開獎結果"] = str(current_20)
                            record["中獎"] = f"中 {len(hits)} 顆 ({hits})"
                    
                    # 產生新預測
                    new_pred = advanced_analysis(all_raw, star_count, analysis_range)
                    st.session_state.history.insert(0, {
                        "時間": now_t,
                        "預測號碼": new_pred,
                        "開獎結果": "等待開獎...",
                        "中獎": "-"
                    })
                    st.session_state.last_draw_data = current_20
                    # LINE 推播
                    try:
                        line_bot_api = LineBotApi(LINE_TOKEN)
                        msg = f"\n🔮 新預測：{new_pred}\n⏰ 台北：{now_t}\n(針對下一期)"
                        for uid in USER_IDS: line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    except: pass
                else:
                    st.info(f"⌛ {now_t}：獎號尚未更新。")

with col2:
    if st.button("🧪 跑 100 期歷史回測"):
        all_raw = fetch_data()
        if all_raw:
            with st.spinner('回測中...'):
                results, rounds = run_backtest(all_raw, star_count, analysis_range)
                if results:
                    st.success(f"✅ 完成 {rounds} 期模擬")
                    st.table(pd.DataFrame({
                        "中獎數": [f"中 {k} 顆" for k in results.keys()],
                        "次數": list(results.values()),
                        "機率": [f"{(v/rounds)*100:.1f}%" for v in results.values()]
                    }))

# --- [6. 顯示結果] ---
st.markdown("---")
if st.session_state.history:
    st.subheader(f"📟 最新開獎 (台北時間)：{st.session_state.last_draw_data}")
    # 轉換為 DataFrame 前，確保只選取我們需要的這四個欄位，避免舊資料干擾
    df = pd.DataFrame(st.session_state.history)
    valid_cols = ["時間", "預測號碼", "開獎結果", "中獎"]
    # 只顯示存在的有效欄位
    df_display = df[[c for c in valid_cols if c in df.columns]]
    st.dataframe(df_display, use_container_width=True)
else:
    st.info("目前沒有紀錄，請按下啟動按鈕。")
