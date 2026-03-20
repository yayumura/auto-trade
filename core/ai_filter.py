import urllib.parse
import feedparser
import re
import requests
import concurrent.futures
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

def get_recent_news(code, name, timeout=5):
    clean_name = re.sub(r'\s+', ' ', name).strip()
    query = urllib.parse.quote(f"{code} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        # V2-M2: requestsでタイムアウト付き取得
        res = requests.get(rss_url, timeout=timeout)
        feed = feedparser.parse(res.content)
        titles = [entry.title for entry in feed.entries[:5]]
        return " | ".join(titles) if titles else "ニュースなし"
    except Exception as e:
        print(f"⚠️ ニュース取得タイムアウト/エラー({code}): {e}")
        return "ニュースなし"

def _ai_qualitative_filter_core(code, name, news_text):
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
        text = response.text.upper()
        # 最初の2行程度をチェックして、YESが含まれているか判定する（解説が先行する場合に対応）
        lines = [line.strip() for line in text.split('\n') if line.strip()][:2]
        
        has_yes = False
        full_reason = text.replace('\n', ' ')
        
        for line in lines:
            if line.startswith("YES") or re.search(r'\bYES\b', line):
                has_yes = True
                break
        
        if has_yes:
            return False, full_reason
        return True, "問題なし"
    except Exception as e:
        err_msg = str(e).lower()
        # クォータ制限などの一時的なエラーの場合のみGroqへ逃げる
        if groq_client and ("429" in err_msg or "quota" in err_msg or "limit" in err_msg):
            try:
                g_response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                text = g_response.choices[0].message.content.upper()
                lines = [line.strip() for line in text.split('\n') if line.strip()][:2]
                has_yes = any("YES" in line for line in lines)
                if has_yes: return False, f"Groq判定: 悪材料検知 ({text[:50]}...)"
                return True, "Groq判定: 問題なし"
            except Exception as ge:
                print(f"⚠️ Groqフェイルオーバーも失敗: {ge}")
        
        # APIが完全に死んでいる、あるいは不明なエラーの場合は、機会損失を防ぐため「一時承認」
        return True, f"AI判定エラー回避(一時承認): {e}"

def ai_qualitative_filter(code, name, news_text, timeout=10):
    """V2-M2: APIやネットワークのスタックを防ぐため、タイムアウト付きでAI判定を実行する"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_ai_qualitative_filter_core, code, name, news_text)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print(f"⚠️ {code} のAI判定がAPIタイムアウト({timeout}秒)しました。機会損失を防ぐため一時承認します。")
            return True, "AI判定タイムアウト(一時承認)"
        except Exception as e:
            return True, f"AI実行時エラー回避(一時承認): {e}"
