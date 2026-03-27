import pywinauto
from pywinauto import Desktop
import psutil
import time

def dump_ui_tree():
    print("--- PID-based UI Tree Dump ---")
    kabus_pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'KabuS.exe':
            kabus_pids.append(proc.info['pid'])
    
    if not kabus_pids:
        print("No KabuS.exe process found.")
        return

    for pid in kabus_pids:
        print(f"\nPID {pid} Windows:")
        try:
            app = pywinauto.Application(backend="uia").connect(process=pid)
            windows = app.windows()
            for i, w in enumerate(windows):
                print(f"[Window {i}] Title: '{w.window_text()}' | Class: '{w.element_info.class_name}'")
                if "ログイン" in w.window_text() or w.window_text() == "":
                    print("Dumping all descendants:")
                    try:
                        # 全ての子孫を取得して主要なプロパティを出す
                        descendants = w.descendants()
                        for d in descendants:
                            print(f"  - Title: '{d.window_text()}' | ID: '{d.element_info.automation_id}' | Type: {d.element_info.control_type}")
                    except Exception as e:
                        print(f"  Error dumping descendants: {e}")
        except Exception as e:
            print(f"Error connecting to PID {pid}: {e}")

if __name__ == "__main__":
    dump_ui_tree()
