import urllib.parse
import feedparser
import re
import requests
import concurrent.futures
from google import genai
from core.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

# Singular Intelligence (Primary)
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    gemini_client = None

# Failover Intelligence (Secondary/Backup)
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        print("⚠️ [Safety Warning] 'groq' library not found. Running without AI Failover.")

# Multithreaded AI Executor for non-blocking analysis
ai_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def clean_text_for_ai(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    return re.sub(r'[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', text).strip()

def get_recent_news(code, name, timeout=5):
    """Fetches high-signal news via Google News RSS to detect fatal risks."""
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        res = requests.get(rss_url, timeout=timeout)
        feed = feedparser.parse(res.content)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "ニュースなし"
    except Exception as e:
        print(f"⚠️ News Fetch Error ({code}): {e}")
        return "ニュースなし"

def _ai_qualitative_filter_core(code, name, news_text):
    """The Final Gate: Qualitative analysis of news for fatal red flags with Failover Support."""
    if not gemini_client and not groq_client:
        return True, "All AI Proxies Missing (Auto-Pass)"
        
    safe_name = clean_text_for_ai(name)
    safe_news = clean_text_for_ai(news_text)

    prompt = f"""
    対象銘柄: {safe_name} ({code})
    最新ニュース: {safe_news}
    
    あなたは機関投資家のコンプライアンス・リスク管理者です。
    この銘柄のニュースの中に、直近で「下方修正」「粉飾決算」「不祥事・スキャンダル」「第三者割当増資(希薄化)」「上場廃止懸念」などの【致命的・突発的な悪材料】が含まれているか判定してください。
    
    【出力ルール】
    1行目: YES または NO (悪材料があればYES、特になければNO)
    2行目: 理由(短く)
    """
    
    # --- PHASE 1: PRIMARY (GEMINI) ---
    try:
        if gemini_client:
            response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            text = response.text.upper()
            lines = [line.strip() for line in text.split('\n') if line.strip()][:2]
            if any(line.startswith("YES") or re.search(r'\bYES\b', line) for line in lines):
                return False, f"Gemini判定: 悪材料検知 ({text[:100]}...)"
            return True, "Gemini判定: 問題なし"
    except Exception as e:
        err_msg = str(e).lower()
        print(f"⚠️ Primary AI (Gemini) Exception ({code}): {err_msg}")
        
        # --- PHASE 2: FAILOVER (GROQ/LLAMA) ---
        # Trigger failover only on rate limits or API instability
        if groq_client and ("429" in err_msg or "quota" in err_msg or "limit" in err_msg or "error" in err_msg):
            try:
                print(f"🔄 [Failover] Activating Groq/Llama for {code}...")
                g_response = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = g_response.choices[0].message.content.upper()
                lines = [line.strip() for line in text.split('\n') if line.strip()][:2]
                if any("YES" in line for line in lines):
                    return False, f"Groq判定: 悪材料検知 ({text[:100]}...)"
                return True, "Groq判定: 問題なし"
            except Exception as ge:
                print(f"⚠️ Failover AI (Groq) also failed for {code}: {ge}")

    # In case of total AI blackout, we prioritize signal flow to avoid opportunity loss
    return True, f"AI Blackout Strategy: Auto-Approved for {code}"

def ai_qualitative_filter(code, name, news_text, timeout=10):
    """Wrapper to ensure AI analysis never blocks the main trading loop."""
    try:
        future = ai_executor.submit(_ai_qualitative_filter_core, code, name, news_text)
        return future.result(timeout=timeout)
    except Exception as e:
        return True, f"AI判定スキップ (Safety Pass): {e}"
