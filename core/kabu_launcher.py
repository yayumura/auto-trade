import time
import subprocess
import os
import psutil
import requests
from pywinauto.application import Application
from core.config import KABUCOM_LOGIN_PASSWORD, TRADE_MODE
from core.log_setup import send_discord_notify

def is_admin():
    """Pythonが管理者権限で実行されているか確認する"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def ensure_kabu_station_running():
    """
    kabuステーションが起動していない場合、自動起動してログインする。
    """
    # TRADE_MODEチェック（カブコムモード以外は何もしない）
    if TRADE_MODE not in ["KABUCOM_LIVE", "KABUCOM_TEST"]:
        return True

    print("\n[Launcher] 🚀 kabuステーションの状態を確認します...")

    # 管理者権限チェック（警告のみ）
    if not is_admin():
        print("⚠️ [WARNING] プロセスが管理者権限で実行されていません。GUI操作が失敗する可能性があります。")

    # すでに起動しているかプロセスをチェック
    for proc in psutil.process_iter(['name']):
        try:
            # プロセス名も KabuS.exe に合わせる
            if proc.info['name'] in ['KabuS.exe', 'kabu.station.exe']:
                print(f"✅ kabuステーション({proc.info['name']})は既に起動しています。")
                return _wait_for_api_server()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print("🟢 kabuステーションを新しく起動します...")
    
    # インストールパス候補の探索
    paths = [
        r"C:\Users\yayum\AppData\Local\kabuStation\KabuS.exe", # ユーザー環境の実際のパス
        r"C:\Program Files (x86)\kabu.com\kabu.station\kabu.station.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''), r"kabu.com\kabu.station\kabu.station.exe"),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), r"kabuStation\KabuS.exe")
    ]
    
    kabu_path = None
    for p in paths:
        if p and os.path.exists(p):
            kabu_path = p
            break
            
    if not kabu_path:
        print("❌ kabuステーションの実行ファイルが見つかりませんでした。")
        print(f"   探索場所: {', '.join([p for p in paths if p])}")
        return False

    try:
        subprocess.Popen(kabu_path)
        print(f"🖥️  プロセスを起動しました: {kabu_path}")
    except Exception as e:
        print(f"❌ アプリケーションの起動に失敗しました: {e}")
        return False

    # ログインウィンドウが出るのを待つ
    login_window = None
    timeout = 60
    start_time = time.time()
    print(f"⏳ ログインウィンドウを探索中 (PIDベース)...")
    
    while time.time() - start_time < timeout:
        try:
            # PIDを取得
            target_pid = None
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] in ['KabuS.exe', 'kabu.station.exe']:
                    target_pid = proc.info['pid']
                    break
            
            if target_pid:
                # PIDに接続してウィンドウを探索
                try:
                    app = Application(backend="uia").connect(process=target_pid, timeout=5)
                    for w in app.windows():
                        if "ログイン" in w.window_text():
                            # パスワード入力欄があるか確認して、本物かどうか判定する
                            if w.child_window(auto_id="PasswordTextBox").exists(timeout=1):
                                login_window = w
                                print(f"🎯 ログインウィンドウを捕捉しました (PID: {target_pid})")
                                break
                    if login_window: break
                except:
                    pass
        except Exception:
            pass
        time.sleep(2)
    
    if not login_window:
        msg = "⚠️ [kabuステーション] ログイン画面の自動認識に失敗しました（Web版ログイン画面の可能性があります）。手動でログインを行ってください。"
        print(msg)
        send_discord_notify(msg)
        return _wait_for_manual_login_and_api(timeout_mins=10) # 手動待ちを長めにとる

    try:
        # パスワードの確認
        if not KABUCOM_LOGIN_PASSWORD or KABUCOM_LOGIN_PASSWORD == "your_app_password":
            msg = "⚠️ [kabuステーション] .env に有効なログインパスワードが設定されていないため、手動ログインが必要です。"
            print(msg)
            send_discord_notify(msg)
            return _wait_for_manual_login_and_api()
            
        print("🔑 パスワードを自動入力しています...")
        password_edit = login_window.child_window(auto_id="PasswordTextBox")
        password_edit.type_keys(KABUCOM_LOGIN_PASSWORD, with_spaces=True)
        time.sleep(1)

        print("🖱️  ログインボタンをクリックします...")
        login_button = login_window.child_window(title="ログイン", control_type="Button")
        login_button.click()
        
        msg = "✅ [kabuステーション] ログインボタンを押下しました。ワンタイムパスワード等が必要な場合は手動で入力してください。"
        print(msg)
        send_discord_notify(msg) # OTP入力が必要かもしれないので通知
        return _wait_for_manual_login_and_api(timeout_mins=5)
        
    except Exception as e:
        msg = f"⚠️ [kabuステーション] 自動ログイン操作中にエラーが発生しました（OTP画面表示など）: {e}\n💡 手動でのログインを待機します。"
        print(msg)
        send_discord_notify(msg)
        return _wait_for_manual_login_and_api(timeout_mins=5)

def _wait_for_manual_login_and_api(timeout_mins=5):
    """ユーザーが手動でログインを完了し、APIサーバーが立ち上がるのを待つ"""
    print(f"⏳ ログイン完了（およびAPIサーバーの起動）を待機しています（最長{timeout_mins}分）...")
    print("🔔 ワンタイムパスワード等の入力が必要な場合は、kabuステーションの画面で操作を行ってください。")
    
    start_time = time.time()
    while time.time() - start_time < (timeout_mins * 60):
        if _wait_for_api_server(timeout_sec=10, silent=True):
            return True
        time.sleep(5)
    
    print(f"❌ {timeout_mins}分以内にログインが確認できませんでした。")
    return False

def _wait_for_api_server(timeout_sec=60, silent=False):
    """APIサーバー（Port 18080/18081）の起動をポーリングで待機する"""
    port = 18080 if TRADE_MODE == "KABUCOM_LIVE" else 18081
    url = f"http://localhost:{port}/kabusapi/auth"
    
    start_wait = time.time()
    if not silent:
        print(f"⏳ APIサーバーの起動を待機中 (Port {port})への疎通確認を開始します（最長{timeout_sec}秒）...")
    
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            requests.get(url, timeout=2)
            if not silent: print(f"✨ [Success] APIサーバーの稼働を確認しました。")
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(2)
        except Exception:
            if not silent: print(f"✨ [Success] APIサーバーの稼働を確認しました。")
            return True
            
    if not silent:
        print("❌ APIサーバーの起動確認がタイムアウトしました。")
    return False

def terminate_kabu_station():
    """
    起動中のkabuステーションのプロセスを終了させる。
    """
    print("\n[Launcher] 🛑 kabuステーションを終了します...")
    target_processes = ['KabuS.exe', 'kabu.station.exe']
    found = False
    
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in target_processes:
                print(f"📦 プロセス {proc.info['name']} (PID: {proc.pid}) を終了しています...")
                proc.terminate() # 優しく終了
                # 3秒待っても終わらなければ強制終了
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    print(f"⚠️ 終了が遅いため強制終了します (PID: {proc.pid})")
                    proc.kill()
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    if found:
        print("✅ kabuステーションを終了しました。")
        send_discord_notify("🛑 [システム終了] kabuステーションを正常に終了しました。")
    else:
        print("ℹ️ 起動中のkabuステーションは見つかりませんでした。")
    return found

def check_api_health():
    """
    APIサーバーが現在稼働中（ログイン済み）かを確認する。
    """
    return _wait_for_api_server(timeout_sec=2, silent=True)
