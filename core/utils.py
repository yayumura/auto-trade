import jpholiday
from datetime import datetime, time, timedelta

def is_business_day(dt):
    """土日・祝日・年末年始(12/31-1/3)を判定"""
    if dt.weekday() >= 5: # 土日
        return False
    if jpholiday.is_holiday(dt.date()): # 祝日
        return False
    # 年末年始休暇 (12/31 - 1/3)
    if (dt.month == 12 and dt.day == 31) or (dt.month == 1 and dt.day in [1, 2, 3]):
        return False
    return True

def get_previous_business_day(dt):
    """前営業日を取得する"""
    temp = dt - timedelta(days=1)
    while not is_business_day(temp):
        temp -= timedelta(days=1)
    return temp.date()

def calculate_effective_age(last_update, current_time):
    """
    取引時間（9:00-11:30, 12:30-15:30）のみをカウントした実効経過秒数を計算する。
    last_update が数日前の引け値であっても、取引時間外を除外して計算する。
    """
    if last_update >= current_time:
        return 0.0

    # 簡易化のため、1分ステップで時間を進めて取引時間内かを判定する（精度は1分で十分）
    # 大量に離れている（数週間など）場合は非常に重くなるため、最大48時間（2営業日分）程度に制限
    total_effective_seconds = 0
    temp_time = last_update.replace(second=0, microsecond=0)
    
    # 取引時間の定義
    morn_start = time(9, 0)
    morn_end = time(11, 30)
    aft_start = time(12, 30)
    aft_end = time(15, 30)
    
    # 1分ずつ進める
    step = timedelta(minutes=1)
    limit_time = current_time
    
    # 効率化のため、日をまたぐ場合の初期スキップ
    while temp_time + timedelta(days=1) < limit_time:
        if is_business_day(temp_time):
            # 1日分の取引時間は 2.5h (150m) + 3h (180m) = 330分
            total_effective_seconds += 330 * 60
        temp_time += timedelta(days=1)

    while temp_time < limit_time:
        if is_business_day(temp_time):
            t = temp_time.time()
            if (morn_start <= t < morn_end) or (aft_start <= t < aft_end):
                total_effective_seconds += 60
        temp_time += step
        
    return float(total_effective_seconds)
