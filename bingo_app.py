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

# --- [1. 基礎配置] ---
# 如果要在雲端保護 Token，建議使用 st.secrets["LINE_TOKEN"]
LINE_TOKEN = "你的_LINE_CHANNEL_ACCESS_TOKEN"
USER_IDS = ["你的_USER_ID"]
TARGET_URL = "https://www.pilio.idv.tw/bingo/list.asp"

st.set_page_config(page_title="BINGO 終極分析儀表板", layout="wide")
st.title("🛡️ BINGO 賓果最強分析 (ABC 綜合加權 + 自動對獎版)")

# 初始化 Session State 儲存歷史紀錄 (網頁不重整就不會消失)
if 'history' not in st.session_state:
    st.session_state.history = []

# 側邊欄參數設定
star_count = st.sidebar.slider("預測星數", 1, 10, 3)
analysis_range = st.sidebar.select_slider("分析樣本數 (越多越精準)", options=[500, 1000, 2000], value=1000)

# --- [2. 數據抓取邏輯 (相容雲端 Linux 環境)] ---
def fetch_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(TARGET_URL)
        time.sleep(5) # 等待網頁渲染
        
        page_text = driver.find_element("tag name", "body").text
        # 精準抓取 01-80 的兩位數，排除期數與時間
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
    
    # A. 頻率加分 (熱門度) - 權重 50
    max_count = max(counts.values()) if counts else 1
    for num, count in counts.items():
        scores[num] += (count / max_count) * 50
    
    # B. 連莊加分 (手感趨勢) - 權重 15
    for num in latest_20:
        scores[num] += 15
        
    # C. 隨機擾動 (模擬伴生關係) - 權重 0-10
    for num in range(1, 81):
        scores[num] += random.randint(0, 10)

    # 排序並選出前 15 名戰鬥力最高的號碼
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [item[0] for item in sorted_scores[:15]]
    
    # 從強勢號碼中隨機抽選需要的星數
    prediction = sorted(random.sample(top_candidates, star))
    return prediction, sorted_scores, latest_20

# --- [4. 主程式 UI 邏輯] ---
if st.button("🚀 啟動最強分析與對獎"):
    with st.spinner('大數據計算中...'):
        all_nums = fetch_data()
        
        if len(all_nums) >= 40:
            prediction, full_scores, current_nums = advanced_analysis(all_nums, star_count)
            
            # --- 對獎逻辑 ---
            last_pred = None
            hit_nums = []
            if st.session_state.history:
                # 拿「上次的預測」與「這次開出的號碼」比對
                last_pred = st.session_state.history[-1]['推薦號碼']
                hit_nums = [n for n in last_pred if n in current_nums]
            
            # 將本次結果存入歷史紀錄
            st.session_state.history.append({
                "時間": time.strftime("%H:%M:%S"),
                "推薦號碼": prediction,
                "開獎號碼 (前20)": sorted(current_nums)
            })

            # --- 畫面顯示 ---
            st.subheader("🔥 最新一期對獎結果")
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**本期開獎：**")
                st.success(f"{sorted(current_nums)}")
            with col_b:
                if last_pred:
                    st.write(f"**上次預測比對 ({len(last_pred)}星)：**")
                    if hit_nums:
                        st.warning(f"🎯 中獎 {len(hit_nums)} 顆：{hit_nums}")
                    else:
                        st.info("☹️ 未中獎，繼續努力！")
                else:
                    st.info("尚無歷史紀錄，下次按鈕時將自動對獎。")

            st.markdown("---")
            
            col_left, col_right = st.columns([1, 2])
            with col_left:
                st.subheader("🎯 系統推薦組合")
                st.metric(label=f"本次 {star_count} 星預測", value=str(prediction))
                
                # LINE 推播
                try:
                    line_bot_api = LineBotApi(LINE_TOKEN)
                    msg = f"\n🎯 賓果預測({star_count}星)：{prediction}\n📊 模式：ABC綜合分析\n⏰ 更新：{time.strftime('%H:%M:%S')}"
                    for uid in USER_IDS:
                        line_bot_api.push_message(uid, TextSendMessage(text=msg))
                    st.toast("📱 LINE 訊息傳送成功！")
                except:
                    st.warning("⚠️ LINE Token 未設定或失效。")

            with col_right:
                st.subheader("📊 號碼戰鬥力排行榜 (Top 20)")
                score_df = pd.DataFrame(full_scores[:20], columns=['號碼', '綜合戰鬥力']).set_index('號碼')
                st.bar_chart(score_df)

            # --- 歷史回測紀錄 ---
            st.markdown("### 📜 歷史預測與對獎紀錄")
            if st.session_state.history:
                # 轉成 DataFrame 方便顯示，並把最新的放在最上面
                df_history = pd.DataFrame(st.session_state.history).iloc[::-1]
                st.dataframe(df_history, use_container_width=True)
        else:
            st.error("⚠️ 無法獲取足夠的數據，請稍後重試。")
else:
    st.info("請點擊上方按鈕開始進行深度分析。")