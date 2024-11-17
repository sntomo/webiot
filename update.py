import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()
# テーブルに 'actual_start_time' カラムを追加
c.execute("ALTER TABLE tasks ADD COLUMN actual_start_time TEXT")
conn.commit()
conn.close()
