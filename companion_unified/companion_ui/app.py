from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from companion_ui.io import read_json_list, atomic_write_json
from companion_ui import auth
from companion.config import load_config
from companion.queues.send_queue import SendEmailSpec, spec_hash as send_spec_hash
from companion.queues.calendar_queue import CreateEventSpec, spec_hash as cal_spec_hash
from companion.queues.moltbook_queue import CreatePostSpec, ReplyPostSpec, spec_hash_post, spec_hash_reply
from companion_exec.tokens_hmac import mint as mint_hmac
from companion.llm.router import build_llm

ROOT = Path(__file__).resolve().parents[1]
ART = Path(os.getenv("COMPANION_ARTIFACTS_DIR", str(ROOT / "artifacts")))
SEND_Q = ART / "messages" / "send_queue.json"
CAL_Q = ART / "calendar" / "event_queue.json"
MOLT_Q = ART / "moltbook" / "post_queue.json"
LEDGER = ART / "ledger.jsonl"
STATE = ART / ".control_state.json"
CHAT_LOG = ART / "chat" / "chat.json"
CHAT_SYS = ART / "chat" / "system.txt"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app = FastAPI()


def _get_secret() -> bytes:
    cfg = load_config()
    s = cfg.exec_secret
    if not s:
        raise RuntimeError("Set COMPANION_EXEC_SECRET")
    return s.encode("utf-8")


def _apply_token(queue_path: Path, qid: str, token: str, *, approved_by: str) -> bool:
    items = read_json_list(queue_path)
    for it in items:
        if it.get("qid") == qid and it.get("status") == "pending":
            it["approval_token"] = token
            it["approved_by"] = approved_by
            it["approved_at"] = datetime.utcnow().isoformat()
            atomic_write_json(queue_path, items)
            return True
    return False


def _load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _process_status(name: str) -> Dict[str, Any]:
    state = _load_state().get(name) or {}
    pid = int(state.get("pid") or 0)
    running = _pid_running(pid)
    if not running and pid:
        state["pid"] = 0
    return {
        "pid": pid if running else 0,
        "running": running,
        "started_at": state.get("started_at"),
        "cmd": state.get("cmd"),
    }


def _start_process(name: str, cmd: List[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    state = _load_state()
    cur = state.get(name) or {}
    pid = int(cur.get("pid") or 0)
    if pid and _pid_running(pid):
        return {"ok": False, "error": f"{name} already running"}
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=full_env, start_new_session=True)
    state[name] = {
        "pid": proc.pid,
        "started_at": datetime.utcnow().isoformat(),
        "cmd": " ".join(cmd),
    }
    _save_state(state)
    return {"ok": True, "pid": proc.pid}


def _stop_process(name: str) -> Dict[str, Any]:
    state = _load_state()
    cur = state.get(name) or {}
    pid = int(cur.get("pid") or 0)
    if not pid or not _pid_running(pid):
        cur["pid"] = 0
        state[name] = cur
        _save_state(state)
        return {"ok": False, "error": f"{name} not running"}
    try:
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            return {"ok": False, "error": str(e)}
    cur["pid"] = 0
    state[name] = cur
    _save_state(state)
    return {"ok": True}


def _safe_artifacts_path(rel: str) -> Path:
    base = ART.resolve()
    target = (base / rel).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="invalid path")
    return target


def _load_chat() -> List[Dict[str, Any]]:
    return read_json_list(CHAT_LOG)


def _save_chat(items: List[Dict[str, Any]]) -> None:
    atomic_write_json(CHAT_LOG, items)


def _append_chat(role: str, content: str) -> None:
    items = _load_chat()
    items.append({"role": role, "content": content, "ts": datetime.utcnow().isoformat()})
    _save_chat(items)


def _get_system_prompt() -> str:
    try:
        return CHAT_SYS.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _set_system_prompt(text: str) -> None:
    CHAT_SYS.parent.mkdir(parents=True, exist_ok=True)
    CHAT_SYS.write_text(text.strip(), encoding="utf-8")


