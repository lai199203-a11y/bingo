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

st.set_page_config(page_title="BINGO AI 專業分析儀", layout="wide")
st.title("🛡️ BINGO 賓果最強分析儀 (樣本精細調校版)")

if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_draw_data' not in st.session_state:
    st.session_state.last_draw_data = []

# --- [3. 側邊欄：修改樣本數單位] ---
st.sidebar.header("📊 參數設定")
star_count = st.sidebar.slider("預測星數", 1, 10, 2) # 預設改為 2 星

# 修改這裡：從原本的固定選項改為 100~2000，每 100 為一格
analysis_range = st.sidebar.slider(
    "分析樣本數 (期數)", 
    min_value=100, 
    max_value=2000, 
    value=500, 
    step=100
)

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
    except Exception as e:
        st.error(f"抓取失敗: {e}")
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

# --- [5. 強制檢查版回測功能] ---
def run_backtest(all_nums, star, limit):
    sim_rounds = 100 
    hits_count = {i: 0 for i in range(star + 1)}
    total_periods = len(all_nums) // 20
    status_text = st.empty()
    
    if total_periods < (sim_rounds + limit):
        sim_rounds = total_periods - limit - 2
        if sim_rounds <= 0:
            st.error(f"❌ 數據量不足！目前資料僅有 {total_periods} 期，無法支援分析樣本 {limit} 期的回測。請調小樣本數。")
            return None, 0
        status_text.warning(f"⚠️ 數據量較少，自動調整模擬期數為：{sim_rounds} 期")
    else:
        status_text.info(f"⏳ 開始模擬最近 {sim_rounds} 期之勝率...")

    bar = st.progress(0)
    for i in range(sim_rounds, 0, -1):
        cut_idx = i * 20
        past_data = all_nums[cut_idx : cut_idx + (limit * 20)]
        real_outcome = all_nums[cut_idx - 20 : cut_idx]
        pred = advanced_analysis(past_data, star, limit)
        hits = len([n for n in pred if n in real_outcome])
        hits_count[hits] += 1
        if i % 10 == 0 or i == 1:
            bar.progress((sim_rounds - i + 1) / sim_rounds)
            status_text.info(f"運算中... 已完成 {sim_rounds - i + 1} / {sim_rounds} 期")
            
    status_text.success(f"✅ 回測完成！已分析完畢最近 {sim_rounds} 期數據。")
    return hits_count, sim_rounds

# --- [6. UI 執行邏輯] ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 啟動預測並自動對獎"):
        with st.spinner('連線抓取最新獎號...'):
            all_raw = fetch_data()
            current_20 = sorted(all_raw[:20]) if all_raw else []
            if current_20:
                now_t = get_taipei_time()
                if st.session_state.last_draw_data != current_20:
                    for record in st.session_state.history:
                        if record.get("開獎結果") == "等待開獎...":
                            pred_nums = record.get("預測號碼")
                            hits = [n for n in pred_nums if n in current_20]
                            record["開獎結果"] = str(current_20)
                            record["中獎"] = f"中 {len(hits)} 顆 ({hits})"
                    
                    new_pred = advanced_analysis(all_raw, star_count, analysis_range)
                    st.session_state.history.insert(0, {
                        "時間": now_t, "預測號碼": new_pred, "開獎結果": "等待開獎...", "中獎": "-"
                    })
                    st.session_state.last_draw_data = current_20
                    try:
                        line_bot_api = LineBotApi(LINE_TOKEN)
                        msg = f"\n🔮 新預測：{new_pred}\n⏰ 台北：{now_t}\n(針對下一期)"
                        for uid in USER_IDS: line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    except: pass
                else:
                    st.info(f"⌛ {now_t}：獎號尚未更新。")

with col2:
    if st.button("🧪 跑歷史回測 (顯示進度)"):
        all_raw = fetch_data()
        if all_raw:
            results, rounds = run_backtest(all_raw, star_count, analysis_range)
            if results:
                st.markdown(f"#### 📊 最近 {rounds} 期命中分佈")
                res_df = pd.DataFrame({
                    "中獎數": [f"中 {k} 顆" for k in results.keys()],
                    "次數": list(results.values()),
                    "命中率": [f"{(v/rounds)*100:.1f}%" for v in results.values()]
                })
                st.table(res_df)

# --- [7. 顯示結果] ---
st.markdown("---")
if st.session_state.history:
    st.subheader(f"📟 最新開獎 (台北時間)：{st.session_state.last_draw_data}")
    df = pd.DataFrame(st.session_state.history)
    valid_cols = ["時間", "預測號碼", "開獎結果", "中獎"]
    df_display = df[[c for c in valid_cols if c in df.columns]]
    st.dataframe(df_display, use_container_width=True)
else:
    st.info("目前沒有紀錄，請按左上方按鈕開始。")
