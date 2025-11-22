"""
Single-file Flask app for MCQ Practice with:
- DESKTOP READY: Auto-open browser & Fixed Paths for .exe
- Fixed Practice Mode (Inputs re-enabled before submit)
- Timers & Auto-submit
- Subject/Category Selection
- Leaderboard (High Scores)
- PDF Print Feature

Setup:
1. pip install flask
2. python app.py
"""
from flask import Flask, request, redirect, url_for, render_template_string, flash, session
import csv
import json
import os
import sys
import random
import time
import webbrowser
from threading import Timer
from datetime import datetime

# --- Configuration ---
ACCESS_PIN = '1234'
SECRET_KEY = 'super-secret-key-change-me'

# --- File Paths (Desktop App Fix) ---
# This ensures data files are stored next to the .exe file, not in a temp folder
if getattr(sys, 'frozen', False):
    # If running as compiled .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If running as python script
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATA_FILE = os.path.join(BASE_DIR, 'questions.json')
SESSION_FILE = os.path.join(BASE_DIR, 'session.json')
SCORES_FILE = os.path.join(BASE_DIR, 'highscores.json')

app = Flask(__name__)
app.secret_key = SECRET_KEY

# --- Data Helpers ---

def load_questions():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_questions(qs):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)

def get_session_data():
    if not os.path.exists(SESSION_FILE): return None
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return None

def save_session_data(data):
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def load_scores():
    if not os.path.exists(SCORES_FILE): return []
    try:
        with open(SCORES_FILE, 'r', encoding='utf-8') as f:
            return sorted(json.load(f), key=lambda x: x['score'], reverse=True)[:10]
    except: return []

def save_score(record):
    scores = load_scores()
    scores.append(record)
    scores.sort(key=lambda x: (x['score'], x['accuracy']), reverse=True)
    with open(SCORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(scores[:20], f) 

def reset_session_file():
    if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)

# --- HTML Templates ---

BASE_LAYOUT = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MCQ Master Suite</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @media print {
            .no-print { display: none; }
            .print-only { display: block; }
            body { background: white; }
        }
    </style>
    <script>
        // Safe Audio Context Setup
        let audioCtx = null;
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch(e) {
            console.warn("Web Audio API not supported");
        }
        
        function unlockAudio() {
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume().then(() => console.log('Audio unlocked'));
            }
            document.removeEventListener('click', unlockAudio);
            document.removeEventListener('touchstart', unlockAudio);
        }
        document.addEventListener('click', unlockAudio);
        document.addEventListener('touchstart', unlockAudio);

        function playSound(type) {
            if (!audioCtx) return;
            try {
                if (audioCtx.state === 'suspended') audioCtx.resume();
                
                const osc = audioCtx.createOscillator();
                const gainNode = audioCtx.createGain();
                osc.connect(gainNode);
                gainNode.connect(audioCtx.destination);

                if (type === 'correct') {
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(500, audioCtx.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(1000, audioCtx.currentTime + 0.1);
                    gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
                    osc.start(); osc.stop(audioCtx.currentTime + 0.5);
                } else if (type === 'wrong') {
                    osc.type = 'sawtooth';
                    osc.frequency.setValueAtTime(150, audioCtx.currentTime);
                    osc.frequency.linearRampToValueAtTime(100, audioCtx.currentTime + 0.3);
                    gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
                    osc.start(); osc.stop(audioCtx.currentTime + 0.3);
                } else if (type === 'tick') {
                    osc.type = 'square';
                    osc.frequency.setValueAtTime(800, audioCtx.currentTime);
                    gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.05);
                    osc.start(); osc.stop(audioCtx.currentTime + 0.05);
                }
            } catch (err) {
                console.error("Audio playback failed:", err);
            }
        }
    </script>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col">
    <nav class="bg-indigo-600 text-white p-4 shadow-md no-print">
        <div class="container mx-auto flex justify-between items-center">
            <a href="/" class="text-xl font-bold flex items-center gap-2">
                <span>🎓</span> MCQ Master Suite
            </a>
            {% if session.get('authenticated') %}
            <a href="/end" class="text-sm bg-indigo-500 hover:bg-indigo-700 px-3 py-1 rounded transition">End Session</a>
            {% endif %}
        </div>
    </nav>

    <div class="container mx-auto p-4 md:p-8 max-w-6xl flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="mb-6 space-y-2 no-print">
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

    <footer class="text-center p-4 text-gray-400 text-sm no-print">
        MCQ Trainer v5.0 &copy; 2024
    </footer>