def _read_ledger_tail(max_lines: int = 200) -> List[Dict[str, Any]]:
    try:
        lines = LEDGER.read_text(encoding="utf-8").splitlines()[-max_lines:]
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line})
    return out


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ("/login", "/logout", "/auth/login", "/auth/callback"):
        return await call_next(request)
    if not auth.is_auth_enabled():
        return await call_next(request)
    user = auth.get_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": os.getenv("COMPANION_AUTH_MODE", "none")})


@app.post("/login")
def login(password: str = Form("")):
    mode = os.getenv("COMPANION_AUTH_MODE", "none").strip().lower()
    if mode == "password":
        expected = os.getenv("COMPANION_AUTH_PASSWORD", "")
        if not expected or password != expected:
            return RedirectResponse(url="/login", status_code=303)
        resp = RedirectResponse(url="/", status_code=303)
        auth.set_password_session(resp)
        return resp
    if mode == "oauth":
        return RedirectResponse(url="/auth/login", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    auth.clear_session(resp)
    return resp


@app.get("/auth/login")
def oauth_login(request: Request):
    redirect_uri = str(request.url_for("oauth_callback"))
    url, state = auth.oauth_login_url(redirect_uri)
    resp = RedirectResponse(url=url, status_code=303)
    resp.set_cookie("companion_oauth_state", auth.encode_state(state), httponly=True, samesite="lax")
    return resp


@app.get("/auth/callback")
def oauth_callback(request: Request, code: str = "", state: str = ""):
    stored = auth.decode_state(request.cookies.get("companion_oauth_state", ""))
    if not stored or stored != state:
        return RedirectResponse(url="/login", status_code=303)
    token = auth.oauth_exchange_code(code, str(request.url_for("oauth_callback")))
    access_token = token.get("access_token") or token.get("accessToken")
    if not access_token:
        return RedirectResponse(url="/login", status_code=303)
    info = auth.oauth_userinfo(access_token)
    email = (info.get("email") or info.get("preferred_username") or info.get("login") or info.get("user") or "")
    if not email or not auth.oauth_email_allowed(email):
        return RedirectResponse(url="/login", status_code=303)
    resp = RedirectResponse(url="/", status_code=303)
    auth.set_oauth_session(resp, user=email, email=email)
    return resp


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    send_items = read_json_list(SEND_Q)
    cal_items = read_json_list(CAL_Q)
    molt_items = read_json_list(MOLT_Q)
    ledger_items = _read_ledger_tail(200)
    status_kernel = _process_status("kernel")
    status_exec = _process_status("executor")
    return templates.TemplateResponse(
        "control.html",
        {
            "request": request,
            "send": send_items,
            "cal": cal_items,
            "molt": molt_items,
            "ledger": ledger_items,
            "kernel": status_kernel,
            "executor": status_exec,
            "artifacts_dir": str(ART),
        },
    )


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    messages = _load_chat()
    system_prompt = _get_system_prompt()
    provider = os.getenv("COMPANION_LLM_PROVIDER", "ollama")
    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    if provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if provider == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    base_url = ""
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    elif provider == "openai":
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
    elif provider == "anthropic":
        base_url = os.getenv("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com")
    return templates.TemplateResponse(
        "chat.html",
        {"request": request, "messages": messages, "system_prompt": system_prompt, "provider": provider, "model": model, "base_url": base_url},
    )


@app.post("/chat/send")
def chat_send(message: str = Form(""), system_prompt: str = Form(""), provider: str = Form(""), model: str = Form(""), base_url: str = Form("")):
    msg = (message or "").strip()
    if system_prompt.strip():
        _set_system_prompt(system_prompt)
    if not msg:
        return RedirectResponse("/chat", status_code=303)

    _append_chat("user", msg)
    llm = build_llm(provider=provider or None, model=model or None, base_url=base_url or None)
    sys_prompt = _get_system_prompt() or "You are a helpful companion."
    if not llm:
        _append_chat("assistant", "LLM not configured. Set COMPANION_LLM_PROVIDER and credentials.")
        return RedirectResponse("/chat", status_code=303)

    history = _load_chat()[-20:]
    convo_lines = []
    for m in history:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user":
            convo_lines.append(f"User: {content}")
        elif role == "assistant":
            convo_lines.append(f"Assistant: {content}")
    prompt = "Conversation so far:\n" + "\n".join(convo_lines) + "\n\nReply to the last user message."
    resp = llm.complete(system=sys_prompt, user=prompt, json_mode=False)
    reply = (resp.text or "").strip() if resp else ""
    _append_chat("assistant", reply or "(no response)")
    return RedirectResponse("/chat", status_code=303)


@app.post("/chat/stream")
def chat_stream(message: str = Form(""), system_prompt: str = Form(""), provider: str = Form(""), model: str = Form(""), base_url: str = Form("")):
    msg = (message or "").strip()
    if system_prompt.strip():
        _set_system_prompt(system_prompt)
    if not msg:
        return StreamingResponse(iter(()), media_type="text/plain")

    _append_chat("user", msg)
    llm = build_llm(provider=provider or None, model=model or None, base_url=base_url or None)
    sys_prompt = _get_system_prompt() or "You are a helpful companion."
    if not llm:
        _append_chat("assistant", "LLM not configured. Set COMPANION_LLM_PROVIDER and credentials.")
        return StreamingResponse(iter(()), media_type="text/plain")

    history = _load_chat()[-20:]
    convo_lines = []
    for m in history:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user":
            convo_lines.append(f"User: {content}")
        elif role == "assistant":
            convo_lines.append(f"Assistant: {content}")
    prompt = "Conversation so far:\n" + "\n".join(convo_lines) + "\n\nReply to the last user message."

    def _gen():
        buf: List[str] = []
        try:
            if hasattr(llm, "stream"):
                for chunk in llm.stream(system=sys_prompt, user=prompt):
                    if not chunk:
                        continue
                    buf.append(chunk)
                    yield chunk
            else:
                resp = llm.complete(system=sys_prompt, user=prompt, json_mode=False)
                text = (resp.text or "") if resp else ""
                for i in range(0, len(text), 160):
                    part = text[i:i+160]
                    buf.append(part)
                    yield part
        finally:
            full = "".join(buf).strip()
            _append_chat("assistant", full or "(no response)")

    return StreamingResponse(_gen(), media_type="text/plain")


@app.post("/chat/clear")
def chat_clear():
    _save_chat([])
    return RedirectResponse("/chat", status_code=303)


@app.post("/approve/send")
def approve_send(qid: str = Form(...), ttl: int = Form(600)):
    secret = _get_secret()
    items = read_json_list(SEND_Q)
    target = next((it for it in items if it.get("qid") == qid), None)
    if not target:
        return RedirectResponse("/", status_code=303)
    token = mint_hmac(secret, token_type="send_email", ttl_s=int(ttl), bind={"qid": qid, "spec_hash": target.get("spec_hash")})
    _apply_token(SEND_Q, qid, token, approved_by="manual")
    return RedirectResponse("/", status_code=303)


@app.post("/approve/event")
def approve_event(qid: str = Form(...), ttl: int = Form(600)):
    secret = _get_secret()
    items = read_json_list(CAL_Q)
    target = next((it for it in items if it.get("qid") == qid), None)
    if not target:
        return RedirectResponse("/", status_code=303)
    token = mint_hmac(secret, token_type="create_event", ttl_s=int(ttl), bind={"qid": qid, "spec_hash": target.get("spec_hash")})
    _apply_token(CAL_Q, qid, token, approved_by="manual")
    return RedirectResponse("/", status_code=303)


@app.post("/approve/moltbook_post")
def approve_moltbook_post(qid: str = Form(...), ttl: int = Form(600)):
    secret = _get_secret()
    items = read_json_list(MOLT_Q)
    target = next((it for it in items if it.get("qid") == qid), None)
    if not target:
        return RedirectResponse("/", status_code=303)
    token = mint_hmac(secret, token_type="moltbook_post", ttl_s=int(ttl), bind={"qid": qid, "spec_hash": target.get("spec_hash")})
    _apply_token(MOLT_Q, qid, token, approved_by="manual")
    return RedirectResponse("/", status_code=303)


@app.post("/approve/moltbook_reply")
def approve_moltbook_reply(qid: str = Form(...), ttl: int = Form(600)):
    secret = _get_secret()
    items = read_json_list(MOLT_Q)
    target = next((it for it in items if it.get("qid") == qid), None)
    if not target:
        return RedirectResponse("/", status_code=303)
    token = mint_hmac(secret, token_type="moltbook_reply", ttl_s=int(ttl), bind={"qid": qid, "spec_hash": target.get("spec_hash")})
    _apply_token(MOLT_Q, qid, token, approved_by="manual")
    return RedirectResponse("/", status_code=303)


@app.post("/control/kernel/start")
def start_kernel(ticks: int = Form(5), use_google: str = Form("off"), repos: str = Form("")):
    args = [sys.executable, "-m", "companion.main", "--ticks", str(ticks), "--artifacts", str(ART)]
    if use_google.lower() in ("1", "true", "on", "yes"):
        args.append("--use_google")
    repo_list = [r.strip() for r in repos.split(",") if r.strip()]
    if repo_list:
        args.append("--repos")
        args.extend(repo_list)
    res = _start_process("kernel", args, env={"COMPANION_ARTIFACTS_DIR": str(ART)})
    return RedirectResponse("/", status_code=303)


@app.post("/control/kernel/stop")
def stop_kernel():
    _stop_process("kernel")
    return RedirectResponse("/", status_code=303)


@app.post("/control/executor/start")
def start_executor():
    args = [sys.executable, "-m", "companion_exec.daemon"]
    _start_process("executor", args, env={"COMPANION_ARTIFACTS_DIR": str(ART)})
    return RedirectResponse("/", status_code=303)


@app.post("/control/executor/stop")
def stop_executor():
    _stop_process("executor")
    return RedirectResponse("/", status_code=303)


@app.get("/queue/send/edit", response_class=HTMLResponse)
def edit_send(request: Request, qid: str):
    items = read_json_list(SEND_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    body = ""
    path = item.get("spec", {}).get("body_md_path")
    if path:
        try:
            body = Path(path).read_text(encoding="utf-8")
        except Exception:
            body = ""
    return templates.TemplateResponse("edit_send.html", {"request": request, "item": item, "body": body})


@app.post("/queue/send/update")
def update_send(qid: str = Form(...), to: str = Form(""), subject: str = Form(""), body: str = Form("")):
    items = read_json_list(SEND_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    spec = item.get("spec") or {}
    spec["to"] = to.strip()
    spec["subject"] = subject.strip()
    body_path = spec.get("body_md_path")
    if body_path:
        try:
            Path(body_path).write_text(body, encoding="utf-8")
        except Exception:
            pass
    new_spec = SendEmailSpec(
        qid=spec.get("qid", qid),
        thread_id=spec.get("thread_id", ""),
        to=spec.get("to", ""),
        subject=spec.get("subject", ""),
        body_md_path=spec.get("body_md_path", ""),
        reply_to_message_id=spec.get("reply_to_message_id"),
    )
    item["spec"] = {
        "qid": new_spec.qid,
        "thread_id": new_spec.thread_id,
        "to": new_spec.to,
        "subject": new_spec.subject,
        "body_md_path": new_spec.body_md_path,
        "reply_to_message_id": new_spec.reply_to_message_id,
    }
    item["spec_hash"] = send_spec_hash(new_spec)
    item["approval_token"] = None
    item["approved_by"] = None
    item["approved_at"] = None
    item["status"] = "pending"
    atomic_write_json(SEND_Q, items)
    return RedirectResponse("/", status_code=303)


@app.get("/queue/event/edit", response_class=HTMLResponse)
def edit_event(request: Request, qid: str):
    items = read_json_list(CAL_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    body = ""
    path = item.get("spec", {}).get("description_md_path")
    if path:
        try:
            body = Path(path).read_text(encoding="utf-8")
        except Exception:
            body = ""
    return templates.TemplateResponse("edit_event.html", {"request": request, "item": item, "body": body})


@app.post("/queue/event/update")
def update_event(
    qid: str = Form(...),
    title: str = Form(""),
    start_iso: str = Form(""),
    end_iso: str = Form(""),
    attendees: str = Form(""),
    description: str = Form(""),
):
    items = read_json_list(CAL_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    spec = item.get("spec") or {}
    spec["title"] = title.strip()
    spec["start_iso"] = start_iso.strip()
    spec["end_iso"] = end_iso.strip()
    spec["attendees"] = [a.strip() for a in attendees.split(",") if a.strip()]
    desc_path = spec.get("description_md_path")
    if desc_path:
        try:
            Path(desc_path).write_text(description, encoding="utf-8")
        except Exception:
            pass
    new_spec = CreateEventSpec(
        qid=spec.get("qid", qid),
        calendar_id=spec.get("calendar_id", "primary"),
        title=spec.get("title", ""),
        start_iso=spec.get("start_iso", ""),
        end_iso=spec.get("end_iso", ""),
        description_md_path=spec.get("description_md_path", ""),
        attendees=list(spec.get("attendees", []) or []),
    )
    item["spec"] = {
        "qid": new_spec.qid,
        "calendar_id": new_spec.calendar_id,
        "title": new_spec.title,
        "start_iso": new_spec.start_iso,
        "end_iso": new_spec.end_iso,
        "description_md_path": new_spec.description_md_path,
        "attendees": new_spec.attendees,
    }
    item["spec_hash"] = cal_spec_hash(new_spec)
    item["approval_token"] = None
    item["approved_by"] = None
    item["approved_at"] = None
    item["status"] = "pending"
    atomic_write_json(CAL_Q, items)
    return RedirectResponse("/", status_code=303)


@app.get("/queue/moltbook/edit", response_class=HTMLResponse)
def edit_moltbook(request: Request, qid: str):
    items = read_json_list(MOLT_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    body = ""
    path = item.get("spec", {}).get("body_md_path")
    if path:
        try:
            body = Path(path).read_text(encoding="utf-8")
        except Exception:
            body = ""
    return templates.TemplateResponse("edit_moltbook.html", {"request": request, "item": item, "body": body})


@app.post("/queue/moltbook/update")
def update_moltbook(qid: str = Form(...), title: str = Form(""), post_id: str = Form(""), body: str = Form("")):
    items = read_json_list(MOLT_Q)
    item = next((it for it in items if it.get("qid") == qid), None)
    if not item:
        return RedirectResponse("/", status_code=303)
    spec = item.get("spec") or {}
    if spec.get("body_md_path"):
        try:
            Path(spec["body_md_path"]).write_text(body, encoding="utf-8")
        except Exception:
            pass
    if item.get("action") == "create_post":
        spec["title"] = title.strip()
        new_spec = CreatePostSpec(
            qid=spec.get("qid", qid),
            title=spec.get("title", ""),
            body_md_path=spec.get("body_md_path", ""),
        )
        item["spec"] = {"qid": new_spec.qid, "title": new_spec.title, "body_md_path": new_spec.body_md_path}
        item["spec_hash"] = spec_hash_post(new_spec)
    else:
        spec["post_id"] = post_id.strip()
        new_spec = ReplyPostSpec(
            qid=spec.get("qid", qid),
            post_id=spec.get("post_id", ""),
            body_md_path=spec.get("body_md_path", ""),
        )
        item["spec"] = {"qid": new_spec.qid, "post_id": new_spec.post_id, "body_md_path": new_spec.body_md_path}
        item["spec_hash"] = spec_hash_reply(new_spec)
    item["approval_token"] = None
    item["approved_by"] = None
    item["approved_at"] = None
    item["status"] = "pending"
    atomic_write_json(MOLT_Q, items)
    return RedirectResponse("/", status_code=303)


@app.get("/artifacts", response_class=HTMLResponse)
def artifacts_page(request: Request, path: str = ""):
    p = _safe_artifacts_path(path) if path else ART
    if p.is_file():
        return RedirectResponse(url=f"/artifact?path={urllib.parse.quote(path)}", status_code=303)
    entries = []
    try:
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            rel = str(child.relative_to(ART))
            entries.append({"name": child.name, "is_dir": child.is_dir(), "rel": rel})
    except Exception:
        entries = []
    return templates.TemplateResponse("artifacts.html", {"request": request, "path": path, "entries": entries})


@app.get("/artifact", response_class=HTMLResponse)
def artifact_view(request: Request, path: str):
    p = _safe_artifacts_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="not found")
    text = ""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        text = "(binary or unreadable)"
    return templates.TemplateResponse("artifact_view.html", {"request": request, "path": path, "text": text})
