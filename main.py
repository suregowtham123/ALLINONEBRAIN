from flask import Flask, render_template, request, redirect, session, url_for, jsonify,flash
from kaggle.api.kaggle_api_extended import KaggleApi
from dotenv import load_dotenv
import kaggle
import cohere
import time
from datetime import datetime
import requests
import random
import sqlite3
import smtplib
import google.generativeai as genai
from email.mime.text import MIMEText
from groq import Groq
import sqlite3
import os

load_dotenv()

app = Flask(__name__)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
app.secret_key = 'super-secret-key'

# API keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
os.environ['KAGGLE_USERNAME'] = 'crazyboy11111'
os.environ['KAGGLE_KEY'] = 'feed5e8d0417ad1e0b13fe42148900e6'


# Initialize AI clients
co = cohere.Client(COHERE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)


def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/start_section/<section_name>')
def start_section(section_name):
    if 'user_email' in session:
        session['start_time'] = datetime.now()
        session['current_section'] = section_name
    return '', 204  # no response needed

# End time and log
@app.route('/end_section')
def end_section():
    if 'user_email' in session and 'start_time' in session:
        end_time = datetime.now()
        duration = (end_time - session['start_time']).total_seconds()
        email = session['user_email']
        section = session['current_section']

        with open('user_activity_log.txt', 'a') as f:
            f.write(f"{email},{section},{duration}\n")

        session.pop('start_time', None)
        session.pop('current_section', None)
    return '', 204


@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    current_user = session['user_email']
    is_admin = current_user == ADMIN_EMAIL

    users_list = []
    if is_admin:
        with open('users.txt', 'r') as f:
            users_list = [line.strip() for line in f.readlines()]

    return render_template('dashboard.html', users_list=users_list if is_admin else None)





@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (uname, pwd)).fetchone()
        conn.close()
        if user:
            session['user_email'] = uname
            session['username'] = uname.split('@')[0]

            # Redirect to admin if logged-in email is admin
            if uname == os.getenv('EMAIL_USER'):
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))

        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')



def send_otp(email, otp):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    msg = MIMEText(f"Your OTP for registration is: {otp}")
    msg['Subject'] = 'Your OTP Code'
    msg['From'] = sender
    msg['To'] = email

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)


def create_search_log_table():
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            query TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

create_search_log_table()  # call this once on app start



@app.route('/delete_user', methods=['POST'])
def delete_user():
    if session.get('user_email') != os.getenv("EMAIL_USER"):
        return redirect(url_for('dashboard'))

    email_to_delete = request.form['email']
    updated_users = []

    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as f:
            updated_users = [line for line in f if line.strip() != email_to_delete]

        with open('users.txt', 'w') as f:
            f.writelines(updated_users)

    return redirect(url_for('admin_page'))

@app.route('/get_pie_data/<email>')
def get_pie_data(email):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT page, SUM(time_spent) 
        FROM user_activity_log 
        WHERE email = ? 
        GROUP BY page
    ''', (email,))
    data = cur.fetchall()
    conn.close()

    labels = [row[0] for row in data]
    values = [row[1] for row in data]

    return jsonify({'labels': labels, 'values': values})






@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']

        # Validate email format (e.g., must end with @gmail.com)
        if not uname.endswith('@gmail.com'):
            return render_template('signup.html', error="Only @gmail.com addresses are allowed.")

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store temporarily in session
        session['temp_user'] = {'username': uname, 'password': pwd, 'otp': otp}

        # Send OTP to email
        send_otp(uname, otp)

        return render_template('verify_otp.html', email=uname)
    
    return render_template('signup.html')


@app.route('/admin')
def admin_dashboard():
    if session.get('user_email') != os.getenv("EMAIL_USER"):
        return redirect(url_for('login'))  # Fix redirect loop

    users = []
    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as f:
            users = [line.strip() for line in f if line.strip()]

    # ✅ Read user activity from SQLite
    log_entries = []
    emails = set()

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, page, time_spent FROM user_activity_log")
    rows = cursor.fetchall()
    conn.close()

    for email, page, time_spent in rows:
        emails.add(email)
        log_entries.append({
            "email": email,
            "page": page,
            "time": time_spent
        })

    user_emails = sorted(emails)

    return render_template(
        'admin.html',
        users=users,
        log_entries=log_entries,
        user_emails=user_emails
    )


def log_user_activity(email, page):
    start_time = session.get('start_time', time.time())
    end_time = time.time()
    time_spent = int(end_time - start_time)
    session['start_time'] = end_time

    # ✅ Save to SQLite instead of file
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            page TEXT,
            time_spent INTEGER
        )
    ''')
    cursor.execute("INSERT INTO user_activity_log (email, page, time_spent) VALUES (?, ?, ?)", 
                   (email, page, time_spent))
    conn.commit()
    conn.close()

