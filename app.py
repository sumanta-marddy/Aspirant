from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os, re, json, random
from datetime import datetime
from werkzeug.utils import secure_filename

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "history": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text

def extract_pdf_text(path):
    if PyPDF2 is None:
        return ""
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += (page.extract_text() or "") + " "
    return clean_text(text)

def extract_txt_text(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return clean_text(f.read())

def split_sentences(text):
    parts = re.split(r"(?<=[.!?।])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 45]

def important_words(text):
    stop = set("""
    the a an and or but if then is are was were be been being to of in on for with by from this that
    these those as at it its into about which who whom whose what when where why how can could should
    would may might will shall do does did have has had not no yes very more most such also
    है हैं था थी थे और या लेकिन अगर तो यह वह इस उस में पर से को का की के लिए एक भी नहीं
    """.split())
    words = re.findall(r"[A-Za-z\u0900-\u097F]{4,}", text)
    freq = {}
    for w in words:
        lw = w.lower()
        if lw not in stop:
            freq[lw] = freq.get(lw, 0) + 1
    return [w for w, c in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:80]]

def make_question_from_sentence(sentence, all_words):
    words = re.findall(r"[A-Za-z\u0900-\u097F]{4,}", sentence)
    candidates = [w for w in words if w.lower() in all_words and len(w) >= 5]
    if not candidates:
        candidates = [w for w in words if len(w) >= 6]
    if not candidates:
        return None

    answer = random.choice(candidates)
    pattern = re.compile(re.escape(answer), re.IGNORECASE)
    question = pattern.sub("_____", sentence, count=1)

    distractors = [w for w in all_words if w.lower() != answer.lower() and len(w) >= 5]
    random.shuffle(distractors)
    options = [answer] + distractors[:3]
    if len(options) < 4:
        return None
    random.shuffle(options)

    return {
        "question": question,
        "options": options,
        "answer": answer
    }

def generate_mcqs(text, count=10):
    text = clean_text(text)
    sentences = split_sentences(text)
    words = important_words(text)
    random.shuffle(sentences)

    mcqs = []
    used = set()
    for s in sentences:
        q = make_question_from_sentence(s, words)
        if q and q["question"] not in used:
            mcqs.append(q)
            used.add(q["question"])
        if len(mcqs) >= count:
            break
    return mcqs

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])

@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        data = load_data()
        if email in data["users"] and data["users"][email]["password"] == password:
            session["user"] = email
            return redirect(url_for("home"))
        msg = "Wrong email or password"
    return render_template("login.html", msg=msg)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    msg = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        if not name or not email or not password:
            msg = "All fields required"
        else:
            data = load_data()
            if email in data["users"]:
                msg = "Account already exists"
            else:
                data["users"][email] = {"name": name, "password": password, "created": str(datetime.now())}
                data["history"][email] = []
                save_data(data)
                session["user"] = email
                return redirect(url_for("home"))
    return render_template("signup.html", msg=msg)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/generate", methods=["POST"])
def generate():
    if "user" not in session:
        return jsonify({"error": "Login required"}), 401

    raw_text = request.form.get("notes", "")
    count = int(request.form.get("count", 10))
    text = raw_text

    file = request.files.get("file")
    if file and file.filename:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(path)
        if filename.lower().endswith(".pdf"):
            text += " " + extract_pdf_text(path)
        elif filename.lower().endswith(".txt"):
            text += " " + extract_txt_text(path)

    mcqs = generate_mcqs(text, count=count)
    if not mcqs:
        return jsonify({"error": "Text kam hai ya PDF ka text read nahi ho paya. Thoda bada note paste karo."})

    session["last_mcqs"] = mcqs
    return jsonify({"mcqs": mcqs})

@app.route("/submit", methods=["POST"])
def submit():
    if "user" not in session:
        return jsonify({"error": "Login required"}), 401

    answers = request.json.get("answers", {})
    mcqs = session.get("last_mcqs", [])
    score = 0
    result = []
    for i, q in enumerate(mcqs):
        selected = answers.get(str(i), "")
        correct = q["answer"]
        ok = selected.lower().strip() == correct.lower().strip()
        if ok:
            score += 1
        result.append({"question": q["question"], "selected": selected, "correct": correct, "ok": ok})

    data = load_data()
    email = session["user"]
    data.setdefault("history", {}).setdefault(email, []).append({
        "date": str(datetime.now()),
        "score": score,
        "total": len(mcqs)
    })
    save_data(data)

    return jsonify({"score": score, "total": len(mcqs), "result": result})

@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))
    data = load_data()
    items = data.get("history", {}).get(session["user"], [])
    return render_template("history.html", items=list(reversed(items)))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
