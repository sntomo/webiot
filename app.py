from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import requests
import schedule
import time
import threading
from datetime import datetime
from database import init_db

app = Flask(__name__)
init_db()

# 実際の開始日時をタスクに登録
def update_task_start_time(task_id, actual_start_time):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('UPDATE tasks SET actual_start_time = ? WHERE id = ?', (actual_start_time, task_id))
    conn.commit()
    conn.close()

def insert_task(title, scheduled_time, end_time):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (title, scheduled_time, end_time) VALUES (?, ?, ?)', 
              (title, scheduled_time, end_time))
    conn.commit()
    conn.close()


def get_current_task():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    current_time = datetime.now()
    c.execute('SELECT id, title, scheduled_time, end_time, is_completed FROM tasks WHERE actual_start_time IS NULL ORDER BY scheduled_time ASC')
    task = c.fetchone()  # まだ開始されていないタスクを取得
    conn.close()

    if task:
        # 終了時間がある場合のみstrptimeを使用
        task_time = None
        if task[3]:  # task[3] (end_time) が存在する場合
            try:
                task_time = datetime.strptime(task[3], "%Y-%m-%dT%H:%M")  # 終了時間をDateTimeに変換
            except ValueError:
                print(f"Invalid end time format for task ID {task[0]}: {task[3]}")  # 不正なフォーマットがあった場合のログ
        if task_time and task_time < current_time:
            mark_task_as_completed(task[0])  # 終了時間が過ぎたら終了フラグを更新
        return {'id': task[0], 'title': task[1], 'scheduled_time': task[2], 'end_time': task[3], 'is_completed': task[4]}
    return None  # 現在進行中のタスクがない場合


def get_next_task():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    current_time = datetime.now()
    c.execute('SELECT title, scheduled_time, end_time, id FROM tasks ORDER BY scheduled_time ASC')
    tasks = c.fetchall()
    conn.close()
    
    for task in tasks:
        # "2024-11-02T15:07" の形式に合わせたフォーマット指定
        task_time = datetime.strptime(task[1], "%Y-%m-%dT%H:%M")
        if task_time > current_time:
            return task  # 未来のタスクが見つかった場合、それを返す
    
    return None  # 未来のタスクがない場合

# タスクを終了済みとしてマークする関数
def mark_task_as_completed(task_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('UPDATE tasks SET is_completed = 1 WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    url = "https://notify-api.line.me/api/notify"
    token = 'YB0NW8ggdR205dV2OskRGHRQBM36CoU8qqy7GPFFvPP'
    headers = {'Authorization': 'Bearer ' + token}
 
    message = 'タスクが完了しました'
    payload = {'message': message}
 
    r = requests.post(url, headers=headers, params=payload,)
    if r.status_code != 200:
        print("error : %d" % (r.status_code))


@app.route('/start_task', methods=['POST'])
def start_task():
    task_id = request.json.get('task_id')
    actual_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_task_start_time(task_id, actual_start_time)
    return jsonify({"status": "success", "actual_start_time": actual_start_time})


@app.route('/next_task')
def next_task():
    task = get_next_task()
    if task:
        return jsonify(id=task[3],title=task[0], scheduled_time=task[1], end_time=task[2])
    else:
        return jsonify(id=None, title=None, scheduled_time=None, endtime=None)  # タスクがない場合

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
        end_time = request.form['end_time']
        
        # Ensure start time is before end time
        if scheduled_time >= end_time:
            return render_template('register.html', error="終了時間は開始時刻より後である必要があります。")
        
        insert_task(title, scheduled_time, end_time)
        return redirect(url_for('index'))
    return render_template('register.html')

# 終了フラグを更新
@app.route('/mark_task_as_completed', methods=['POST'])
def mark_task_as_completed_endpoint():
    # リクエストから task_id を取得
    task_id = request.json.get('task_id')
    if not task_id:
        return jsonify({"status": "error", "message": "Task ID is required"}), 400
    
    try:
        # 修正した関数を呼び出し
        mark_task_as_completed(task_id)
        return jsonify({"status": "success", "message": "Task marked as completed"})
    except Exception as e:
        print(f"Error marking task as completed: {e}")
        return jsonify({"status": "error", "message": "Failed to mark task as completed"}), 500


# フロントエンドで更新された状態を確認
@app.route('/update_current_task')
def update_current_task():
    task = get_current_task()
    if task:
        return jsonify(task)
    else:
        return jsonify({'message': 'No active task'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

