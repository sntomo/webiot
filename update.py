import sqlite3

# データベースに接続
conn = sqlite3.connect('tasks.db')
c = conn.cursor()

# 'characters' テーブルを作成
c.execute("""
    CREATE TABLE IF NOT EXISTS characters (
        points INTEGER DEFAULT 0,
        type TEXT
    )
""")

# 変更を保存して接続を閉じる
conn.commit()
conn.close()
