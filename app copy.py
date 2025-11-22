"""
Single-file Flask app for uploading MCQs (CSV) and practising them.
Save this as app.py and run: `pip install flask` then `python app.py`.
Open http://127.0.0.1:5000

CSV format expected (header optional):
question,option1,option2,option3,option4,answer_index
answer_index is 1,2,3 or 4 corresponding to the correct option

Features:
- Upload CSV of MCQs
- Stores questions to a JSON file (questions.json)
- Practice mode: shows random questions, tracks score
- Simple progress/results page

This is intentionally single-file and minimal for easy testing.
"""
from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, flash
import csv
import json
import os
import random

app = Flask(__name__)
app.secret_key = 'change-this-secret'
DATA_FILE = 'questions.json'

# --- Helper functions ---

def load_questions():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_questions(qs):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)


# --- Routes ---

INDEX_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCQ Practice</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <h1 class="mb-4">MCQ Practice (Python Flask)</h1>
  <div class="row">
    <div class="col-md-6">
      <div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">Upload MCQs (CSV)</h5>
          <form action="/upload" method="post" enctype="multipart/form-data">
            <div class="mb-3">
              <input class="form-control" type="file" name="file" accept=".csv,text/csv">
            </div>
            <button class="btn btn-primary" type="submit">Upload</button>
          </form>
          <small class="text-muted d-block mt-2">CSV columns: question,option1,option2,option3,option4,answer_index (1-4)</small>
        </div>
      </div>

      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Current Questions</h5>
          <p class="card-text">Total: {{ total }}</p>
          <a class="btn btn-success" href="/practice">Start Practice</a>
          <a class="btn btn-secondary" href="/download">Download JSON</a>
        </div>
      </div>

    </div>
    <div class="col-md-6">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          <div class="alert alert-info">
            {{ messages[0] }}
          </div>
        {% endif %}
      {% endwith %}

      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Quick Tips</h5>
          <ul>
            <li>Upload CSV with headers or without headers.</li>
            <li>You can upload multiple times; this will append questions (duplicates possible).</li>
            <li>During practice you will see one question at a time with four options.</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>
'''

PRACTICE_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Practice</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <h2>Practice Session</h2>
  {% if not question %}
    <div class="alert alert-warning">No questions available. Please upload a CSV first.</div>
    <a class="btn btn-primary" href="/">Back</a>
  {% else %}
    <div class="card mb-3">
      <div class="card-body">
        <h5>Question {{ qnum }} / {{ total }}</h5>
        <p class="lead">{{ question['question'] }}</p>
        <form method="post" action="/answer">
          {% for idx, opt in enumerate(question['options'], start=1) %}
            <div class="form-check">
              <input class="form-check-input" type="radio" name="choice" id="opt{{idx}}" value="{{idx}}" required>
              <label class="form-check-label" for="opt{{idx}}">{{ opt }}</label>
            </div>
          {% endfor %}
          <input type="hidden" name="qindex" value="{{ qindex }}">
          <input type="hidden" name="qnum" value="{{ qnum }}">
          <div class="mt-3">
            <button class="btn btn-primary">Submit Answer</button>
          </div>
        </form>
      </div>
    </div>

    <div>
      <p>Score: {{ score }} | Correct: {{ correct }} | Attempted: {{ attempted }}</p>
      <a class="btn btn-secondary" href="/end">End Session</a>
    </div>
  {% endif %}
</div>
</body>
</html>
'''

RESULT_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Result</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <h2>Session Result</h2>
  <div class="card">
    <div class="card-body">
      <p>Total Questions Attempted: {{ attempted }}</p>
      <p>Correct: {{ correct }}</p>
      <p>Score: {{ score }}</p>
      <a class="btn btn-primary" href="/practice?restart=1">Start Again</a>
      <a class="btn btn-secondary" href="/">Home</a>
    </div>
  </div>
