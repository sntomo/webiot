import sqlite3

def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
end_time TEXT NOT NULL,
actual_start_time TEXT,
is_completed BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()