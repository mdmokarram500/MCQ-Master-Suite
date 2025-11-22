<?php
session_start();

// --- Configuration ---
define('ACCESS_PIN', '1234');
define('DATA_FILE', 'questions.json');
define('SCORES_FILE', 'scores.json');

// --- Helper Functions ---

function getQuestions() {
    if (!file_exists(DATA_FILE)) return [];
    $json = file_get_contents(DATA_FILE);
    return json_decode($json, true) ?? [];
}

function saveQuestions($data) {
    file_put_contents(DATA_FILE, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

function getScores() {
    if (!file_exists(SCORES_FILE)) return [];
    $json = file_get_contents(SCORES_FILE);
    $scores = json_decode($json, true) ?? [];
    
    // Sort by score (desc), then accuracy (desc)
    usort($scores, function($a, $b) {
        if ($a['score'] == $b['score']) {
            return $b['accuracy'] - $a['accuracy'];
        }
        return $b['score'] - $a['score'];
    });
    
    return array_slice($scores, 0, 10);
}

function saveScore($record) {
    $scores = getScores(); // Gets top 10
    // Reload raw to append
    if (file_exists(SCORES_FILE)) {
        $raw = json_decode(file_get_contents(SCORES_FILE), true) ?? [];
    } else {
        $raw = [];
    }
    $raw[] = $record;
    file_put_contents(SCORES_FILE, json_encode($raw, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

function setFlash($msg, $type = 'info') {
    $_SESSION['flash'][] = ['msg' => $msg, 'type' => $type];
}

function getFlash() {
    $msgs = $_SESSION['flash'] ?? [];
    unset($_SESSION['flash']);
    return $msgs;
}

// --- Routing / Controller Logic ---

$page = $_GET['page'] ?? 'home';

// 1. Upload Handler
if ($page === 'upload' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if (isset($_FILES['csv_file']) && $_FILES['csv_file']['error'] === UPLOAD_ERR_OK) {
        $tmpName = $_FILES['csv_file']['tmp_name'];
        
        // Auto-detect line endings for cross-platform compatibility
        ini_set('auto_detect_line_endings', true);
        
        $rows = array_map('str_getcsv', file($tmpName));
        $newQs = [];
        
        foreach ($rows as $row) {
            // Remove invisible BOM characters from the first column if present
            if (isset($row[0])) {
                $row[0] = preg_replace('/[\x00-\x1F\x80-\xFF]/', '', $row[0]);
            }

            // Expecting: question, opt1, opt2, opt3, opt4, ans_index(1-4), subject
            if (count($row) >= 6 && !empty(trim($row[0]))) {
                $subj = isset($row[6]) ? trim($row[6]) : 'General';
                $ansIndex = (int)trim($row[5]);
                
                // Validate Answer Index (Must be 1-4)
                if ($ansIndex < 1 || $ansIndex > 4) $ansIndex = 1; // Default to 1 if invalid

                $newQs[] = [
                    'question' => trim($row[0]),
                    'options'  => [trim($row[1]), trim($row[2]), trim($row[3]), trim($row[4])],
                    'answer'   => $ansIndex,
                    'subject'  => $subj
                ];
            }
        }
        
        if (!empty($newQs)) {
            $current = getQuestions();
            $merged = array_merge($current, $newQs);
            saveQuestions($merged);
            setFlash("Successfully uploaded " . count($newQs) . " questions.", "success");
        } else {
            setFlash("No valid questions found in CSV.", "error");
        }
    }
    header('Location: index.php');
    exit;
}

// 2. Clear Data Handler
if ($page === 'clear_all' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if (file_exists(DATA_FILE)) unlink(DATA_FILE);
    if (file_exists(SCORES_FILE)) unlink(SCORES_FILE);
    unset($_SESSION['quiz']);
    setFlash("All system data cleared.", "success");
    header('Location: index.php');
    exit;
}

// 3. Start Session Handler
if ($page === 'start_session' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $pin = $_POST['access_pin'] ?? '';
    if ($pin !== ACCESS_PIN) {
        setFlash("Invalid Access PIN.", "error");
        header('Location: index.php');
        exit;
    }

    $userName = htmlspecialchars($_POST['user_name']);
    $subject = $_POST['subject'] ?? 'all';
    $mode = $_POST['mode'] ?? 'practice';
    $difficulty = $_POST['difficulty'] ?? 'medium';
    $count = (int)($_POST['num_questions'] ?? 10);

    $allQs = getQuestions();
    
    // Filter by subject
    if ($subject !== 'all') {
        $allQs = array_filter($allQs, function($q) use ($subject) {
            return ($q['subject'] ?? 'General') === $subject;
        });
    }

    if (empty($allQs)) {
        setFlash("No questions found for subject: $subject", "warning");
        header('Location: index.php');
        exit;
    }

    shuffle($allQs);
    $selectedQs = array_slice($allQs, 0, $count);

    // Timer Logic
    $timers = ['easy' => 60, 'medium' => 30, 'hard' => 15];
    $timerLimit = $timers[$difficulty] ?? 30;

    // Initialize Session
    $_SESSION['quiz'] = [
        'user_name' => $userName,
        'authenticated' => true,
        'questions' => $selectedQs,
        'pos' => 0,
        'score' => 0,
        'correct' => 0,
        'attempted' => 0,
        'difficulty' => $difficulty,
        'mode' => $mode,
        'timer' => $timerLimit,
        'subject' => $subject,
        'reviews' => [],
        'start_date' => date('Y-m-d')
    ];

    header('Location: index.php?page=practice');
    exit;
}

// 4. Answer Handler
if ($page === 'answer' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!isset($_SESSION['quiz'])) { header('Location: index.php'); exit; }

    $qIdx = $_SESSION['quiz']['pos'];
    $currentQ = $_SESSION['quiz']['questions'][$qIdx];
    
    $userChoice = isset($_POST['choice']) ? (int)$_POST['choice'] : null;
    $isTimeout = ($_POST['is_timeout'] ?? '0') === '1';
    
    $correctChoice = (int)$currentQ['answer'];
    $isCorrect = ($userChoice === $correctChoice) && !$isTimeout;

    // Scoring
    $_SESSION['quiz']['attempted']++;
    if ($isCorrect) {
        $_SESSION['quiz']['score']++;
        $_SESSION['quiz']['correct']++;
    } else {
        if ($_SESSION['quiz']['difficulty'] === 'hard') {
            $_SESSION['quiz']['score'] -= 0.25;
        }
    }

    // Save Review
    $_SESSION['quiz']['reviews'][] = [
        'question' => $currentQ['question'],
        'options' => $currentQ['options'],
        'user_choice' => $userChoice,
        'correct_choice' => $correctChoice,
        'is_correct' => $isCorrect,
        'is_timeout' => $isTimeout
    ];

    // Advance
    $_SESSION['quiz']['pos']++;

    header('Location: index.php?page=practice');
    exit;
}

// 5. End Session (Manual)
if ($page === 'end_early') {
    unset($_SESSION['quiz']);
    header('Location: index.php');
    exit;
}

// --- View Rendering ---
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MCQ Master Suite (PHP)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @media print {
            .no-print { display: none !important; }
            .print-only { display: block !important; }
            body { background: white; }
        }
        .print-only { display: none; }
    </style>
    <!-- Audio Context Script -->
    <script>
        let audioCtx = null;
        try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}

        function unlockAudio() {
            if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
            document.removeEventListener('click', unlockAudio);
        }
        document.addEventListener('click', unlockAudio);

        function playSound(type) {
            if (!audioCtx) return;
            const osc = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            osc.connect(gainNode);
            gainNode.connect(audioCtx.destination);

            const now = audioCtx.currentTime;
            if (type === 'correct') {
                osc.type = 'sine';
                osc.frequency.setValueAtTime(500, now);
                osc.frequency.exponentialRampToValueAtTime(1000, now + 0.1);
                gainNode.gain.setValueAtTime(0.1, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.5);
                osc.start(); osc.stop(now + 0.5);
            } else if (type === 'wrong') {
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(150, now);
                osc.frequency.linearRampToValueAtTime(100, now + 0.3);
                gainNode.gain.setValueAtTime(0.1, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
                osc.start(); osc.stop(now + 0.3);
            } else if (type === 'tick') {
                osc.type = 'square';
                osc.frequency.setValueAtTime(800, now);
                gainNode.gain.setValueAtTime(0.05, now);
                gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
                osc.start(); osc.stop(now + 0.05);
            }
        }
    </script>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col">

    <!-- Navbar -->
    <nav class="bg-indigo-600 text-white p-4 shadow-md no-print">
        <div class="container mx-auto flex justify-between items-center">
            <a href="index.php" class="text-xl font-bold flex items-center gap-2">
                <span>🎓</span> MCQ Master Suite
            </a>
            <?php if(isset($_SESSION['quiz'])): ?>
                <a href="index.php?page=end_early" class="text-sm bg-indigo-500 hover:bg-indigo-700 px-3 py-1 rounded transition">Exit Session</a>
            <?php endif; ?>
        </div>
    </nav>

    <div class="container mx-auto p-4 md:p-8 max-w-6xl flex-grow">
        
        <!-- Flash Messages -->
        <?php foreach(getFlash() as $flash): ?>
            <div class="mb-6 p-4 rounded-lg shadow-sm border-l-4 flex items-center justify-between no-print
                <?= $flash['type'] == 'success' ? 'bg-green-50 border-green-500 text-green-700' : 
                   ($flash['type'] == 'error' ? 'bg-red-50 border-red-500 text-red-700' : 
                   'bg-yellow-50 border-yellow-500 text-yellow-700') ?>">
                <span><?= $flash['msg'] ?></span>
            </div>
        <?php endforeach; ?>

        <!-- PAGE: HOME -->
        <?php if ($page === 'home'): 
            $qs = getQuestions();
            $scores = getScores();
            $total = count($qs);
            $subjects = array_unique(array_column($qs, 'subject'));
            sort($subjects);
        ?>
            <div class="grid lg:grid-cols-3 gap-8 fade-in">
                <!-- Left Col: Setup -->
                <div class="lg:col-span-2 space-y-6">
                    <div class="bg-white p-8 rounded-xl shadow-lg border-t-4 border-indigo-500">
                        <h2 class="text-2xl font-bold text-indigo-700 mb-2">🚀 Start New Session</h2>
                        <p class="text-gray-500 mb-6">Customize your test parameters below.</p>

                        <?php if ($total > 0): ?>
                        <form action="index.php?page=start_session" method="post" class="grid md:grid-cols-2 gap-6">
                            <div class="md:col-span-2 grid md:grid-cols-2 gap-4">
                                <input type="text" name="user_name" placeholder="Your Name" required
                                    class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 outline-none">
                                <input type="password" name="access_pin" placeholder="PIN (1234)" required
                                    class="w-full p-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 outline-none">
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Subject</label>
                                <select name="subject" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                                    <option value="all">📚 All Subjects</option>
                                    <?php foreach($subjects as $sub): ?>
                                        <option value="<?= htmlspecialchars($sub) ?>"><?= htmlspecialchars($sub) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Mode</label>
                                <select name="mode" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                                    <option value="practice">🛡️ Practice (Feedback)</option>
                                    <option value="exam">⏱️ Exam (Silent)</option>
                                </select>
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Difficulty</label>
                                <select name="difficulty" class="w-full p-3 rounded-lg border border-gray-300 bg-white outline-none">
                                    <option value="easy">🟢 Easy (60s)</option>
                                    <option value="medium" selected>🟡 Medium (30s)</option>
                                    <option value="hard">🔴 Hard (15s, Neg. Mark)</option>
                                </select>
                            </div>

                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Count</label>
                                <input type="number" name="num_questions" min="1" max="<?= $total ?>" value="<?= min(10, $total) ?>"
                                    class="w-full p-3 rounded-lg border border-gray-300 outline-none">
                            </div>

                            <button type="submit" class="md:col-span-2 w-full bg-indigo-600 text-white font-bold py-4 rounded-lg hover:bg-indigo-700 transition shadow-xl text-lg">
                                Start Test
                            </button>
                        </form>
                        <?php else: ?>
                            <div class="text-center py-10 text-gray-400 bg-gray-50 rounded-lg border-dashed border-2 border-gray-200">
                                Database is empty. Upload CSV to begin.
                            </div>
                        <?php endif; ?>
                    </div>

                    <!-- Upload -->
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                        <div class="flex justify-between items-center mb-4">
                            <h2 class="text-lg font-bold text-gray-800">📂 Upload Data</h2>
                            <span class="bg-indigo-100 text-indigo-800 text-sm font-bold px-3 py-1 rounded-full">Total Qs: <?= $total ?></span>
                        </div>
                        <form action="index.php?page=upload" method="post" enctype="multipart/form-data" class="flex gap-4 items-center">
                            <input type="file" name="csv_file" accept=".csv" required 
                                class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"/>
                            <button type="submit" class="bg-gray-800 text-white py-2 px-6 rounded-lg hover:bg-gray-900 whitespace-nowrap">Upload</button>
                        </form>
                        <p class="text-xs text-gray-400 mt-2">CSV: <code>question,opt1,opt2,opt3,opt4,ans_idx(1-4),subject</code></p>
                    </div>
                </div>

                <!-- Right Col: Leaderboard -->
                <div class="space-y-6">
                    <div class="bg-white p-6 rounded-xl shadow-lg">
                        <div class="flex items-center justify-between mb-4 border-b pb-2">
                            <h2 class="text-xl font-bold text-yellow-600">🏆 Leaderboard</h2>
                            <span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded">Top 10</span>
                        </div>
                        
                        <div class="space-y-3 max-h-[400px] overflow-y-auto">
                            <?php if(empty($scores)): ?>
                                <p class="text-center text-gray-400 py-4 text-sm">No records yet.</p>
                            <?php else: ?>
                                <?php foreach($scores as $idx => $s): ?>
                                <div class="flex justify-between items-center p-3 rounded-lg <?= $idx < 3 ? 'bg-yellow-50 border border-yellow-100' : 'bg-gray-50' ?>">
                                    <div class="flex items-center gap-3">
                                        <span class="font-bold text-gray-400 w-4 text-center"><?= $idx + 1 ?></span>
                                        <div>
                                            <p class="font-bold text-gray-800 text-sm"><?= htmlspecialchars($s['name']) ?></p>
                                            <p class="text-xs text-gray-400"><?= htmlspecialchars($s['date']) ?></p>
                                        </div>
                                    </div>
                                    <div class="text-right">
                                        <p class="font-bold text-indigo-600"><?= number_format($s['score'], 2) ?></p>
                                        <p class="text-xs text-gray-500"><?= $s['accuracy'] ?>%</p>
                                    </div>
                                </div>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </div>
                    </div>

                    <div class="bg-white p-6 rounded-xl shadow-sm border border-red-100">
                        <h2 class="text-sm font-bold text-red-600 mb-3">Danger Zone</h2>
                        <form action="index.php?page=clear_all" method="post" onsubmit="return confirm('Delete ALL data?');">
                            <button class="w-full text-red-500 bg-red-50 py-2 rounded-lg hover:bg-red-100 transition text-sm">Reset System Data</button>
                        </form>
                    </div>
                </div>
            </div>

        <!-- PAGE: PRACTICE / QUIZ -->
        <?php elseif ($page === 'practice'): 
            if (!isset($_SESSION['quiz'])) { echo "<script>window.location='index.php';</script>"; exit; }
            
            $quiz = $_SESSION['quiz'];
            $totalQs = count($quiz['questions']);
            
            // Check if finished
            if ($quiz['pos'] >= $totalQs) {
                // Calculate final stats and save
                $accuracy = $totalQs > 0 ? round(($quiz['correct'] / $totalQs) * 100) : 0;
                saveScore([
                    'name' => $quiz['user_name'],
                    'score' => $quiz['score'],
                    'accuracy' => $accuracy,
                    'date' => date('Y-m-d H:i')
                ]);
                echo "<script>window.location='index.php?page=result';</script>";
                exit;
            }

            $q = $quiz['questions'][$quiz['pos']];
            $qNum = $quiz['pos'] + 1;
        ?>
            <div class="max-w-3xl mx-auto fade-in">
                <!-- Header info -->
                <div class="flex justify-between items-end mb-4 px-1">
                    <div>
                        <p class="text-xs font-bold text-gray-400 uppercase tracking-wider">Candidate</p>
                        <p class="font-bold text-gray-800"><?= htmlspecialchars($quiz['user_name']) ?> 
                            <span class="text-xs font-normal text-gray-500 ml-1">
                                (<?= ucfirst($quiz['difficulty']) ?> / <?= ucfirst($quiz['mode']) ?>)
                            </span>
                        </p>
                    </div>
                    <div class="text-right">
                        <span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-sm font-bold">
                            Q <?= $qNum ?> / <?= $totalQs ?>
                        </span>
                        <?php if ($quiz['subject'] !== 'all'): ?>
                        <span class="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm font-bold ml-2">
                            <?= htmlspecialchars($quiz['subject']) ?>
                        </span>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Card -->
                <div class="bg-white rounded-2xl shadow-xl overflow-hidden mb-6 relative">
                    <!-- Timer Bar -->
                    <div class="h-2 w-full bg-gray-100">
                        <div id="timer-bar" class="h-full bg-indigo-500 transition-all duration-1000 ease-linear" style="width: 100%;"></div>
                    </div>
                    
                    <div class="p-6 md:p-8 relative">
                        <!-- Timer Display -->
                        <div class="absolute top-4 right-4 flex items-center gap-1 font-mono font-bold text-xl">
                            <span id="timer-icon" class="text-indigo-500">⏱️</span>
                            <span id="timer-text" class="text-gray-700"><?= $quiz['timer'] ?></span>
                        </div>

                        <!-- Question Text -->
                        <h3 class="text-xl md:text-2xl font-medium text-gray-800 mt-8 mb-8 leading-relaxed pr-12">
                            <?= htmlspecialchars($q['question']) ?>
                        </h3>

                        <!-- Local Feedback Box (Hidden by default) -->
                        <div id="client-feedback" class="hidden mb-6 p-4 rounded-lg border animate-pulse">
                            <p id="feedback-msg" class="font-bold text-lg"></p>
                            <p id="feedback-detail" class="text-sm mt-1"></p>
                        </div>

                        <form action="index.php?page=answer" method="post" id="quiz-form">
                            <input type="hidden" name="is_timeout" id="is_timeout" value="0">
                            
                            <div class="space-y-3">
                                <?php foreach($q['options'] as $idx => $opt): $val = $idx + 1; ?>
                                <label class="group relative flex items-center p-4 border-2 border-gray-100 rounded-xl cursor-pointer hover:border-indigo-500 hover:bg-indigo-50 transition-all duration-200" id="label-<?= $val ?>">
                                    <input type="radio" name="choice" value="<?= $val ?>" class="w-5 h-5 text-indigo-600 border-gray-300 focus:ring-indigo-500 option-input">
                                    <span class="ml-4 text-gray-700 font-medium group-hover:text-indigo-800"><?= htmlspecialchars($opt) ?></span>
                                </label>
                                <?php endforeach; ?>
                            </div>

                            <button type="submit" id="submit-btn" class="mt-8 w-full bg-indigo-600 text-white font-bold py-4 rounded-xl hover:bg-indigo-700 transition shadow-lg">
                                <?= $quiz['mode'] == 'practice' ? 'Check Answer' : 'Submit Answer' ?>
                            </button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- JS Logic for Practice Mode & Timer -->
            <script>
                const MODE = "<?= $quiz['mode'] ?>";
                const CORRECT_IDX = <?= $q['answer'] ?>;
                const OPTIONS = <?= json_encode($q['options']) ?>;
                const IS_LAST = <?= ($qNum == $totalQs) ? 'true' : 'false' ?>;
                
                let timeLeft = <?= $quiz['timer'] ?>;
                const totalTime = <?= $quiz['timer'] ?>;
                const timerBar = document.getElementById('timer-bar');
                const timerText = document.getElementById('timer-text');
                const form = document.getElementById('quiz-form');
                const timeoutInput = document.getElementById('is_timeout');
                const submitBtn = document.getElementById('submit-btn');
                const feedbackBox = document.getElementById('client-feedback');
                const feedbackMsg = document.getElementById('feedback-msg');
                const feedbackDetail = document.getElementById('feedback-detail');
                
                let phase = 1; // 1 = Check, 2 = Next
                let submitted = false;

                form.addEventListener('submit', function(e) {
                    // Practice Mode Interaction
                    if (MODE === 'practice' && phase === 1 && timeoutInput.value !== '1') {
                        e.preventDefault();
                        const selected = document.querySelector('input[name="choice"]:checked');
                        if (!selected) { alert('Please select an option!'); return; }

                        submitted = true; // Stop timer

                        const val = parseInt(selected.value);
                        const isCorrect = (val === CORRECT_IDX);

                        feedbackBox.classList.remove('hidden');
                        if (isCorrect) {
                            feedbackBox.className = "mb-6 p-4 rounded-lg border animate-pulse bg-green-100 border-green-300";
                            feedbackMsg.className = "font-bold text-lg text-green-800";
                            feedbackMsg.innerText = "✅ Correct Answer!";
                            feedbackDetail.innerText = "";
                            document.getElementById('label-'+val).classList.add('bg-green-50', 'border-green-500');
                            playSound('correct');
                        } else {
                            feedbackBox.className = "mb-6 p-4 rounded-lg border animate-pulse bg-red-100 border-red-300";
                            feedbackMsg.className = "font-bold text-lg text-red-800";
                            feedbackMsg.innerText = "❌ Wrong Answer!";
                            feedbackDetail.className = "text-sm text-red-700 mt-1";
                            feedbackDetail.innerText = "Correct option: " + OPTIONS[CORRECT_IDX - 1];
                            document.getElementById('label-'+val).classList.add('bg-red-50', 'border-red-500');
                            playSound('wrong');
                        }

                        phase = 2;
                        document.querySelectorAll('.option-input').forEach(el => el.disabled = true);
                        
                        if (IS_LAST) {
                            submitBtn.innerText = "Finish Test 🏁";
                            submitBtn.className = "mt-8 w-full bg-green-600 text-white font-bold py-4 rounded-xl hover:bg-green-700 transition shadow-lg";
                        } else {
                            submitBtn.innerText = "Next Question ➡️";
                            submitBtn.className = "mt-8 w-full bg-gray-800 text-white font-bold py-4 rounded-xl hover:bg-gray-900 transition shadow-lg";
                        }
                    } else {
                        // Phase 2 or Exam Mode: Just submit
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
                        playSound('tick');
                    }

                    if (timeLeft <= 0) {
                        clearInterval(countdown);
                        timeoutInput.value = "1";
                        form.submit(); 
                    }
                }, 1000);
            </script>

        <!-- PAGE: RESULT -->
        <?php elseif ($page === 'result'): 
            if (!isset($_SESSION['quiz'])) { echo "<script>window.location='index.php';</script>"; exit; }
            $quiz = $_SESSION['quiz'];
            $total = count($quiz['questions']);
            $acc = $total > 0 ? round(($quiz['correct'] / $total) * 100) : 0;
        ?>
            <div class="max-w-2xl mx-auto bg-white rounded-2xl shadow-2xl overflow-hidden fade-in print:shadow-none">
                <div class="bg-indigo-600 p-8 text-center print:bg-white print:text-black print:border-b">
                    <h2 class="text-3xl font-bold text-white mb-1 print:text-black">Session Result</h2>
                    <p class="text-indigo-200 print:text-gray-600"><?= htmlspecialchars($quiz['user_name']) ?> • <?= date('Y-m-d') ?></p>
                </div>

                <div class="p-8">
                    <div class="grid grid-cols-2 gap-6 mb-8">
                        <div class="text-center p-4 bg-green-50 rounded-xl border border-green-100 print:border-gray-300">
                            <p class="text-sm text-green-600 font-bold uppercase tracking-wide">Score</p>
                            <p class="text-4xl font-bold text-gray-800 mt-1"><?= $quiz['score'] ?> <span class="text-lg text-gray-400">/ <?= $total ?></span></p>
                        </div>
                        <div class="text-center p-4 bg-blue-50 rounded-xl border border-blue-100 print:border-gray-300">
                            <p class="text-sm text-blue-600 font-bold uppercase tracking-wide">Accuracy</p>
                            <p class="text-4xl font-bold text-gray-800 mt-1"><?= $acc ?>%</p>
                        </div>
                    </div>

                    <div class="space-y-3 no-print">
                        <button onclick="window.print()" class="block w-full text-center bg-gray-800 text-white font-bold py-3 rounded-xl hover:bg-gray-900 transition shadow">
                            🖨️ Print / Save as PDF
                        </button>
                        
                        <a href="index.php?page=review" class="block w-full text-center bg-yellow-500 text-white font-bold py-3 rounded-xl hover:bg-yellow-600 transition shadow">
                            📝 Detailed Answer Review
                        </a>
                        
                        <div class="flex gap-3">
                            <a href="index.php?page=end_early" class="flex-1 text-center bg-indigo-600 text-white font-bold py-3 rounded-xl hover:bg-indigo-700 transition shadow">
                                Home
                            </a>
                        </div>
                    </div>
                    
                    <div class="hidden print-only text-center text-sm text-gray-500 mt-8">
                        Generated by MCQ Master Suite on <?= date('Y-m-d H:i') ?>
                    </div>
                </div>
            </div>

        <!-- PAGE: REVIEW -->
        <?php elseif ($page === 'review'): 
            if (!isset($_SESSION['quiz'])) { echo "<script>window.location='index.php';</script>"; exit; }
            $reviews = $_SESSION['quiz']['reviews'];
        ?>
            <div class="max-w-4xl mx-auto fade-in">
                <div class="flex justify-between items-center mb-6 no-print">
                    <h2 class="text-2xl font-bold text-gray-800">📝 Review Answers</h2>
                    <div class="gap-2 flex">
                        <button onclick="window.print()" class="bg-gray-200 px-4 py-2 rounded font-bold hover:bg-gray-300">Print</button>
                        <a href="index.php?page=end_early" class="text-indigo-600 font-medium hover:underline flex items-center">Back to Home</a>
                    </div>
                </div>

                <div class="space-y-6">
                    <?php foreach($reviews as $idx => $item): ?>
                    <div class="bg-white p-6 rounded-xl shadow-sm border-l-4 <?= $item['is_correct'] ? 'border-green-500' : 'border-red-500' ?> break-inside-avoid">
                        <div class="flex justify-between items-start mb-3">
                            <h3 class="text-lg font-semibold text-gray-900"><?= $idx + 1 ?>. <?= htmlspecialchars($item['question']) ?></h3>
                            <?php if($item['is_correct']): ?>
                                <span class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full font-bold border border-green-200">Correct</span>
                            <?php elseif($item['is_timeout']): ?>
                                <span class="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full font-bold border border-gray-200">Time Up</span>
                            <?php else: ?>
                                <span class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded-full font-bold border border-red-200">Wrong</span>
                            <?php endif; ?>
                        </div>

                        <div class="grid grid-cols-2 gap-4 mt-2 text-sm">
                            <div class="p-3 rounded-lg <?= $item['is_correct'] ? 'bg-green-50' : 'bg-red-50' ?>">
                                <p class="text-xs text-gray-500 uppercase font-bold mb-1">Your Answer</p>
                                <p class="font-medium <?= $item['is_correct'] ? 'text-green-700' : 'text-red-700' ?>">
                                    <?= $item['user_choice'] ? htmlspecialchars($item['options'][$item['user_choice'] - 1]) : 'Skipped' ?>
                                </p>
                            </div>
                            <?php if(!$item['is_correct']): ?>
                            <div class="p-3 rounded-lg bg-blue-50">
                                <p class="text-xs text-gray-500 uppercase font-bold mb-1">Correct Answer</p>
                                <p class="font-medium text-blue-700">
                                    <?php 
                                        $cIdx = $item['correct_choice'] - 1;
                                        $cOpt = $item['options'][$cIdx] ?? null;
                                        echo $cOpt ? htmlspecialchars($cOpt) : '<span class="text-red-500">Check Data (Index Error)</span>';
                                    ?>
                                </p>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                    <?php endforeach; ?>
                </div>
            </div>
        <?php endif; ?>

    </div>

    <footer class="text-center p-4 text-gray-400 text-sm no-print">
        MCQ Trainer (PHP Version) &copy; <?= date('Y') ?>
    </footer>
</body>
</html>