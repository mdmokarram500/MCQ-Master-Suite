"""
Single-file Flask app for MCQ Practice with Timers.
Features:
1. Question Timer (Countdown per question).
2. Auto-submit when time expires.
3. Total Session Time tracking.
4. CSV Upload & Management.
5. Tailwind CSS UI.

Setup:
1. pip install flask
2. python app.py
"""
from flask import Flask, request, redirect, url_for, render_template_string, flash, session
import csv
import json
import os
import random
import time
from datetime import timedelta

# --- Configuration ---
ACCESS_PIN = '1234'          # Login PIN
QUESTION_TIMER_SECONDS = 30  # Time per question (in seconds)
SECRET_KEY = 'change-this-to-random-secret-key'

# --- File Paths ---
DATA_FILE = 'questions.json'
SESSION_FILE = 'session.json'

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = SECRET_KEY

# --- Helper Functions (Data Management) ---

def load_questions():
    """Load questions from JSON file"""
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

def save_questions(qs):
    """Save questions to JSON file"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)

def get_session_data():
    """Read session data"""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def save_session_data(data):
    """Save session data"""
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def reset_session_file():
    """Delete/Reset session file"""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# --- HTML Templates (Tailwind CSS Integrated) ---

BASE_LAYOUT = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MCQ Pro Trainer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col">
    <nav class="bg-indigo-600 text-white p-4 shadow-md">
        <div class="container mx-auto flex justify-between items-center">
            <a href="/" class="text-xl font-bold flex items-center gap-2">
                <span>⏱️</span> MCQ Timer App
            </a>
            {% if session.get('authenticated') %}
            <a href="/end" class="text-sm bg-indigo-500 hover:bg-indigo-700 px-3 py-1 rounded transition">End Session</a>
            {% endif %}
        </div>
    </nav>

    <div class="container mx-auto p-4 md:p-8 max-w-4xl flex-grow">
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="mb-6 space-y-2">
            {% for category, message in messages %}
              <div class="p-4 rounded-lg shadow-sm border-l-4 flex items-center justify-between
                {% if 'success' in category %}bg-green-50 border-green-500 text-green-700
                {% elif 'warning' in category %}bg-yellow-50 border-yellow-500 text-yellow-700
                {% else %}bg-red-50 border-red-500 text-red-700{% endif %}">
                <span>{{ message }}</span>
              </div>
            {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        {{ content | safe }}
    </div>

    <footer class="text-center p-4 text-gray-400 text-sm">
        MCQ Trainer &copy; 2024
    </footer>
</body>
</html>
'''

INDEX_CONTENT = '''
<div class="grid md:grid-cols-2 gap-8 fade-in">
    <!-- Left Column: Upload -->
    <div class="space-y-6">
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h2 class="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                📂 1. Upload Questions (CSV)
            </h2>
            <form action="/upload" method="post" enctype="multipart/form-data" class="space-y-3">
                <input type="file" name="file" accept=".csv" required 
                    class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 transition"/>
                <button type="submit" class="w-full bg-gray-800 text-white py-2.5 rounded-lg hover:bg-gray-900 transition shadow-lg">
                    Upload CSV
                </button>
            </form>
            <p class="text-xs text-gray-400 mt-2">
                Format: <code>question,opt1,opt2,opt3,opt4,ans_index(1-4)</code>
            </p>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h2 class="text-lg font-bold text-red-600 mb-4">⚠️ Data Management</h2>
            <div class="flex justify-between items-center mb-4">
                <span class="text-gray-600">Total Questions:</span>
                <span class="font-mono font-bold text-xl">{{ total }}</span>
            </div>
            {% if total > 0 %}
            <form action="/clear_all" method="post" onsubmit="return confirm('Are you sure you want to delete all questions?');">
                <button class="w-full text-red-500 bg-red-50 py-2 rounded-lg hover:bg-red-100 transition border border-red-100">
                    Clear All Data
                </button>
            </form>
            {% endif %}
        </div>
    </div>

    <!-- Right Column: Start -->
    <div class="bg-white p-8 rounded-xl shadow-lg border-t-4 border-indigo-500 h-fit">
        <h2 class="text-2xl font-bold text-indigo-700 mb-2">2. Start Practice</h2>
        <p class="text-gray-500 mb-6">Enter your details to begin the timed test.</p>

        {% if total > 0 %}
        <form action="/start_session" method="post" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input type="text" name="user_name" placeholder="Enter your name" required
                    class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition outline-none">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Access PIN</label>
                <input type="password" name="access_pin" placeholder="••••" required
                    class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition outline-none">
            </div>
            
            <div class="bg-indigo-50 p-4 rounded-lg text-sm text-indigo-800 flex items-start gap-2">
                <span class="text-lg">⏳</span>
                <div>
                    <strong>Timer Rules:</strong><br>
                    You have <b>{{ timer_limit }} seconds</b> per question.<br>
                    It will auto-skip if time runs out.
                </div>
            </div>

            <button type="submit" class="w-full bg-indigo-600 text-white font-bold py-3.5 rounded-lg hover:bg-indigo-700 transition shadow-xl transform hover:-translate-y-0.5">
                Start Test 🚀
            </button>
        </form>
        {% else %}
        <div class="text-center py-10 text-gray-400 bg-gray-50 rounded-lg border-dashed border-2 border-gray-200">
            Upload questions to enable the test.
        </div>
        {% endif %}
    </div>
</div>
'''

PRACTICE_CONTENT = '''
<div class="max-w-3xl mx-auto">
    <!-- Info Bar -->
    <div class="flex justify-between items-end mb-4 px-1">
        <div>
            <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Candidate</p>
            <p class="font-bold text-gray-800">{{ user_name }}</p>
        </div>
        <div class="text-right">
            <span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-sm font-bold">
                Q {{ qnum }} / {{ total }}
            </span>
        </div>
    </div>

    <!-- Timer Card -->
    <div class="bg-white rounded-2xl shadow-xl overflow-hidden mb-6 relative">
        <!-- Timer Progress Bar (Absolute top) -->
        <div class="h-2 w-full bg-gray-100">
            <div id="timer-bar" class="h-full bg-indigo-500 transition-all duration-1000 ease-linear" style="width: 100%;"></div>
        </div>
        
        <div class="p-6 md:p-8">
            <!-- Timer Display -->
            <div class="absolute top-4 right-4 flex items-center gap-1 font-mono font-bold text-xl" id="timer-display-container">
                <span id="timer-icon" class="text-indigo-500">⏱️</span>
                <span id="timer-text" class="text-gray-700">{{ timer_limit }}</span>
            </div>

            <!-- Question -->
            <h3 class="text-xl md:text-2xl font-medium text-gray-800 mt-4 mb-8 leading-relaxed pr-12">
                {{ question['question'] }}
            </h3>

            <!-- Options Form -->
            <form method="post" action="/answer" id="quiz-form">
                <input type="hidden" name="qindex" value="{{ qindex }}">
                <input type="hidden" name="is_timeout" id="is_timeout" value="0">
                
                <div class="space-y-3">
                {% for idx, opt in enumerate(question['options'], start=1) %}
                    <label class="group relative flex items-center p-4 border-2 border-gray-100 rounded-xl cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition-all duration-200">
                        <input type="radio" name="choice" value="{{idx}}" class="w-5 h-5 text-indigo-600 border-gray-300 focus:ring-indigo-500">
                        <span class="ml-4 text-gray-700 font-medium group-hover:text-indigo-800">{{ opt }}</span>
                    </label>
                {% endfor %}
                </div>

                <button type="submit" class="mt-8 w-full bg-indigo-600 text-white font-bold py-4 rounded-xl hover:bg-indigo-700 transition shadow-lg">
                    Submit Answer
                </button>
            </form>
        </div>
    </div>
</div>

<script>
    // --- Timer Logic ---
    let timeLeft = {{ timer_limit }};
    const totalTime = {{ timer_limit }};
    const timerBar = document.getElementById('timer-bar');
    const timerText = document.getElementById('timer-text');
    const timerDisplay = document.getElementById('timer-display-container');
    const form = document.getElementById('quiz-form');
    const timeoutInput = document.getElementById('is_timeout');

    // Prevent double submission
    let submitted = false;
    form.addEventListener('submit', () => { submitted = true; });

    const countdown = setInterval(() => {
        if(submitted) { clearInterval(countdown); return; }
        
        timeLeft--;
        timerText.innerText = timeLeft;

        // Update bar width
        const percentage = (timeLeft / totalTime) * 100;
        timerBar.style.width = percentage + "%";

        // Change visual urgency
        if (timeLeft <= 10) {
            timerBar.classList.remove('bg-indigo-500');
            timerBar.classList.add('bg-red-500');
            timerDisplay.classList.add('text-red-600', 'animate-pulse');
        }

        // Timeout
        if (timeLeft <= 0) {
            clearInterval(countdown);
            timeoutInput.value = "1"; // Mark as timeout
            form.submit();
        }
    }, 1000);
</script>
'''

RESULT_CONTENT = '''
<div class="max-w-lg mx-auto bg-white rounded-2xl shadow-2xl overflow-hidden fade-in">
    <div class="bg-indigo-600 p-8 text-center">
        <div class="inline-block p-4 bg-white bg-opacity-20 rounded-full mb-4">
            <span class="text-4xl">🏆</span>
        </div>
        <h2 class="text-3xl font-bold text-white mb-1">Session Complete</h2>
        <p class="text-indigo-200">{{ user_name }}</p>
    </div>

    <div class="p-8">
        <div class="grid grid-cols-2 gap-6 mb-8">
            <div class="text-center p-4 bg-green-50 rounded-xl border border-green-100">
                <p class="text-sm text-green-600 font-bold uppercase tracking-wide">Score</p>
                <p class="text-3xl font-bold text-gray-800 mt-1">{{ correct }}<span class="text-gray-400 text-lg">/{{ attempted }}</span></p>
            </div>
            <div class="text-center p-4 bg-blue-50 rounded-xl border border-blue-100">
                <p class="text-sm text-blue-600 font-bold uppercase tracking-wide">Time Taken</p>
                <p class="text-2xl font-bold text-gray-800 mt-2">{{ time_taken }}</p>
            </div>
        </div>

        <div class="mb-8">
            <div class="flex justify-between text-sm mb-2">
                <span class="font-bold text-gray-600">Accuracy</span>
                <span class="font-bold text-indigo-600">{{ accuracy }}%</span>
            </div>
            <div class="w-full bg-gray-100 rounded-full h-3">
                <div class="bg-indigo-600 h-3 rounded-full" style="width: {{ accuracy }}%"></div>
            </div>
        </div>

        <div class="space-y-3">
            <a href="/practice?restart=1" class="block w-full text-center bg-indigo-600 text-white font-bold py-3 rounded-xl hover:bg-indigo-700 transition shadow">
                Restart Practice
            </a>
            <a href="/" class="block w-full text-center bg-white text-gray-600 font-bold py-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition">
                Back to Home
            </a>
        </div>
    </div>
</div>
'''

# --- Routes ---

@app.route('/')
def index():
    """Home Page"""
    qs = load_questions()
    # Clear auth on home load
    session.pop('user_name', None)
    session.pop('authenticated', None)
    
    return render_template_string(
        BASE_LAYOUT, 
        content=render_template_string(INDEX_CONTENT, total=len(qs), timer_limit=QUESTION_TIMER_SECONDS)
    )

@app.route('/start_session', methods=['POST'])
def start_session():
    """Auth & Setup Session"""
    user_name = request.form.get('user_name')
    access_pin = request.form.get('access_pin')
    
    if access_pin != ACCESS_PIN:
        flash('❌ Incorrect PIN. Please try again.', 'error')
        return redirect(url_for('index'))
        
    qs = load_questions()
    if not qs:
        flash('⚠️ No questions available to practice.', 'warning')
        return redirect(url_for('index'))

    # Init Secure Session
    session['user_name'] = user_name.strip()
    session['authenticated'] = True

    # Init File Session (Data Persistence)
    reset_session_file()
    order = list(range(len(qs)))
    random.shuffle(order)
    
    sess_data = {
        'order': order,
        'pos': 0,
        'score': 0,
        'correct': 0,
        'attempted': 0,
        'start_time': time.time()
    }
    save_session_data(sess_data)
    
    return redirect(url_for('practice'))

@app.route('/practice')
def practice():
    """Question Page"""
    if not session.get('authenticated'):
        return redirect(url_for('index'))
    
    qs = load_questions()
    sess_data = get_session_data()
    
    # If file session is missing/corrupt, go home
    if not sess_data:
        return redirect(url_for('index'))
        
    # Check restart flag
    if request.args.get('restart'):
        reset_session_file()
        # Recursive redirect to restart logic handled in start_session, 
        # but here we just want to reset stats for current user? 
        # Simpler: Redirect to home to re-login or implement restart logic here.
        # Let's keep it simple: restart means re-shuffle.
        order = list(range(len(qs)))
        random.shuffle(order)
        sess_data = {
            'order': order, 'pos': 0, 'score': 0, 'correct': 0, 'attempted': 0,
            'start_time': time.time()
        }
        save_session_data(sess_data)

    # Check End
    if sess_data['pos'] >= len(sess_data['order']):
        return redirect(url_for('end'))

    qindex = sess_data['order'][sess_data['pos']]
    question = qs[qindex]

    return render_template_string(
        BASE_LAYOUT,
        content=render_template_string(
            PRACTICE_CONTENT,
            user_name=session['user_name'],
            question=question,
            qindex=qindex,
            qnum=sess_data['pos'] + 1,
            total=len(sess_data['order']),
            timer_limit=QUESTION_TIMER_SECONDS,
            enumerate=enumerate
        )
    )

@app.route('/answer', methods=['POST'])
def answer():
    """Handle Answer & Timeout"""
    if not session.get('authenticated'):
        return redirect(url_for('index'))
        
    sess_data = get_session_data()
    qs = load_questions()
    
    if not sess_data: return redirect(url_for('index'))
    
    choice_str = request.form.get('choice')
    is_timeout = request.form.get('is_timeout') == '1'
    qindex = int(request.form.get('qindex', -1))
    
    # Validation: If not timeout and no choice made
    if not choice_str and not is_timeout:
        flash('⚠️ Please select an option.', 'warning')
        return redirect(url_for('practice'))
        
    correct_ans = qs[qindex]['answer']
    sess_data['attempted'] += 1
    
    if is_timeout:
        flash('⏰ Time Up! Question skipped.', 'error')
        # No score increase
    else:
        choice = int(choice_str)
        if choice == correct_ans:
            sess_data['score'] += 1
            sess_data['correct'] += 1
            flash('✅ Correct Answer!', 'success')
        else:
            correct_text = qs[qindex]['options'][correct_ans - 1]
            flash(f'❌ Wrong! Correct: {correct_text}', 'error')

    sess_data['pos'] += 1
    save_session_data(sess_data)
    
    return redirect(url_for('practice'))

@app.route('/end')
def end():
    """Result Page"""
    if not session.get('authenticated'):
        return redirect(url_for('index'))
        
    sess_data = get_session_data()
    if not sess_data: return redirect(url_for('index'))
    
    # Calc Time
    start = sess_data.get('start_time', time.time())
    end_t = time.time()
    delta = int(end_t - start)
    
    # Format nicely
    if delta < 60:
        time_str = f"{delta} sec"
    else:
        mins, secs = divmod(delta, 60)
        time_str = f"{mins} min {secs} sec"

    attempted = sess_data.get('attempted', 1) # avoid div by zero if 0
    correct = sess_data.get('correct', 0)
    
    # Calculate accuracy based on attempted (or total seen)
    # Here we use 'pos' as total seen
    total_seen = sess_data.get('pos', 1)
    if total_seen == 0: total_seen = 1
    
    accuracy = int((correct / total_seen) * 100)
    
    return render_template_string(
        BASE_LAYOUT,
        content=render_template_string(
            RESULT_CONTENT,
            user_name=session['user_name'],
            correct=correct,
            attempted=total_seen,
            time_taken=time_str,
            accuracy=accuracy
        )
    )

@app.route('/upload', methods=['POST'])
def upload():
    """Handle CSV Upload"""
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('⚠️ No file selected', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Read CSV
        lines = file.read().decode('utf-8').splitlines()
        reader = csv.reader(lines)
        
        new_questions = []
        for row in reader:
            # Expecting at least 6 columns: Q, O1, O2, O3, O4, AnsIndex
            if len(row) >= 6 and row[0].strip():
                try:
                    ans_idx = int(row[5].strip())
                    # Basic Validation
                    if 1 <= ans_idx <= 4:
                        new_questions.append({
                            'question': row[0].strip(),
                            'options': [col.strip() for col in row[1:5]],
                            'answer': ans_idx
                        })
                except ValueError:
                    continue # Skip headers or bad data

        if new_questions:
            current_qs = load_questions()
            current_qs.extend(new_questions)
            save_questions(current_qs)
            flash(f'✅ Successfully added {len(new_questions)} questions!', 'success')
        else:
            flash('⚠️ No valid questions found in CSV. Check format.', 'warning')

    except Exception as e:
        flash(f'❌ Error reading file: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    """Reset Data"""
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
        save_questions([])
    reset_session_file()
    flash('🗑️ All data cleared successfully.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Ensure data file exists
    if not os.path.exists(DATA_FILE):
        save_questions([])
    
    print(f"App running! Login PIN is: {ACCESS_PIN}")
    app.run(debug=True)