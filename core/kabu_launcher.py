import time
import subprocess
import os
import psutil
import requests
from email.utils import parsedate_to_datetime

from core.config import (
    KABUCOM_API_PASSWORD,
    KABUCOM_LOGIN_PASSWORD,
    KABUCOM_PORT_LIVE,
    KABUCOM_PORT_TEST,
    TRADE_MODE,
    is_placeholder_secret,
)
from core.log_setup import send_discord_notify

def is_admin():
    """Pythonが管理者権限で実行されているか確認する"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def _resolve_kabu_port() -> int:
    return KABUCOM_PORT_LIVE if TRADE_MODE == "KABUCOM_LIVE" else KABUCOM_PORT_TEST


def _resolve_kabu_base_url() -> str:
    return f"http://localhost:{_resolve_kabu_port()}/kabusapi"


def is_api_port_reachable(timeout_sec=60, silent=False) -> bool:
    """kabuステーションのHTTPポートが応答するかを確認する。401/403 でも疎通としては成功とみなす。"""
    port = _resolve_kabu_port()
    url = f"http://localhost:{port}/kabusapi/board/7203@1"

    if not silent:
        print(f"⏳ APIポートの疎通を確認中 (Port {port})...（最長{timeout_sec}秒）")

    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout_sec:
        try:
            res = requests.get(url, timeout=2)
            if res is not None:
                if not silent:
                    print("✨ [Success] APIポートの応答を確認しました。")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception:
            pass
        time.sleep(2)

    if not silent:
        print("❌ APIポートの疎通確認がタイムアウトしました。")
    return False


def is_api_authenticated_ready(timeout_sec=60, silent=False) -> bool:
    """kabuステーションAPIに認証でき、業務 API を使える状態かを確認する。"""
    if is_placeholder_secret(KABUCOM_API_PASSWORD):
        if not silent:
            print("⚠️ API認証確認に必要な KABUCOM_API_PASSWORD が未設定です。")
        return False

    base_url = _resolve_kabu_base_url()
    url = f"{base_url}/token"
    headers = {"Content-Type": "application/json"}
    data = {"APIPassword": KABUCOM_API_PASSWORD}

    if not silent:
        print(f"⏳ API認証の完了を確認中 (Port {_resolve_kabu_port()})...（最長{timeout_sec}秒）")

    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout_sec:
        try:
            res = requests.post(url, headers=headers, json=data, timeout=5)
            if res is not None and res.status_code == 200:
                try:
                    token = res.json().get("Token")
                except Exception:
                    token = None
                if token:
                    if not silent:
                        print("✨ [Success] API認証済みであることを確認しました。")
                    return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception:
            pass
        time.sleep(2)

    if not silent:
        print("❌ API認証完了の確認がタイムアウトしました。")
    return False

def ensure_kabu_station_running():
    """
    kabuステーションが起動していない場合、自動起動してログインする。
    """
    # TRADE_MODEチェック（カブコムモード以外は何もしない）
    if TRADE_MODE not in ["KABUCOM_LIVE", "KABUCOM_TEST"]:
        return True

    print("\n[Launcher] 🚀 kabuステーションの状態を確認します...")

    try:
        from pywinauto.application import Application
    except Exception as exc:
        print(f"⚠️ [Launcher] pywinauto を利用できないため kabuステーション起動をスキップします: {exc}")
        return False

    # 管理者権限チェック（警告のみ）
    if not is_admin():
        print("⚠️ [WARNING] プロセスが管理者権限で実行されていません。GUI操作が失敗する可能性があります。")

    # すでに起動しているかプロセスをチェック
    for proc in psutil.process_iter(['name']):
        try:
            # プロセス名も KabuS.exe に合わせる
            if proc.info['name'] in ['KabuS.exe', 'kabu.station.exe']:
                print(f"✅ kabuステーション({proc.info['name']})は既に起動しています。")
                return _wait_for_manual_login_and_api(timeout_mins=10)
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
        # 古い残存プロセスがあれば一度掃除する（二重起動防止とクリーンな状態の確保）
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] in ['KabuS.exe', 'kabu.station.exe']:
                     proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(1)

        # 起動の安定性を高めるため、cwd を exe の場所に固定する
        kabu_dir = os.path.dirname(kabu_path)
        subprocess.Popen([kabu_path], cwd=kabu_dir)
        print(f"🖥️  アプリケーションを起動しました: {kabu_path} (CWD: {kabu_dir})")
        
        # 少し待ってからプロセスが本当に存在するか軽くチェック
        time.sleep(3)
        found_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] in ['KabuS.exe', 'kabu.station.exe']:
                found_pid = proc.info['pid']
                break
        
        if not found_pid:
            print("⚠️ プロセスを開始しましたが、psutilで確認できませんでした。起動に時間がかかっているか、失敗した可能性があります。")
        else:
            print(f"✅ プロセスを確認しました (PID: {found_pid})")

    except Exception as e:
        print(f"❌ アプリケーションの起動に失敗しました: {e}")
        return False

    # ログインウィンドウが出るのを待つ
    login_window = None
    timeout = 60
    start_time = time.monotonic()
    print(f"⏳ ログインウィンドウを探索中 (PIDベース)...")
    
    while time.monotonic() - start_time < timeout:
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
        if is_placeholder_secret(KABUCOM_LOGIN_PASSWORD):
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

def _describe_api_readiness_failure(*, port_reachable: bool, api_password_ready: bool) -> str:
    if not port_reachable:
        return "api_port_not_listening"
    if not api_password_ready:
        return "api_password_missing"
    return "api_token_authentication_failed"


def _wait_for_manual_login_and_api(timeout_mins=5):
    """ユーザーが手動でログインを完了し、APIサーバーが立ち上がるのを待つ"""
    print(f"⏳ ログイン完了（およびAPI認証の完了）を待機しています（最長{timeout_mins}分）...")
    print("🔔 ワンタイムパスワード等の入力が必要な場合は、kabuステーションの画面で操作を行ってください。")
    
    start_time = time.monotonic()
    while time.monotonic() - start_time < (timeout_mins * 60):
        if is_api_authenticated_ready(timeout_sec=10, silent=True):
            return True
        time.sleep(5)

    port_reachable = is_api_port_reachable(timeout_sec=2, silent=True)
    failure_reason = _describe_api_readiness_failure(
        port_reachable=port_reachable,
        api_password_ready=not is_placeholder_secret(KABUCOM_API_PASSWORD),
    )
    if failure_reason == "api_port_not_listening":
        print(
            f"❌ {timeout_mins}分以内にAPIポートが起動しませんでした。"
            "kabuステーション右上の </> を右クリックし、APIシステム設定で"
            "「APIを利用する」とAPIパスワードを設定してから、kabuステーションを再起動してください。"
        )
    elif failure_reason == "api_password_missing":
        print("❌ APIポートは起動していますが、KABUCOM_API_PASSWORD が未設定です。")
    else:
        print(
            "❌ APIポートは起動していますが、token認証に失敗しました。"
            "KABUCOM_API_PASSWORD とkabuステーションのAPIシステム設定を照合してください。"
        )
    return False

def _wait_for_api_server(timeout_sec=60, silent=False):
    """APIサーバー（Port 18080/18081）の起動をポーリングで待機する。"""
    return is_api_port_reachable(timeout_sec=timeout_sec, silent=silent)

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
    APIサーバーが稼働し、認証済みで業務 API を使えるかを確認する。
    """
    if not is_api_port_reachable(timeout_sec=2, silent=True):
        return False
    return is_api_authenticated_ready(timeout_sec=2, silent=True)