</body>
</html>
'''

INDEX_CONTENT = '''
<div class="grid lg:grid-cols-3 gap-8 fade-in">
    
    <!-- Column 1: Start Practice -->
    <div class="lg:col-span-2 space-y-6">
        <div class="bg-white p-8 rounded-xl shadow-lg border-t-4 border-indigo-500">
            <h2 class="text-2xl font-bold text-indigo-700 mb-2">🚀 Start New Session</h2>
            <p class="text-gray-500 mb-6">Customize your test parameters below.</p>

            {% if total > 0 %}
            <form action="/start_session" method="post" class="grid md:grid-cols-2 gap-6">
                <!-- User Info -->
                <div class="md:col-span-2 grid md:grid-cols-2 gap-4">
                    <input type="text" name="user_name" placeholder="Your Name" required
                        class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 outline-none">
                    <input type="password" name="access_pin" placeholder="PIN (1234)" required
                        class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 outline-none">
                </div>

                <!-- Subject & Mode -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Subject / Topic</label>
                    <select name="subject" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                        <option value="all">📚 All Subjects</option>
                        {% for sub in subjects %}
                        <option value="{{ sub }}">{{ sub }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Test Mode</label>
                    <select name="mode" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                        <option value="practice">🛡️ Practice Mode (Feedback & Sound)</option>
                        <option value="exam">⏱️ Exam Mode (Fast, Silent)</option>
                    </select>
                </div>

                <!-- Difficulty & Count -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Difficulty</label>
                    <select name="difficulty" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                        <option value="easy">🟢 Easy (60s)</option>
                        <option value="medium" selected>🟡 Medium (30s)</option>
                        <option value="hard">🔴 Hard (15s, Neg. Mark)</option>
                    </select>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Question Count</label>
                    <input type="number" name="num_questions" min="1" max="{{ total }}" value="{{ min(10, total) }}"
                        class="w-full p-3 rounded-lg border border-gray-300 outline-none">
                </div>

                <button type="submit" class="md:col-span-2 w-full bg-indigo-600 text-white font-bold py-4 rounded-lg hover:bg-indigo-700 transition shadow-xl text-lg">
                    Start Test
                </button>
            </form>
            {% else %}
            <div class="text-center py-10 text-gray-400 bg-gray-50 rounded-lg border-dashed border-2 border-gray-200">
                Database is empty. Upload CSV to begin.
            </div>
            {% endif %}
        </div>

        <!-- Upload Section -->
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-lg font-bold text-gray-800">📂 Upload Data</h2>
                <span class="bg-indigo-100 text-indigo-800 text-sm font-bold px-3 py-1 rounded-full">Total Questions: {{ total }}</span>
            </div>
            <form action="/upload" method="post" enctype="multipart/form-data" class="flex gap-4 items-center">
                <input type="file" name="file" accept=".csv" required 
                    class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 transition"/>
                <button type="submit" class="bg-gray-800 text-white py-2 px-6 rounded-lg hover:bg-gray-900 whitespace-nowrap">
                    Upload
                </button>
            </form>
            <p class="text-xs text-gray-400 mt-2">Format: <code>question,opt1,opt2,opt3,opt4,ans,subject(optional)</code></p>
        </div>
    </div>

    <!-- Column 2: Leaderboard -->
    <div class="space-y-6">
        <div class="bg-white p-6 rounded-xl shadow-lg">
            <div class="flex items-center justify-between mb-4 border-b pb-2">
                <h2 class="text-xl font-bold text-yellow-600">🏆 Leaderboard</h2>
                <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded">Top Rankers</span>
            </div>
            
            {% if scores %}
            <div class="space-y-3 max-h-[400px] overflow-y-auto">
                {% for s in scores %}
                <div class="flex justify-between items-center p-3 rounded-lg {{ 'bg-yellow-50 border border-yellow-100' if loop.index <= 3 else 'bg-gray-50' }}">
                    <div class="flex items-center gap-3">
                        <span class="font-bold text-gray-400 w-4 text-center">{{ loop.index }}</span>
                        <div>
                            <p class="font-bold text-gray-800 text-sm">{{ s.name }}</p>
                            <p class="text-xs text-gray-400">{{ s.date }}</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="font-bold text-indigo-600">{{ s.score }}</p>
                        <p class="text-xs text-gray-500">{{ s.accuracy }}%</p>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-center text-gray-400 py-4 text-sm">No records yet. Be the first!</p>
            {% endif %}
        </div>

        <div class="bg-white p-6 rounded-xl shadow-sm border border-red-100">
            <h2 class="text-sm font-bold text-red-600 mb-3">Danger Zone</h2>
             {% if total > 0 %}
            <form action="/clear_all" method="post" onsubmit="return confirm('Warning: This will delete ALL questions and scores. Continue?');">
                <button class="w-full text-red-500 bg-red-50 py-2 rounded-lg hover:bg-red-100 transition text-sm">
                    Reset System Data
                </button>
            </form>
            {% else %}
             <p class="text-xs text-gray-400">System empty.</p>
            {% endif %}
        </div>
    </div>
</div>
'''

PRACTICE_CONTENT = '''
<div class="max-w-3xl mx-auto" id="practice-container">
    <!-- Info Header -->
    <div class="flex justify-between items-end mb-4 px-1">
        <div>
            <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Candidate</p>
            <p class="font-bold text-gray-800">{{ user_name }} 
                <span class="text-xs font-normal text-gray-500 ml-1">
                    ({{ difficulty|title }} / {{ mode|title }})
                </span>
            </p>
        </div>
        <div class="text-right">
            <span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-sm font-bold">
                Q {{ qnum }} / {{ total }}
            </span>
            {% if subject != 'all' %}
            <span class="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm font-bold ml-2">
                {{ subject }}
            </span>
            {% endif %}
        </div>
    </div>

    <!-- Card -->
    <div class="bg-white rounded-2xl shadow-xl overflow-hidden mb-6 relative">
        
        <!-- Timer Bar -->
        <div class="h-2 w-full bg-gray-100">
            <div id="timer-bar" class="h-full bg-indigo-500 transition-all duration-1000 ease-linear" style="width: 100%;"></div>
        </div>
        
        <div class="p-6 md:p-8 relative">
            <!-- Timer Text -->
            <div class="absolute top-4 right-4 flex items-center gap-1 font-mono font-bold text-xl" id="timer-display-container">
                <span id="timer-icon" class="text-indigo-500">⏱️</span>
                <span id="timer-text" class="text-gray-700">{{ timer_limit }}</span>
            </div>

            <!-- Question -->
            <h3 class="text-xl md:text-2xl font-medium text-gray-800 mt-8 mb-8 leading-relaxed pr-12">
                {{ question['question'] }}
            </h3>

            <!-- Client Side Feedback Box (Hidden Initially) -->
            <div id="client-feedback" class="hidden mb-6 p-4 rounded-lg border animate-pulse">
                <p id="feedback-msg" class="font-bold text-lg"></p>
                <p id="feedback-detail" class="text-sm mt-1"></p>
            </div>

            <!-- Answer Form -->
            <form method="post" action="/answer" id="quiz-form">
                <input type="hidden" name="qindex" value="{{ qindex }}">
                <input type="hidden" name="is_timeout" id="is_timeout" value="0">
                
                <div class="space-y-3" id="options-container">
                {% for idx, opt in enumerate(question['options'], start=1) %}
                    <label class="group relative flex items-center p-4 border-2 border-gray-100 rounded-xl cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition-all duration-200" id="label-{{idx}}">
                        <input type="radio" name="choice" value="{{idx}}" class="w-5 h-5 text-indigo-600 border-gray-300 focus:ring-indigo-500 option-input">
                        <span class="ml-4 text-gray-700 font-medium group-hover:text-indigo-800">{{ opt }}</span>
                    </label>
                {% endfor %}
                </div>

                <button type="submit" id="submit-btn" class="mt-8 w-full bg-indigo-600 text-white font-bold py-4 rounded-xl hover:bg-indigo-700 transition shadow-lg">
                    {{ 'Check Answer' if mode == 'practice' else 'Submit Answer' }}
                </button>
            </form>
        </div>
    </div>
</div>

<script>
    const MODE = "{{ mode }}";
    const CORRECT_IDX = {{ question['answer'] }};
    const OPTIONS = {{ question['options'] | tojson }};
    const IS_LAST = {{ 'true' if qnum == total else 'false' }};
    
    let timeLeft = {{ timer_limit }};
    const totalTime = {{ timer_limit }};
    const timerBar = document.getElementById('timer-bar');
    const timerText = document.getElementById('timer-text');
    const form = document.getElementById('quiz-form');
    const timeoutInput = document.getElementById('is_timeout');
    const submitBtn = document.getElementById('submit-btn');
    const feedbackBox = document.getElementById('client-feedback');
    const feedbackMsg = document.getElementById('feedback-msg');
    const feedbackDetail = document.getElementById('feedback-detail');
    
    let phase = 1; // 1 = Check Answer, 2 = Go Next
    let submitted = false; // Stops timer

    form.addEventListener('submit', function(e) {
        // --- PRACTICE MODE LOGIC ---
        if (MODE === 'practice' && phase === 1 && timeoutInput.value !== '1') {
            e.preventDefault(); // STOP form from reloading
            
            const selected = document.querySelector('input[name="choice"]:checked');
            if (!selected) { alert('Please select an option!'); return; }

            submitted = true; // Pause timer

            try {
                const val = parseInt(selected.value);
                const isCorrect = (val === CORRECT_IDX);
                
                // UI Updates
                feedbackBox.classList.remove('hidden');
                if (isCorrect) {
                    feedbackBox.className = "mb-6 p-4 rounded-lg border animate-pulse bg-green-100 border-green-300";
                    feedbackMsg.className = "font-bold text-lg text-green-800";
                    feedbackMsg.innerText = "✅ Correct Answer!";
                    feedbackDetail.innerText = "";
                    document.getElementById('label-'+val).classList.add('bg-green-50', 'border-green-500');
                } else {
                    feedbackBox.className = "mb-6 p-4 rounded-lg border animate-pulse bg-red-100 border-red-300";
                    feedbackMsg.className = "font-bold text-lg text-red-800";
                    feedbackMsg.innerText = "❌ Wrong Answer!";
                    feedbackDetail.className = "text-sm text-red-700 mt-1";
                    feedbackDetail.innerText = "Correct option: " + OPTIONS[CORRECT_IDX - 1];
                    document.getElementById('label-'+val).classList.add('bg-red-50', 'border-red-500');
                }

                // Audio
                if (isCorrect) playSound('correct');
                else playSound('wrong');
            } catch(err) { console.error(err); }

            // Update Phase & UI
            phase = 2;
            document.querySelectorAll('.option-input').forEach(el => el.disabled = true);
            
            if (IS_LAST) {
                submitBtn.innerText = "Finish Test 🏁";
                submitBtn.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
                submitBtn.classList.add('bg-green-600', 'hover:bg-green-700');
            } else {
                submitBtn.innerText = "Next Question ➡️";
                submitBtn.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
                submitBtn.classList.add('bg-gray-800', 'hover:bg-gray-900');
            }
        } 
        // --- PHASE 2 (SUBMITTING) ---
        else {
            // IMPORTANT FIX: Re-enable inputs so the form sends data!
            document.querySelectorAll('.option-input').forEach(el => el.disabled = false);
        }
    });

    // Timer
    const countdown = setInterval(() => {
        if(submitted) { clearInterval(countdown); return; }
        
        timeLeft--;
        timerText.innerText = timeLeft;
        timerBar.style.width = (timeLeft / totalTime * 100) + "%";

        if (timeLeft <= 5 && timeLeft > 0) {
            timerBar.classList.remove('bg-indigo-500');
            timerBar.classList.add('bg-red-500');
            try { playSound('tick'); } catch(e) {} 
        }

        if (timeLeft <= 0) {
            clearInterval(countdown);
            timeoutInput.value = "1";
            form.submit(); 
        }
    }, 1000);
</script>
'''

RESULT_CONTENT = '''
<div class="max-w-2xl mx-auto bg-white rounded-2xl shadow-2xl overflow-hidden fade-in print:shadow-none">
    <div class="bg-indigo-600 p-8 text-center print:bg-white print:text-black print:border-b">
        <h2 class="text-3xl font-bold text-white mb-1 print:text-black">Session Result</h2>
        <p class="text-indigo-200 print:text-gray-600">{{ user_name }} • {{ date }}</p>
    </div>

    <div class="p-8">
        <div class="grid grid-cols-2 gap-6 mb-8">
            <div class="text-center p-4 bg-green-50 rounded-xl border border-green-100 print:border-gray-300">
                <p class="text-sm text-green-600 font-bold uppercase tracking-wide">Score</p>
                <p class="text-4xl font-bold text-gray-800 mt-1">{{ score }} <span class="text-lg text-gray-400">/ {{ total }}</span></p>
            </div>
            <div class="text-center p-4 bg-blue-50 rounded-xl border border-blue-100 print:border-gray-300">
                <p class="text-sm text-blue-600 font-bold uppercase tracking-wide">Accuracy</p>
                <p class="text-4xl font-bold text-gray-800 mt-1">{{ accuracy }}%</p>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="space-y-3 no-print">
            <button onclick="window.print()" class="block w-full text-center bg-gray-800 text-white font-bold py-3 rounded-xl hover:bg-gray-900 transition shadow">
                🖨️ Print / Save as PDF
            </button>
            
            <a href="/review" class="block w-full text-center bg-yellow-500 text-white font-bold py-3 rounded-xl hover:bg-yellow-600 transition shadow">
                📝 Detailed Answer Review
            </a>
            
            <div class="flex gap-3">
                <a href="/practice?restart=1" class="flex-1 text-center bg-indigo-600 text-white font-bold py-3 rounded-xl hover:bg-indigo-700 transition shadow">
                    Restart
                </a>
                <a href="/" class="flex-1 text-center bg-white text-gray-600 font-bold py-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition">
                    Home
                </a>
            </div>
        </div>

        <!-- Print Only Footer -->
        <div class="hidden print-only text-center text-sm text-gray-500 mt-8">
            Generated by MCQ Master Suite on {{ date }}
        </div>
    </div>
</div>
'''

REVIEW_CONTENT = '''
<div class="max-w-4xl mx-auto fade-in">
    <div class="flex justify-between items-center mb-6 no-print">
        <h2 class="text-2xl font-bold text-gray-800">📝 Review Answers</h2>
        <div class="gap-2 flex">
            <button onclick="window.print()" class="bg-gray-200 px-4 py-2 rounded font-bold hover:bg-gray-300">Print</button>
            <a href="/" class="text-indigo-600 font-medium hover:underline flex items-center">Back to Home</a>
        </div>
    </div>

    <div class="space-y-6">
    {% for item in reviews %}
        <div class="bg-white p-6 rounded-xl shadow-sm border-l-4 {{ 'border-green-500' if item.is_correct else 'border-red-500' }} break-inside-avoid">
            <div class="flex justify-between items-start mb-3">
                <h3 class="text-lg font-semibold text-gray-900">{{ loop.index }}. {{ item.question }}</h3>
                {% if item.is_correct %}
                    <span class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full font-bold border border-green-200">Correct</span>
                {% elif item.is_timeout %}
                    <span class="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full font-bold border border-gray-200">Time Up</span>
                {% else %}
                    <span class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded-full font-bold border border-red-200">Wrong</span>
                {% endif %}
            </div>

            <div class="grid grid-cols-2 gap-4 mt-2 text-sm">
                <div class="p-3 rounded-lg {{ 'bg-green-50' if item.is_correct else 'bg-red-50' }}">
                    <p class="text-xs text-gray-500 uppercase font-bold mb-1">Your Answer</p>
                    <p class="font-medium {{ 'text-green-700' if item.is_correct else 'text-red-700' }}">
                        {{ item.options[item.user_choice - 1] if item.user_choice else 'Skipped' }}
                    </p>
                </div>
                {% if not item.is_correct %}
                <div class="p-3 rounded-lg bg-blue-50">
                    <p class="text-xs text-gray-500 uppercase font-bold mb-1">Correct Answer</p>
                    <p class="font-medium text-blue-700">
                        {{ item.options[item.correct_choice - 1] }}
                    </p>
                </div>
                {% endif %}
            </div>
        </div>
    {% endfor %}
    </div>
</div>
'''

# --- Routes ---

@app.route('/')
def index():
    qs = load_questions()
    scores = load_scores()
    subjects = sorted(list(set([q.get('subject', 'General') for q in qs]))) if qs else []
    session.pop('authenticated', None)
    return render_template_string(BASE_LAYOUT, 
        content=render_template_string(INDEX_CONTENT, total=len(qs), subjects=subjects, scores=scores, min=min))

@app.route('/start_session', methods=['POST'])
def start_session():
    user_name = request.form.get('user_name')
    access_pin = request.form.get('access_pin')
    subject = request.form.get('subject')
    difficulty = request.form.get('difficulty')
    mode = request.form.get('mode')
    try:
        limit = int(request.form.get('num_questions'))
    except: limit = 10

    if access_pin != ACCESS_PIN:
        flash('❌ Invalid PIN', 'warning')
        return redirect(url_for('index'))

    qs = load_questions()
    if subject != 'all':
        qs = [q for q in qs if q.get('subject', 'General') == subject]
    
    if not qs:
        flash('⚠️ No questions found for this subject.', 'warning')
        return redirect(url_for('index'))

    random.shuffle(qs)
    qs = qs[:limit]
    timers = {'easy': 60, 'medium': 30, 'hard': 15}
    
    session['user_name'] = user_name
    session['authenticated'] = True
    reset_session_file()
    
    sess_data = {
        'questions': qs,
        'pos': 0,
        'score': 0,
        'correct': 0,
        'attempted': 0,
        'difficulty': difficulty,
        'mode': mode,
        'timer': timers.get(difficulty, 30),
        'start_time': time.time(),
        'subject': subject,
        'reviews': []
    }
    save_session_data(sess_data)
    return redirect(url_for('practice'))

@app.route('/practice')
def practice():
    if not session.get('authenticated'): return redirect(url_for('index'))
    sess = get_session_data()
    if not sess: return redirect(url_for('index'))

    if request.args.get('restart'):
        sess['pos'] = 0; sess['score'] = 0; sess['correct'] = 0; sess['attempted'] = 0
        sess['reviews'] = []; sess['start_time'] = time.time()
        random.shuffle(sess['questions'])
        save_session_data(sess)
        return redirect(url_for('practice'))

    if sess['pos'] >= len(sess['questions']):
        return redirect(url_for('end'))

    question = sess['questions'][sess['pos']]
    
    return render_template_string(BASE_LAYOUT,
        content=render_template_string(PRACTICE_CONTENT,
            user_name=session['user_name'],
            question=question,
            qindex=sess['pos'],
            qnum=sess['pos'] + 1,
            total=len(sess['questions']),
            difficulty=sess['difficulty'],
            mode=sess['mode'],
            timer_limit=sess['timer'],
            subject=sess.get('subject', 'General').title(),
            enumerate=enumerate
        )
    )

@app.route('/answer', methods=['POST'])
def answer():
    if not session.get('authenticated'): return redirect(url_for('index'))
    sess = get_session_data()
    if not sess: return redirect(url_for('index'))
    
    choice_str = request.form.get('choice')
    is_timeout = request.form.get('is_timeout') == '1'
    
    if not choice_str and not is_timeout:
        flash('Please select an option', 'warning')
        return redirect(url_for('practice'))

    question = sess['questions'][sess['pos']]
    correct_ans = question['answer']
    
    user_choice = int(choice_str) if choice_str else None
    is_correct = (user_choice == correct_ans) and not is_timeout
    
    # Update Stats
    sess['attempted'] += 1
    
    if is_correct:
        sess['score'] += 1
        sess['correct'] += 1
    else:
        if sess['difficulty'] == 'hard':
            sess['score'] -= 0.25
    
    # Save Review
    sess['reviews'].append({
        'question': question['question'],
        'options': question['options'],
        'user_choice': user_choice,
        'correct_choice': correct_ans,
        'is_correct': is_correct,
        'is_timeout': is_timeout
    })
    
    # Move Next (Always, for both modes now)
    sess['pos'] += 1
    save_session_data(sess)
    
    return redirect(url_for('practice'))

@app.route('/end')
def end():
    if not session.get('authenticated'): return redirect(url_for('index'))
    sess = get_session_data()
    if not sess: return redirect(url_for('index'))
    
    total = len(sess['questions'])
    acc = int((sess['correct'] / total * 100)) if total > 0 else 0
    
    score_record = {
        'name': session['user_name'],
        'score': sess['score'],
        'accuracy': acc,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_score(score_record)
    
    return render_template_string(BASE_LAYOUT,
        content=render_template_string(RESULT_CONTENT,
            user_name=session['user_name'],
            score=sess['score'],
            total=total,
            accuracy=acc,
            date=datetime.now().strftime("%Y-%m-%d")
        )
    )

@app.route('/review')
def review():
    if not session.get('authenticated'): return redirect(url_for('index'))
    sess = get_session_data()
    return render_template_string(BASE_LAYOUT, 
        content=render_template_string(REVIEW_CONTENT, reviews=sess.get('reviews', [])))

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return redirect(url_for('index'))
    
    try:
        lines = file.read().decode('utf-8').splitlines()
        reader = csv.reader(lines)
        new_qs = []
        for row in reader:
            if len(row) >= 6 and row[0].strip():
                try:
                    ans = int(row[5].strip())
                    subj = row[6].strip() if len(row) > 6 else 'General'
                    new_qs.append({
                        'question': row[0],
                        'options': [x.strip() for x in row[1:5]],
                        'answer': ans,
                        'subject': subj
                    })
                except: continue
        
        if new_qs:
            curr = load_questions()
            curr.extend(new_qs)
            save_questions(curr)
            flash(f'✅ Uploaded {len(new_qs)} questions successfully!', 'success')
        else: flash('⚠️ No valid data found.', 'warning')
    except Exception as e: flash(f'Error: {e}', 'error')
    
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(SCORES_FILE): os.remove(SCORES_FILE)
    reset_session_file()
    flash('🗑️ All data cleared.', 'success')
    return redirect(url_for('index'))

def open_browser():
    # Give the server a moment to start
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    if not os.path.exists(DATA_FILE): save_questions([])
    
    # Start browser in a separate thread so it doesn't block the server
    if not os.environ.get("WERKZEUG_RUN_MAIN"): # Prevent opening twice on reload
        Timer(1, open_browser).start()
        
    print(f"App running! Login PIN is: {ACCESS_PIN}")
    # Setting use_reloader=False is important for PyInstaller
    app.run(debug=False, use_reloader=False)