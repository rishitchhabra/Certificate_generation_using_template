import json
import os
import uuid

import pymupdf
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import cert, config, db
from . import excel as excel_parser

app = FastAPI(title="School Certificate Download")

app.mount("/static", StaticFiles(directory=os.path.join(config.BASE_DIR, "static")), name="static")

STATIC_DIR = os.path.join(config.BASE_DIR, "static")


@app.on_event("startup")
def startup():
    os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
    db.init_db()


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------
def require_admin(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    username = db.session_username(token)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return username


@app.post("/api/admin/login")
def login(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        token = db.create_session(username)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(
            config.SESSION_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 3600,
        )
        return resp
    raise HTTPException(status_code=401, detail="Invalid username or password.")


@app.post("/api/admin/logout")
def logout(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    db.delete_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp


@app.get("/api/admin/session")
def admin_session(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    username = db.session_username(token)
    return {"authenticated": bool(username)}


# ---------------------------------------------------------------------------
# Admin: certificate sets
# ---------------------------------------------------------------------------
@app.get("/api/admin/sets")
def admin_list_sets(user=Depends(require_admin)):
    return db.list_sets()


@app.post("/api/admin/upload/template")
async def admin_upload_template(file: UploadFile = File(...), user=Depends(require_admin)):
    data = await file.read()
    template_type, ext = cert.detect_template(data)
    if template_type is None:
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid certificate template (PDF or JPG/PNG image).",
        )

    template_id = str(uuid.uuid4())
    path = os.path.join(config.TEMPLATE_DIR, f"{template_id}.{ext}")
    with open(path, "wb") as f:
        f.write(data)

    if template_type == "pdf":
        try:
            doc = pymupdf.open(path)
            doc.close()
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            raise HTTPException(
                status_code=400,
                detail="Please upload a valid certificate template (PDF or JPG/PNG image).",
            )

    return {"template_id": template_id, "template_type": template_type}


@app.get("/api/admin/template/{template_id}/preview")
def admin_template_preview(template_id: str, user=Depends(require_admin)):
    path = _template_file_path(template_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    template_type = _template_type_of(path)
    if template_type == "pdf":
        pix = cert.render_pdf_preview(path)
        return Response(content=pix.tobytes("png"), media_type="image/png")
    return Response(content=cert.render_image_preview(path), media_type="image/png")


def _parse_position(raw: str) -> dict:
    try:
        pos = json.loads(raw)
        x = float(pos["x"])
        y = float(pos["y"])
    except Exception:
        raise HTTPException(status_code=400, detail="Please position the name on the certificate.")
    return {"x": max(0.0, min(x, 1.0)), "y": max(0.0, min(y, 1.0))}


def _template_file_path(template_id: str):
    for ext in ("pdf", "png", "jpg"):
        p = os.path.join(config.TEMPLATE_DIR, f"{template_id}.{ext}")
        if os.path.exists(p):
            return p
    return None


def _template_type_of(path: str) -> str:
    return "pdf" if os.path.splitext(path)[1].lower() == ".pdf" else "image"


def _validate_template_id(template_id: str) -> str:
    if not template_id:
        raise HTTPException(status_code=400, detail="Please upload a certificate template (PDF or JPG/PNG).")
    path = _template_file_path(template_id)
    if path is None:
        raise HTTPException(status_code=400, detail="Please upload a certificate template (PDF or JPG/PNG).")
    return os.path.basename(path)


@app.post("/api/admin/sets")
async def admin_create_set(
    school_name: str = Form(...),
    name: str = Form(...),
    name_position: str = Form(...),
    name_font_size: float = Form(...),
    name_font: str = Form(...),
    name_color: str = Form("#000000"),
    template_id: str = Form(...),
    excel_file: UploadFile = File(...),
    user=Depends(require_admin),
):
    school_name = school_name.strip()
    name = name.strip()
    if not school_name:
        raise HTTPException(status_code=400, detail="Please enter a school name.")
    if not name:
        raise HTTPException(status_code=400, detail="Please enter a certificate name.")

    position = _parse_position(name_position)
    template_path = _validate_template_id(template_id)

    data = await excel_file.read()
    try:
        names = excel_parser.parse_names(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    school_id = db.find_or_create_school(school_name)
    set_id = db.create_set(
        school_id, name, template_path, _template_type_of(template_path),
        json.dumps(position), name_font_size, name_font, name_color,
    )
    db.replace_students(set_id, names)
    return {"id": set_id, "students": len(names)}


@app.put("/api/admin/sets/{set_id}")
async def admin_update_set(
    set_id: int,
    school_name: str = Form(...),
    name: str = Form(...),
    name_position: str = Form(...),
    name_font_size: float = Form(...),
    name_font: str = Form(...),
    name_color: str = Form("#000000"),
    template_id: str = Form(""),
    excel_file: UploadFile = File(None),
    user=Depends(require_admin),
):
    existing = db.get_set(set_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Certificate set not found.")

    school_name = school_name.strip()
    name = name.strip()
    if not school_name:
        raise HTTPException(status_code=400, detail="Please enter a school name.")
    if not name:
        raise HTTPException(status_code=400, detail="Please enter a certificate name.")

    position = _parse_position(name_position)
    template_path = existing["template_path"]
    if template_id:
        template_path = _validate_template_id(template_id)

    school_id = db.find_or_create_school(school_name)
    db.update_set(
        set_id, school_id, name, template_path, _template_type_of(template_path),
        json.dumps(position), name_font_size, name_font, name_color,
    )

    if excel_file is not None:
        data = await excel_file.read()
        try:
            names = excel_parser.parse_names(data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        db.replace_students(set_id, names)

    return {"ok": True, "students": db.count_students(set_id)}


@app.get("/api/admin/sets/{set_id}")
def admin_get_set(set_id: int, user=Depends(require_admin)):
    s = db.get_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Certificate set not found.")
    return s


@app.delete("/api/admin/sets/{set_id}")
def admin_delete_set(set_id: int, user=Depends(require_admin)):
    s = db.get_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Certificate set not found.")
    db.delete_set(set_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Public (student) side
# ---------------------------------------------------------------------------
@app.get("/api/public/schools")
def public_schools():
    return db.list_schools()


@app.get("/api/public/schools/{school_id}/certificates")
def public_school_certificates(school_id: int):
    return db.school_certificates(school_id)


@app.get("/api/public/certificates/{set_id}/students")
def public_certificate_students(set_id: int):
    return db.certificate_students(set_id)


@app.get("/api/public/certificates/{set_id}/image")
def public_certificate_image(set_id: int, student_id: int):
    s = db.get_set(set_id)
    if not s or not s["template_path"]:
        raise HTTPException(status_code=404, detail="This certificate could not be generated. Please try again.")
    student = db.get_student(set_id, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="This certificate could not be generated. Please try again.")
    try:
        position = json.loads(s["name_position"])
    except Exception:
        raise HTTPException(status_code=500, detail="This certificate could not be generated. Please try again.")
    try:
        path = os.path.join(config.TEMPLATE_DIR, s["template_path"])
        if _template_type_of(s["template_path"]) == "pdf":
            pix = cert.render_pdf_certificate(
                path, student["name"], position, s["name_font_size"], s["name_font"],
                s.get("name_color") or "#000000",
            )
            data = pix.tobytes("png")
        else:
            data = cert.render_image_certificate(
                path, student["name"], position, s["name_font_size"], s["name_font"],
                s.get("name_color") or "#000000",
            )
    except Exception:
        raise HTTPException(status_code=500, detail="This certificate could not be generated. Please try again.")
    return Response(content=data, media_type="image/png")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/admin")
def admin_page():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))
