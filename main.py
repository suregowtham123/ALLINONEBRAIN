from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from dotenv import load_dotenv
import cohere
import google.generativeai as genai
from groq import Groq
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'super-secret-key'
# API keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize clients
co = cohere.Client(COHERE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# Dummy user store
users = {}

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname in users and users[uname] == pwd:
            session['username'] = uname
            return redirect(url_for('home'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname in users:
            return "Username already exists"
        users[uname] = pwd
        return redirect(url_for('login'))
    return render_template('signup.html')

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

if __name__ == '__main__':
    app.run(debug=True)      