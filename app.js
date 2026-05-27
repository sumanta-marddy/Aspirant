let currentMcqs = [];
let seconds = 0;
let timerInterval = null;

const form = document.getElementById("genForm");
if(form){
  form.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd = new FormData(form);
    document.getElementById("questions").innerHTML = "<p>Generating...</p>";
    document.getElementById("testBox").classList.remove("hidden");
    document.getElementById("resultBox").classList.add("hidden");

    const res = await fetch("/generate", {method:"POST", body: fd});
    const data = await res.json();

    if(data.error){
      alert(data.error);
      document.getElementById("questions").innerHTML = "";
      return;
    }

    currentMcqs = data.mcqs;
    renderQuestions();
    startTimer();
  });
}

function renderQuestions(){
  const box = document.getElementById("questions");
  box.innerHTML = "";
  currentMcqs.forEach((q, i)=>{
    const div = document.createElement("div");
    div.className = "q";
    let html = `<b>Q${i+1}. ${q.question}</b>`;
    q.options.forEach(opt=>{
      html += `
      <label class="option">
        <input type="radio" name="q${i}" value="${escapeHtml(opt)}">
        <span>${escapeHtml(opt)}</span>
      </label>`;
    });
    div.innerHTML = html;
    box.appendChild(div);
  });
}

function startTimer(){
  seconds = 0;
  clearInterval(timerInterval);
  timerInterval = setInterval(()=>{
    seconds++;
    const m = String(Math.floor(seconds/60)).padStart(2,"0");
    const s = String(seconds%60).padStart(2,"0");
    document.getElementById("timer").textContent = `${m}:${s}`;
  },1000);
}

async function submitTest(){
  clearInterval(timerInterval);
  const answers = {};
  currentMcqs.forEach((q,i)=>{
    const selected = document.querySelector(`input[name="q${i}"]:checked`);
    answers[i] = selected ? selected.value : "";
  });

  const res = await fetch("/submit", {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({answers})
  });
  const data = await res.json();
  document.getElementById("resultBox").classList.remove("hidden");
  document.getElementById("score").innerHTML = `<h2>Your Score: ${data.score}/${data.total}</h2>`;

  let review = "";
  data.result.forEach((r,i)=>{
    review += `<div class="q">
      <b>Q${i+1}. ${r.question}</b>
      <p>Your answer: <span class="${r.ok?'pass':'fail'}">${r.selected || 'Not answered'}</span></p>
      <p>Correct answer: <b>${r.correct}</b></p>
    </div>`;
  });
  document.getElementById("review").innerHTML = review;
  window.scrollTo({top: document.body.scrollHeight, behavior:"smooth"});
}

function escapeHtml(str){
  return String(str).replace(/[&<>"']/g, s => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[s]));
}
