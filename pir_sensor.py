import RPi.GPIO as GPIO
import time
import sqlite3
from datetime import datetime

# PIRセンサーのGPIOピン
PIR_PIN = 4
# SQLiteデータベースのファイル名
DB_FILE = "motion_data.db"

# GPIO設定
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

# SQLiteデータベース接続とテーブルの作成
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS motion_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        motion_detected INTEGER
    )
""")
conn.commit()

try:
    print("PIRモーションセンサーを起動しています...")
    time.sleep(5)  # センサーのウォームアップ時間
    print("準備完了。動きを検出しています。")

    previous_state = False
    while True:
        current_state = GPIO.input(PIR_PIN)
        if current_state != previous_state:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            motion_detected = 1 if current_state else 0

            # 動きの検知状態をデータベースに保存
            cursor.execute("INSERT INTO motion_log (timestamp, motion_detected) VALUES (?, ?)",
                           (timestamp, motion_detected))
            conn.commit()

            if current_state:
                print(f"{timestamp}: 動きを検出しました！")
            else:
                print(f"{timestamp}: 動きなし。")

            previous_state = current_state

        time.sleep(0.5)

except KeyboardInterrupt:
    print("プログラムを終了します。")

finally:
    GPIO.cleanup()
    conn.close()