</div>
</body>
</html>
'''


@app.route('/')
def index():
    qs = load_questions()
    return render_template_string(INDEX_HTML, total=len(qs))


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        flash('No file uploaded')
        return redirect(url_for('index'))
    try:
        text = file.read().decode('utf-8').splitlines()
        reader = csv.reader(text)
        new = []
        for row in reader:
            # skip empty rows
            if not row or all([not c.strip() for c in row]):
                continue
            # accept rows with at least 6 columns; extra columns ignored
            if len(row) < 6:
                continue
            q = row[0].strip()
            opts = [row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip()]
            try:
                ans = int(row[5])
                if ans < 1 or ans > 4:
                    continue
            except:
                continue
            new.append({'question': q, 'options': opts, 'answer': ans})
        if not new:
            flash('No valid questions found in CSV.')
            return redirect(url_for('index'))
        qs = load_questions()
        qs.extend(new)
        save_questions(qs)
        flash(f'Uploaded {len(new)} questions. Total now {len(qs)}')
    except Exception as e:
        flash('Failed to process file: ' + str(e))
    return redirect(url_for('index'))


@app.route('/download')
def download():
    if not os.path.exists(DATA_FILE):
        flash('No data file to download')
        return redirect(url_for('index'))
    return send_from_directory(directory='.', filename=DATA_FILE, as_attachment=True)


# Simple practice state kept in server-side session-like file. For demo only.
SESSION_FILE = 'session.json'


def reset_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


def save_session(s):
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f)


def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.route('/practice')
def practice():
    qs = load_questions()
    if not qs:
        return render_template_string(PRACTICE_HTML, question=None)
    # build session if not exists or restart requested
    if request.args.get('restart') == '1' or not load_session():
        order = list(range(len(qs)))
        random.shuffle(order)
        sess = {
            'order': order,
            'pos': 0,
            'score': 0,
            'correct': 0,
            'attempted': 0
        }
        save_session(sess)
    else:
        sess = load_session()
    pos = sess['pos']
    if pos >= len(sess['order']):
        return redirect(url_for('end'))
    qindex = sess['order'][pos]
    question = qs[qindex]
    return render_template_string(PRACTICE_HTML,
                                  question=question,
                                  qindex=qindex,
                                  qnum=pos+1,
                                  total=len(sess['order']),
                                  score=sess['score'],
                                  correct=sess['correct'],
                                  attempted=sess['attempted'],
                                  enumerate=enumerate)


@app.route('/answer', methods=['POST'])
def answer():
    choice = request.form.get('choice')
    qindex = int(request.form.get('qindex'))
    qnum = int(request.form.get('qnum'))
    qs = load_questions()
    sess = load_session()
    if not sess:
        flash('Session expired. Start again.')
        return redirect(url_for('practice'))
    pos = sess['pos']
    # validate
    if pos+1 != qnum:
        # user might tamperper
        pass
    try:
        choice = int(choice)
    except:
        choice = None
    correct_ans = qs[qindex]['answer']
    sess['attempted'] += 1
    if choice == correct_ans:
        sess['score'] += 1
        sess['correct'] += 1
        flash('Correct!')
    else:
        flash(f'Wrong. Correct answer: option {correct_ans}')
    sess['pos'] += 1
    save_session(sess)
    if sess['pos'] >= len(sess['order']):
        return redirect(url_for('end'))
    return redirect(url_for('practice'))


@app.route('/end')
def end():
    sess = load_session() or {'attempted': 0, 'correct': 0, 'score': 0}
    attempted = sess.get('attempted', 0)
    correct = sess.get('correct', 0)
    score = sess.get('score', 0)
    reset_session()
    return render_template_string(RESULT_HTML, attempted=attempted, correct=correct, score=score)


if __name__ == '__main__':
    # create empty data file if not exists
    if not os.path.exists(DATA_FILE):
        save_questions([])
    app.run(debug=True)