@app.route('/get_user_activity')
def get_user_activity():
    email = request.args.get('email')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT page, SUM(time_spent) FROM user_activity_log WHERE email=? GROUP BY page", (email,))
    data = cursor.fetchall()
    conn.close()

    labels = [row[0] for row in data]
    values = [row[1] for row in data]
    return jsonify({'labels': labels, 'values': values})






@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form['otp']
    temp_user = session.get('temp_user')

    if temp_user and entered_otp == temp_user['otp']:
        uname = temp_user['username']
        pwd = temp_user['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (uname, pwd))
            conn.commit()
            flash('Signup successful! Please login.')
        except sqlite3.IntegrityError:
            flash('User already exists.')
        conn.close()

        # ✅ Save email to users.txt only if not already present
        if not os.path.exists('users.txt'):
            open('users.txt', 'w').close()

        with open('users.txt', 'r') as f:
            existing_users = f.read().splitlines()

        if uname not in existing_users:
            with open('users.txt', 'a') as f:
                f.write(uname + '\n')

        # ✅ Cleanup temp session
        session.pop('temp_user', None)
        return redirect('/login')

    else:
        flash('Invalid OTP. Please try again.')
        return render_template('verify_otp.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get("question", "")
    mode = data.get("mode", "answer")
    groq_text = gemini_text = cohere_text = final_answer = ""

    try:
        groq_response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": question}]
        )
        groq_text = groq_response.choices[0].message.content.strip()
    except Exception as e:
        groq_text = f"[Groq Error: {str(e)}]"

    try:
        gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        gemini_response = gemini_model.generate_content(question)
        gemini_text = gemini_response.text.strip()
    except Exception as e:
        gemini_text = f"[Gemini Error: {str(e)}]"

    try:
        cohere_response = co.chat(
            message=question,
            model='command-r-plus',
            temperature=0.3
        )
        cohere_text = cohere_response.text.strip()
    except Exception as e:
        cohere_text = f"[Cohere Error: {str(e)}]"

    if mode == "explanation":
        final_answer = f"Groq: {groq_text}\n\nGemini: {gemini_text}\n\nCohere: {cohere_text}"
    else:
        final_answer = groq_text or gemini_text or cohere_text or "No answer"

    return jsonify({
        "groq": groq_text,
        "gemini": gemini_text,
        "cohere": cohere_text,
        "final": final_answer
    })

@app.route('/bots')
def bot_analyzer():
    if 'user_email' in session:
        log_user_activity(session['user_email'], "AI Answer Analyzer")
        return render_template('bots.html')
    return redirect('/login')



@app.route('/courses', methods=['GET', 'POST'])
def learning_courses():
    if 'user_email' in session:
        log_user_activity(session['user_email'], "Learning Courses")

    videos = []
    if request.method == 'POST':
        query = request.form.get('search')
        if query:
            url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=10&type=video'
            response = requests.get(url)
            data = response.json()
            for item in data.get('items', []):
                videos.append({
                    'title': item['snippet']['title'],
                    'video_id': item['id']['videoId'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url']
                })

    return render_template('courses.html', videos=videos)


@app.route('/datasets', methods=['GET', 'POST'])
def datasets():
    from kaggle.api.kaggle_api_extended import KaggleApi

    if 'user_email' not in session:
        return redirect('/login')

    # ✅ Log user activity for page access
    log_user_activity(session['user_email'], "Dataset Finder")

    api = KaggleApi()
    api.authenticate()
    results = []
    error = None
    query = ''

    if request.method == 'POST':
        query = request.form.get('query')
        user_email = session.get('user_email')  # fixed key name

        if query:
            try:
                datasets = api.dataset_list(search=query, sort_by='hottest', max_size=None)
                for ds in datasets:
                    results.append({
                        'title': ds.title,
                        'ref': ds.ref,
                        'url': f"https://www.kaggle.com/datasets/{ds.ref}"
                    })

                # Optional: Save the search to a log or DB
                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS search_logs (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    user_email TEXT,
                                    query TEXT,
                                    timestamp TEXT
                                  )''')
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT INTO search_logs (user_email, query, timestamp) VALUES (?, ?, ?)",
                               (user_email, query, timestamp))
                conn.commit()
                conn.close()

            except Exception as e:
                error = str(e)

    return render_template('datasets.html', results=results, query=query, error=error)





if __name__ == '__main__':
    app.run(debug=True)
