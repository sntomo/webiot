from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import requests
import schedule
import time
import threading
import random
from datetime import datetime, date
from database import init_db
from collections import defaultdict

app = Flask(__name__)
init_db()


# 実際の開始日時をタスクに登録
def update_task_start_time(task_id, actual_start_time):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('UPDATE tasks SET actual_start_time = ? WHERE id = ?', (actual_start_time, task_id))
    conn.commit()
    conn.close()


def insert_task(title, scheduled_time, end_time, comments):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (title, scheduled_time, end_time, comments) VALUES (?, ?, ?, ?)', 
            (title, scheduled_time, end_time, comments))
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


# 岩部追記 一日のタスクをDBから取り出してデータを成形
def get_todays_task():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    d = date.today()
    todays_task = []
    d_str = d.strftime("%Y-%m-%d")
    c.execute('SELECT scheduled_time, title, id, is_completed FROM tasks WHERE scheduled_time LIKE ? ORDER BY scheduled_time ASC ', (d_str+'%',))
    todays_task_data = [{"time": row[0], "task": row[1], "task_id": row[2], "is_completed": row[3]} for row in c.fetchall()]
    conn.close()
    # 時間ごとにタスクをまとめる辞書
    grouped_tasks = defaultdict(list)
    for record in todays_task_data:
        time_obj = datetime.fromisoformat(record["time"])  # ISOフォーマットをdatetimeオブジェクトに変換
        hour_minute = time_obj.strftime("%H:00")  # "HH:MM"形式の文字列に変換
        grouped_tasks[hour_minute].append({"task": record["task"], "task_id": record["task_id"], "is_completed": record["is_completed"]})
    # `task_id` を含めてリストを作成
    todays_task = [{"time": time, "task": [task["task"] for task in tasks], "task_id": [task["task_id"] for task in tasks], "is_completed": [task["is_completed"] for task in tasks]} for time, tasks in grouped_tasks.items()]
    return todays_task


# タスクを終了済みとしてマークする関数
def mark_task_as_completed(task_id):
    # データベース接続を開く
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()

    try:
        # タスクを完了済みに設定
        c.execute('UPDATE tasks SET is_completed = 1 WHERE id = ?', (task_id,))
        conn.commit()

        # タスクの開始時間と終了時間を取得
        c.execute('SELECT title, scheduled_time, end_time FROM tasks WHERE id = ?', (task_id,))
        result = c.fetchone()
        if result:
            title, start_time, end_time = result
        else:
            raise ValueError(f"Task ID {task_id} not found in the database.")

        # 計測率を計算
        sensor_rate = calculate_sensor_rate(start_time, end_time)
        threshold = 0.1  # 計測率の閾値（例: 10%）

        # LINE通知
        url = "https://notify-api.line.me/api/notify"
        token = 'aFfnFfIIQXtpwgez3ahZLN1lxkXxADdMwJQvecjc7QV'
        headers = {'Authorization': 'Bearer ' + token}

        if sensor_rate >= threshold:
            message = f"{title} は予定通りに実行されました！"
            # 正常実行された場合、キャラクターテーブルのポイントを追加
            update_character()
        else:
            message = f"{title} は予定通り実行されませんでした"

        payload = {'message': message}
        r = requests.post(url, headers=headers, params=payload)
        if r.status_code != 200:
            print("LINE通知のエラー:", r.status_code)

    except Exception as e:
        print(f"Error marking task as completed: {e}")

    finally:
        # データベース接続を閉じる
        conn.close()

