import urllib.parse
import feedparser
import re
from google import genai
from core.config import GEMINI_API_KEY, GROQ_API_KEY, GEMINI_MODEL

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    gemini_client = None

if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

def clean_text_for_ai(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    return re.sub(r'[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', '', text).strip()

def get_recent_news(code, name):
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "ニュースなし"
    except:
        return ""

def ai_qualitative_filter(code, name, news_text):
    if not gemini_client:
        return True, "API Key Missing (Skipped)"
        
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
    
    try:
        response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = response.text.strip().upper()
        if text.startswith("YES") or "YES" in text.split('\n')[0]:
            return False, text.replace('\n', ' ') 
        return True, "問題なし"
    except Exception as e:
        err_msg = str(e).lower()
        if groq_client and ("429" in err_msg or "quota" in err_msg):
            try:
                g_response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1
                )
                text = g_response.choices[0].message.content.strip().upper()
                if "YES" in text.split('\n')[0]: return False, "Groq:悪材料検知"
                return True, "Groq:問題なし"
            except:
                pass
        return True, "AI判定エラー（一時承認）"
