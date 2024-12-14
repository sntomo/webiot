import sqlite3

def add_subject_column():
    conn = sqlite3.connect('tasks.db')  # データベース名を確認
    c = conn.cursor()
    try:
        c.execute("update characters set lv = 3, type = 2, points = 5, subject =2")
        #print("Column 'lv' added successfully.")
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")  # カラムが既に存在する場合など
    finally:
        conn.commit()
        conn.close()

add_subject_column()