# 人感センサーでの計測率を取得する
def calculate_sensor_rate(start_time, end_time):
    conn = sqlite3.connect('motion_data.db')
    cursor = conn.cursor()
    
    # センサーデータを開始・終了時間の間で取得
    cursor.execute("""
        SELECT COUNT(*) FROM motion_log
        WHERE strftime('%Y-%m-%dT%H:%M', timestamp) BETWEEN ? AND ? AND motion_detected = 1
    """, (start_time, end_time))
    motion_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM motion_log
        WHERE strftime('%Y-%m-%dT%H:%M', timestamp) BETWEEN ? AND ?
    """, (start_time, end_time))
    total_count = cursor.fetchone()[0]
    
    conn.close()
    
    # 計測率を計算
    if total_count == 0:
        return 0  # データがない場合
    return motion_count / total_count

# キャラクターのデータを更新する
def update_character():
    conn = sqlite3.connect('tasks.db')  # データベース名を確認
    c = conn.cursor()
    
    try:
        # 現在のポイントを取得
        c.execute('SELECT points FROM characters')
        result = c.fetchone()
        if not result:
            print(f"Record not found.")
            return
        
        current_points = result[0]
        
        # ポイントを1増加
        new_points = current_points + 1
        c.execute('UPDATE characters SET points = ?', (new_points,))
        
        # ポイントが10になった場合
        if new_points == 10:
            new_type = random.randint(1, 3)  # 1～3のランダム値
            c.execute('UPDATE characters SET type = ?, lv = 1', (new_type,))
            print(f"Type set to {new_type}, LV set to 1.")
        
        # ポイントが20になった場合
        if new_points == 20:
            new_subject = random.randint(1, 5)  # 1～5のランダム値
            c.execute('UPDATE characters SET subject = ?,lv = 2', (new_subject,))
            print(f"Subject set to {new_subject}.")
        
        conn.commit()
        print(f"Points updated to {new_points}.")
    
    except Exception as e:
        print(f"Error updating character: {e}")
    
    finally:
        conn.close()

# キャラ画像を取得する
def get_character_image():
    # データベースからキャラクター情報を取得
    conn = sqlite3.connect('tasks.db')  # データベースファイル名を指定
    c = conn.cursor()
    
    try:
        # キャラクター情報を取得
        c.execute('SELECT lv, type, subject FROM characters')
        result = c.fetchone()
        
        if not result:
            print("No character data found.")
            return "default.png"
        
        lv, char_type, subject = result
        
        # 現在時刻を取得
        current_hour = datetime.now().hour
        is_night = current_hour >= 22 or current_hour < 6  # 深夜10時～朝6時
        
        # 画像パスを決定
        if lv == 1:
            image = "1-s.png" if is_night else "1.png"
        elif lv == 2:
            image = f"2-{char_type}-s.png" if is_night else f"2-{char_type}.png"
        elif lv == 3:
            random_value = random.randint(1, 3)  # ランダム値
            image = f"3-{char_type}-{subject}-s.png" if is_night else f"3-{char_type}-{subject}-{random_value}.png"
        else:
            image = "default.png"  # デフォルト画像
        
        return image

    except Exception as e:
        print(f"Error fetching character image: {e}")
        return "default.png"

    finally:
        conn.close()

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


# 岩部追記 fetch用エンドポイント
@app.route('/todays_task', methods=['POST'])
def todays_task():
    todays_task = get_todays_task()
    if todays_task:
        return jsonify(todays_task)
    else:
        return jsonify({'time':None, 'task':None, 'task_id':None})  # タスクがない場合


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.route('/')
def index():
    next_task = get_next_task()
    current_time = get_current_time()
    character_image = get_character_image()
    return render_template('index.html',
        next_task=next_task,
        current_time=current_time,
        character_image=character_image
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        title = request.form['title']
        scheduled_time = request.form['scheduled_time']
        end_time = request.form['end_time']
        comments = request.form['comments']
        
        # Ensure start time is before end time
        if scheduled_time >= end_time:
            return render_template('register.html', error="終了時間は開始時刻より後である必要があります。")
        
        insert_task(title, scheduled_time, end_time, comments)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/points', methods=['GET'])
def points():
    next_task = get_next_task()
    if next_task:
        next_task_time = datetime.strptime(next_task[1], "%Y-%m-%dT%H:%M")
        next_task_time = next_task_time.strftime("%H:%M")
        next_task_title = next_task[0]
    else:
        next_task_time = ""
        next_task_title = ""

    # キャラクター情報を取得
    # データベースからキャラクター情報を取得
    conn = sqlite3.connect('tasks.db')  # データベースファイル名を指定
    c = conn.cursor()
    
    try:

        c.execute('SELECT lv, type, subject FROM characters')
        result = c.fetchone()
        
        if not result:
            print("No character data found.")
        
        lv, char_type, subject = result
    
    except Exception as e:
        print(f"Error fetching character image: {e}")
        return "default.png"

    finally:
        conn.close()

    # サンプルデータ
    user_data = {
        "username": "サンプルユーザー",
        "level": lv,
        "points_to_next_level": 50,
        "status": "疲れ気味",
        "consecutive_days": 20,
        "next_task_time": next_task_time,
        "next_task_title": next_task_title
    }
    
    character_image = get_character_image()
    return render_template('points.html',
        user=user_data,
        character_image=character_image,
    )

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

