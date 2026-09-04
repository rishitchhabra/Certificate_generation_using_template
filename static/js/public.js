let state = {
  schools: [],
  certificates: [],
  students: [],
  selectedSchool: null,
  selectedCert: null,
  selectedStudent: null,
  imageBlob: null,
};

const $ = (id) => document.getElementById(id);
const msg = $("message");

function showMessage(text, type) {
  msg.textContent = text;
  msg.className = "message show " + type;
}

function clearMessage() {
  msg.className = "message";
  msg.textContent = "";
}

function showStep(id) {
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  $(id).classList.add("active");
  updateSteps(id);
}

function updateSteps(id) {
  const pills = document.querySelectorAll(".steps .step-pill");
  pills.forEach((p) => {
    const n = parseInt(p.dataset.step, 10);
    p.classList.remove("active", "done");
    if (id === "step-school" && n === 1) p.classList.add("active");
    if (id === "step-cert" && n === 2) p.classList.add("active");
    if (id === "step-name" && n === 2) p.classList.add("active");
    if (id === "step-certificate" && n === 3) p.classList.add("active");
    if (
      (id === "step-cert" || id === "step-name") && n === 1
    ) p.classList.add("done");
    if (id === "step-certificate" && n <= 2) p.classList.add("done");
  });
}

function goBack() {
  if (state.selectedStudent) {
    state.selectedStudent = null;
    state.imageBlob = null;
    showStep("step-name");
  } else if (state.selectedCert) {
    state.selectedCert = null;
    if (state.certificates.length > 1) {
      renderCerts();
      showStep("step-cert");
    } else {
      state.selectedSchool = null;
      renderSchools();
      showStep("step-school");
    }
  } else {
    state.selectedSchool = null;
    renderSchools();
    showStep("step-school");
  }
}

async function api(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const data = await res.json();
      if (data && data.detail) detail = data.detail;
    } catch (e) {}
    throw new Error(detail);
  }
  return res;
}

function renderSchools() {
  const list = $("school-list");
  list.innerHTML = "";
  const q = $("school-search").value.trim().toLowerCase();
  const filtered = state.schools.filter((s) => s.name.toLowerCase().includes(q));
  $("school-empty").style.display = filtered.length ? "none" : "block";
  filtered.forEach((s) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = s.name;
    btn.onclick = () => selectSchool(s);
    li.appendChild(btn);
    list.appendChild(li);
  });
}

function selectSchool(school) {
  state.selectedSchool = school;
  state.selectedCert = null;
  $("school-search").value = "";
  loadCertificates(school.id);
}

async function loadCertificates(schoolId) {
  try {
    const res = await api(`/api/public/schools/${schoolId}/certificates`);
    state.certificates = await res.json();
    if (state.certificates.length === 1) {
      selectCert(state.certificates[0]);
    } else if (state.certificates.length > 1) {
      renderCerts();
      showStep("step-cert");
    } else {
      showMessage("No certificates are available for this school.", "error");
    }
  } catch (e) {
    showMessage(e.message, "error");
  }
}

function renderCerts() {
  const list = $("cert-list");
  list.innerHTML = "";
  state.certificates.forEach((c) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = c.name;
    btn.onclick = () => selectCert(c);
    li.appendChild(btn);
    list.appendChild(li);
  });
}

function selectCert(cert) {
  state.selectedCert = cert;
  state.selectedStudent = null;
  loadStudents(cert.id);
}

async function loadStudents(certId) {
  try {
    const res = await api(`/api/public/certificates/${certId}/students`);
    state.students = await res.json();
    renderNames();
    showStep("step-name");
  } catch (e) {
    showMessage(e.message, "error");
  }
}

function renderNames() {
  const list = $("name-list");
  list.innerHTML = "";
  const q = $("name-search").value.trim().toLowerCase();
  const filtered = state.students.filter((s) => s.name.toLowerCase().includes(q));
  $("name-empty").style.display = filtered.length ? "none" : "block";
  filtered.forEach((s) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.textContent = s.name;
    btn.onclick = () => selectStudent(s);
    li.appendChild(btn);
    list.appendChild(li);
  });
}

function selectStudent(student) {
  state.selectedStudent = student;
  $("name-search").value = "";
  generateCertificate(student);
}

async function generateCertificate(student) {
  showStep("step-certificate");
  $("preview-loading").style.display = "block";
  $("preview-img").style.display = "none";
  $("download-btn").disabled = true;
  clearMessage();
  try {
    const res = await api(
      `/api/public/certificates/${state.selectedCert.id}/image?student_id=${student.id}`
    );
    const blob = await res.blob();
    state.imageBlob = blob;
    const url = URL.createObjectURL(blob);
    const img = $("preview-img");
    img.src = url;
    img.style.display = "block";
    $("preview-loading").style.display = "none";
    $("download-btn").disabled = false;
    partyPop();
  } catch (e) {
    $("preview-loading").style.display = "none";
    showMessage(e.message, "error");
  }
}

function downloadCertificate() {
  if (!state.imageBlob || !state.selectedStudent) return;
  const name = state.selectedStudent.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(state.imageBlob);
  a.download = `certificate-${name || "student"}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function partyPop() {
  const canvas = document.createElement("canvas");
  canvas.style.cssText =
    "position:fixed;inset:0;pointer-events:none;z-index:9999;";
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const DPR = window.devicePixelRatio || 1;
  const w = () => window.innerWidth;
  const h = () => window.innerHeight;
  const resize = () => {
    canvas.width = w() * DPR;
    canvas.height = h() * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  };
  resize();
  window.addEventListener("resize", resize);

  const colors = ["#6366f1", "#a855f7", "#ec4899", "#f59e0b", "#10b981", "#3b82f6"];
  const particles = [];
  const count = 180;
  const cx = w() / 2;
  const cy = h() / 2;
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 4 + Math.random() * 14;
    particles.push({
      x: cx + (Math.random() - 0.5) * 100,
      y: cy + (Math.random() - 0.5) * 40,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 4,
      size: 6 + Math.random() * 9,
      rot: Math.random() * Math.PI * 2,
      vrot: (Math.random() - 0.5) * 0.4,
      color: colors[Math.floor(Math.random() * colors.length)],
      shape: Math.random() > 0.5 ? "rect" : "circle",
      life: 0,
      ttl: 100 + Math.random() * 60,
    });
  }

  function tick() {
    ctx.clearRect(0, 0, w(), h());
    let alive = 0;
    for (const p of particles) {
      p.life++;
      if (p.life > p.ttl) continue;
      alive++;
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.35;
      p.vx *= 0.99;
      p.rot += p.vrot;
      const a = Math.max(0, 1 - p.life / p.ttl);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      if (p.shape === "rect") {
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      } else {
        ctx.beginPath();
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    if (alive > 0) {
      requestAnimationFrame(tick);
    } else {
      canvas.remove();
      window.removeEventListener("resize", resize);
    }
  }
  requestAnimationFrame(tick);
}

document.addEventListener("DOMContentLoaded", async () => {
  $("school-search").addEventListener("input", renderSchools);
  $("name-search").addEventListener("input", renderNames);
  try {
    const res = await api("/api/public/schools");
    state.schools = await res.json();
    renderSchools();
    showStep("step-school");
  } catch (e) {
    showMessage(e.message, "error");
  }
});
