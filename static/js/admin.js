const FONTS = ["helv", "hebo", "tiro", "tibo", "cour"];
const FONT_FAMILIES = {
  helv: "Helvetica, Arial, sans-serif",
  hebo: "Helvetica, Arial, sans-serif",
  tiro: "Times New Roman, Times, serif",
  tibo: "Times New Roman, Times, serif",
  cour: "'Courier New', Courier, monospace",
};
const FONT_WEIGHTS = { helv: 400, hebo: 700, tiro: 400, tibo: 700, cour: 400 };
const REF_PAGE_WIDTH = 612;

let editingId = null; // null = create, otherwise set id
let templateId = ""; // uploaded temp template id
let position = { x: 0.5, y: 0.5 };
let dragging = false;

const $ = (id) => document.getElementById(id);
const msg = $("msg");

function showMessage(text, type) {
  msg.textContent = text;
  msg.className = "message show " + (type || "error");
}
function clearMessage() {
  msg.className = "message";
  msg.textContent = "";
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

// ---------------------------------------------------------------------------
// Login / session
// ---------------------------------------------------------------------------
async function login() {
  clearMessage();
  const username = $("login-user").value.trim();
  const password = $("login-pass").value;
  if (!username || !password) {
    showMessage("Please enter your username and password.", "error");
    return;
  }
  try {
    await api("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    enterDashboard();
  } catch (e) {
    showMessage(e.message, "error");
  }
}

async function logout() {
  try {
    await api("/api/admin/logout", { method: "POST" });
  } catch (e) {}
  location.reload();
}

async function checkSession() {
  try {
    const res = await api("/api/admin/session");
    const data = await res.json();
    if (data.authenticated) enterDashboard();
  } catch (e) {}
}

function enterDashboard() {
  $("login-card").style.display = "none";
  $("dashboard").style.display = "block";
  loadDashboard();
}

async function loadDashboard() {
  try {
    const res = await api("/api/admin/sets");
    renderSets(await res.json());
  } catch (e) {
    showMessage(e.message, "error");
  }
}

function renderSets(sets) {
  const tbody = $("sets-tbody");
  tbody.innerHTML = "";
  $("sets-empty").style.display = sets.length ? "none" : "block";
  sets.forEach((s) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(s.school_name)}</td>
      <td>${escapeHtml(s.name)}</td>
      <td style="text-align:right">${s.student_count}</td>
      <td>
        <div class="row-actions actions">
          <button class="btn btn-sm btn-secondary" onclick="openEdit(${s.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteSet(${s.id})">Delete</button>
        </div>
      </td>`;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

async function deleteSet(id) {
  if (!confirm("Delete this certificate set? This cannot be undone.")) return;
  try {
    await api(`/api/admin/sets/${id}`, { method: "DELETE" });
    loadDashboard();
  } catch (e) {
    showMessage(e.message, "error");
  }
}

// ---------------------------------------------------------------------------
// Add / Edit form
// ---------------------------------------------------------------------------
function openForm() {
  clearMessage();
  editingId = null;
  templateId = "";
  position = { x: 0.5, y: 0.5 };
  $("form-title").textContent = "Add Certificate Set";
  $("f-school").value = "";
  $("f-cert").value = "";
  $("f-excel").value = "";
  $("f-pdf").value = "";
  $("excel-name").textContent = "Tap to choose Excel file";
  $("pdf-name").textContent = "Tap to choose template";
  $("f-fontsize").value = 36;
  $("f-fontsize-val").textContent = "36";
  $("f-font").value = "helv";
  $("f-color").value = "#000000";
  $("f-color-val").textContent = "#000000";
  $("position-section").style.display = "none";
  $("pdf-stage").style.display = "none";
  $("save-btn").disabled = false;
  showForm();
}

async function openEdit(id) {
  clearMessage();
  try {
    const res = await api(`/api/admin/sets/${id}`);
    const s = await res.json();
    editingId = id;
    $("form-title").textContent = "Edit Certificate Set";
    $("f-school").value = s.school_name || "";
    $("f-cert").value = s.name || "";
    $("f-excel").value = "";
    $("f-pdf").value = "";
    $("excel-name").textContent = "Tap to choose Excel file (replace)";
    $("pdf-name").textContent = "Tap to choose template (replace)";
    $("save-btn").disabled = false;

    templateId = (s.template_path || "").replace(/\.[^.]+$/, "");
    position = JSON.parse(s.name_position || "{\"x\":0.5,\"y\":0.5}");
    $("f-fontsize").value = s.name_font_size || 36;
    $("f-fontsize-val").textContent = $("f-fontsize").value;
    $("f-font").value = s.name_font || "helv";
    $("f-color").value = s.name_color || "#000000";
    $("f-color-val").textContent = $("f-color").value;

    showForm();
    if (templateId) {
      $("position-section").style.display = "block";
      $("pdf-stage").style.display = "block";
      $("pdf-preview").src = `/api/admin/template/${templateId}/preview`;
      updatePlaceholder();
    }
  } catch (e) {
    showMessage(e.message, "error");
  }
}

function showForm() {
  $("dashboard").style.display = "none";
  $("form-card").style.display = "block";
}

function closeForm() {
  clearMessage();
  $("form-card").style.display = "none";
  $("dashboard").style.display = "block";
  loadDashboard();
}

async function onTemplateSelect(input) {
  const file = input.files[0];
  if (!file) return;
  const ok = file.type === "application/pdf" || file.type === "image/jpeg" || file.type === "image/png";
  if (!ok) {
    showMessage("Please upload a valid certificate template (PDF or JPG/PNG image).", "error");
    return;
  }
  clearMessage();
  $("pdf-name").textContent = file.name;
  $("position-section").style.display = "none";
  $("pdf-stage").style.display = "none";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await api("/api/admin/upload/template", { method: "POST", body: fd });
    const data = await res.json();
    templateId = data.template_id;
    position = { x: 0.5, y: 0.5 };
    $("position-section").style.display = "block";
    $("pdf-stage").style.display = "block";
    $("pdf-preview").src = `/api/admin/template/${templateId}/preview`;
    updatePlaceholder();
  } catch (e) {
    showMessage(e.message, "error");
  }
}

function placeMarker() {
  $("pos-marker").style.left = position.x * 100 + "%";
  $("pos-marker").style.top = position.y * 100 + "%";
  $("pos-marker").style.display = "block";
}

function updatePlaceholder() {
  const marker = $("pos-marker");
  const stage = $("pdf-stage");
  const fontId = $("f-font").value || "helv";
  const size = parseFloat($("f-fontsize").value) || 36;
  const color = $("f-color").value || "#000000";
  const displayPx = (size / REF_PAGE_WIDTH) * stage.clientWidth;
  marker.style.fontSize = displayPx + "px";
  marker.style.fontFamily = FONT_FAMILIES[fontId] || FONT_FAMILIES.helv;
  marker.style.fontWeight = FONT_WEIGHTS[fontId] || 400;
  marker.style.color = color;
  placeMarker();
}

function setPositionFromEvent(e) {
  const stage = $("pdf-stage");
  const rect = stage.getBoundingClientRect();
  let cx, cy;
  if (e.touches && e.touches[0]) {
    cx = e.touches[0].clientX;
    cy = e.touches[0].clientY;
  } else if (e.changedTouches && e.changedTouches[0]) {
    cx = e.changedTouches[0].clientX;
    cy = e.changedTouches[0].clientY;
  } else {
    cx = e.clientX;
    cy = e.clientY;
  }
  let nx = (cx - rect.left) / rect.width;
  let ny = (cy - rect.top) / rect.height;
  nx = Math.max(0, Math.min(1, nx));
  ny = Math.max(0, Math.min(1, ny));
  position = { x: nx, y: ny };
  placeMarker();
}

function setupPositioning() {
  const stage = $("pdf-stage");
  const marker = $("pos-marker");

  stage.addEventListener("click", (e) => {
    if (dragging) return;
    setPositionFromEvent(e);
  });

  marker.addEventListener("pointerdown", (e) => {
    dragging = true;
    marker.setPointerCapture(e.pointerId);
    e.preventDefault();
  });

  marker.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    setPositionFromEvent(e);
  });

  marker.addEventListener("pointerup", (e) => {
    dragging = false;
    marker.releasePointerCapture(e.pointerId);
  });

  marker.addEventListener("touchstart", (e) => {
    dragging = true;
    e.preventDefault();
  });
  marker.addEventListener("touchmove", (e) => {
    if (!dragging) return;
    setPositionFromEvent(e);
  });
  marker.addEventListener("touchend", () => {
    dragging = false;
  });
}

async function saveSet() {
  clearMessage();
  const schoolName = $("f-school").value.trim();
  const certName = $("f-cert").value.trim();
  const excelFile = $("f-excel").files[0];
  const pdfFile = $("f-pdf").files[0];

  if (!schoolName) return showMessage("Please enter a school name.", "error");
  if (!certName) return showMessage("Please enter a certificate name.", "error");

  if (!editingId) {
    if (!excelFile) return showMessage("Please upload the student names Excel file.", "error");
    if (!templateId) return showMessage("Please upload a certificate template (PDF or JPG/PNG).", "error");
  }

  $("save-btn").disabled = true;

  let finalTemplateId = templateId;
  if (pdfFile) {
    try {
      const fd = new FormData();
      fd.append("file", pdfFile);
      const res = await api("/api/admin/upload/template", { method: "POST", body: fd });
      finalTemplateId = (await res.json()).template_id;
    } catch (e) {
      $("save-btn").disabled = false;
      return showMessage(e.message, "error");
    }
  }

  const fd = new FormData();
  fd.append("school_name", schoolName);
  fd.append("name", certName);
  fd.append("name_position", JSON.stringify(position));
  fd.append("name_font_size", $("f-fontsize").value);
  fd.append("name_font", $("f-font").value);
  fd.append("name_color", $("f-color").value);
  fd.append("template_id", finalTemplateId);
  if (excelFile) fd.append("excel_file", excelFile);

  try {
    if (editingId) {
      await api(`/api/admin/sets/${editingId}`, { method: "PUT", body: fd });
      showMessage("Certificate set updated.", "success");
    } else {
      await api("/api/admin/sets", { method: "POST", body: fd });
      showMessage("Certificate set created.", "success");
    }
    setTimeout(closeForm, 700);
  } catch (e) {
    $("save-btn").disabled = false;
    showMessage(e.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("login-btn").addEventListener("click", login);
  $("login-pass").addEventListener("keydown", (e) => {
    if (e.key === "Enter") login();
  });
  $("f-pdf").addEventListener("change", (e) => onTemplateSelect(e.target));
  $("f-excel").addEventListener("change", (e) => {
    const f = e.target.files[0];
    $("excel-name").textContent = f ? f.name : "Tap to choose Excel file";
  });
  $("f-fontsize").addEventListener("input", (e) => {
    $("f-fontsize-val").textContent = e.target.value;
    updatePlaceholder();
  });
  $("f-font").addEventListener("change", updatePlaceholder);
  $("f-color").addEventListener("input", (e) => {
    $("f-color-val").textContent = e.target.value;
    updatePlaceholder();
  });
  $("pdf-preview").addEventListener("load", updatePlaceholder);
  setupPositioning();
  checkSession();
});
