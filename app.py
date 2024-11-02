from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import schedule
import time
import threading
from datetime import datetime
from database import init_db

app = Flask(__name__)
init_db()

def insert_task(title, scheduled_time):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (title, scheduled_time) VALUES (?, ?)', (title, scheduled_time))
    conn.commit()
    conn.close()

def get_next_task():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    current_time = datetime.now()
    c.execute('SELECT title, scheduled_time FROM tasks ORDER BY scheduled_time ASC')
    tasks = c.fetchall()
    conn.close()
    
    for task in tasks:
        # "2024-11-02T15:07" の形式に合わせたフォーマット指定
        task_time = datetime.strptime(task[1], "%Y-%m-%dT%H:%M")
        if task_time > current_time:
            return task  # 未来のタスクが見つかった場合、それを返す
    
    return None  # 未来のタスクがない場合

@app.route('/next_task')
def next_task():
    task = get_next_task()
    if task:
        return jsonify(title=task[0], scheduled_time=task[1])
    else:
        return jsonify(title=None, scheduled_time=None)  # タスクがない場合

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route('/')
def index():
    next_task = get_next_task()
    current_time = get_current_time()
    return render_template('index.html', next_task=next_task, current_time=current_time)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        title = request.form['title']
        scheduled_time = request.form['scheduled_time']
        insert_task(title, scheduled_time)
        return redirect(url_for('index'))
    return render_template('register.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

