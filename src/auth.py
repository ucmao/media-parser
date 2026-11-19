import hashlib
import hmac
import re
import secrets
import string
from datetime import datetime, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from src.db import get_db, setting, utcnow


bp = Blueprint("auth", __name__, url_prefix="/auth")


from datetime import datetime, timedelta, timezone


def hash_api_key(raw_key):
    return hashlib.sha256(b"mp_api_key_salt_v1:" + raw_key.encode()).hexdigest()


def legacy_hash_api_key(raw_key):
    try:
        pepper = current_app.config["SECRET_KEY"].encode()
        return hmac.new(pepper, raw_key.encode(), hashlib.sha256).hexdigest()
    except Exception:
        return ""


def generate_api_key(length=24):
    alphabet = string.ascii_letters + string.digits
    return "mp-" + "".join(secrets.choice(alphabet) for _ in range(length))


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return session["csrf_token"]


def validate_csrf():
    supplied = request.form.get("csrf_token")
    expected = session.get("csrf_token")
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def auth_rate_limited(action, username=""):
    """限制管理员初始化、注册和登录尝试，避免批量注册与密码爆破。"""
    from src.api.access import consume_rate_limits, get_client_ip

    client_ip = get_client_ip()
    if action == "setup":
        limits = [(f"auth:setup:ip:{client_ip}", 10, 900)]
    elif action == "register":
        limits = [
            (f"auth:register:ip:{client_ip}", 3, 3600),
            (f"auth:register:ip-day:{client_ip}", 5, 86400),
        ]
    else:
        username_digest = hashlib.sha256(username.casefold().encode()).hexdigest()
        limits = [
            (f"auth:login:ip:{client_ip}", 30, 300),
            (f"auth:login:user:{username_digest}", 10, 300),
        ]
    return consume_rate_limits(limits) is not None


def registration_quota_exceeded():
    """全站每日注册上限（按最近 24 小时成功注册数计算），0 表示不限制。

    只统计成功注册，失败的尝试不占名额，避免攻击者刷失败请求把正常客户挡在门外。
    """
    try:
        daily_limit = int(setting("registration_daily_limit", "30"))
    except (TypeError, ValueError):
        daily_limit = 30
    if daily_limit <= 0:
        return False
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    count = get_db().execute(
        "SELECT COUNT(*) c FROM users WHERE role != 'admin' AND created_at >= ?", (since,)
    ).fetchone()["c"]
    if count >= daily_limit:
        current_app.logger.warning(
            "[注册告警] 最近 24 小时已注册 %s 个账号，达到全站上限 %s，已拒绝新注册", count, daily_limit
        )
        return True
    return False


EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
EMAIL_CODE_TTL_SECONDS = 600
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_CODE_RESEND_SECONDS = 60


def email_verification_required():
    """仅当已配置 SMTP 且管理员未关闭时才要求邮箱验证；否则沿用原有的用户名注册流程。"""
    from src.mailer import smtp_configured
    return smtp_configured() and setting("email_verification_enabled", "1") == "1"


def normalize_email(value):
    email = (value or "").strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        return None
    return email


def _hash_email_code(email, code):
    pepper = current_app.config["SECRET_KEY"].encode()
    return hmac.new(pepper, f"register:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _email_taken(email):
    return get_db().execute(
        "SELECT 1 FROM users WHERE email = ? COLLATE NOCASE", (email,)
    ).fetchone() is not None


def verify_email_code(email, code, purpose="register"):
    """校验验证码；成功后立即作废，失败累计次数，超限作废。返回错误文案或 None。"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM email_verification_codes WHERE email = ? AND purpose = ?", (email, purpose)
    ).fetchone()
    if row is None:
        return "请先获取邮箱验证码"
    if row["expires_at"] <= utcnow() or row["attempts"] >= EMAIL_CODE_MAX_ATTEMPTS:
        db.execute("DELETE FROM email_verification_codes WHERE email = ? AND purpose = ?", (email, purpose))
        db.commit()
        return "验证码已失效，请重新获取"
    if not code or not hmac.compare_digest(row["code_hash"], _hash_email_code(email, code)):
        db.execute(
            "UPDATE email_verification_codes SET attempts = attempts + 1 WHERE email = ? AND purpose = ?",
            (email, purpose),
        )
        db.commit()
        return "验证码错误"
    return None


def consume_email_code(db, email, purpose="register"):
    db.execute("DELETE FROM email_verification_codes WHERE email = ? AND purpose = ?", (email, purpose))


def csrf_protected(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not validate_csrf():
            flash("页面已过期，请重试", "error")
            return redirect(request.referrer or url_for("web.index"))
        return view(*args, **kwargs)
    return wrapped


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        if g.user["role"] != "admin":
            flash("需要管理员权限", "error")
            return redirect(url_for("portal.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None if user_id is None else get_db().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def _client_ip():
    from src.api.access import get_client_ip
    return get_client_ip()


@bp.before_app_request
def block_blacklisted_ip():
    """管理员全局 IP 黑名单：命中后注册、登录、接口调用、在线体验全部拒绝。

    已登录的管理员不受影响，避免误封自己后无法进入后台解封。
    """
    if request.endpoint == "static":
        return None
    if g.get("user") is not None and g.user["role"] == "admin":
        return None
    from src.ip_rules import is_ip_blacklisted
    client_ip = _client_ip()
    if not is_ip_blacklisted(client_ip):
        return None
    current_app.logger.warning("[IP 黑名单] 已拦截 %s %s", client_ip, request.path)
    if request.path.startswith("/api/"):
        from src.api.access import record_request
        from src.api.response import make_response
        record_request(None, None, request.path, 403, "IP_BLOCKED", 0)
        return make_response(403, "当前 IP 已被禁止访问", None, False, "IP_BLOCKED"), 403
    return "当前 IP 已被禁止访问", 403


@bp.route("/setup", methods=("GET", "POST"))
def setup():
    if get_db().execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        if not validate_csrf():
            flash("页面已过期，请重试", "error")
        elif auth_rate_limited("setup"):
            flash("初始化尝试过于频繁，请稍后再试", "error")
            return render_template("auth/setup.html"), 429
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if len(username) < 3 or len(password) < 6:
                flash("用户名至少 3 位，密码至少 6 位", "error")
            elif password != confirm_password:
                flash("两次输入的密码不一致", "error")
            else:
                db = get_db()
                db.execute(
                    "INSERT INTO users(username,password_hash,role,qps_limit,created_at) VALUES(?,?,?,?,?)",
                    (username, generate_password_hash(password), "admin", 20, utcnow()),
                )
                db.commit()
                flash("管理员创建成功，请登录", "success")
                return redirect(url_for("auth.login"))
    return render_template("auth/setup.html")


@bp.post("/register/send-code")
def register_send_code():
    """注册邮箱验证码：仅在启用邮箱验证时可用，返回 JSON 供注册页异步调用。"""
    from src.api.access import consume_rate_limits, get_client_ip
    from src.mailer import send_mail

    def fail(message, status=400):
        return jsonify({"succ": False, "message": message}), status

    if setting("registration_enabled", "1") != "1":
        return fail("当前未开放注册", 403)
    if not email_verification_required():
        return fail("当前未启用邮箱验证", 404)
    if not validate_csrf():
        return fail("页面已过期，请刷新后重试", 400)
    email = normalize_email(request.form.get("email"))
    if not email:
        return fail("请输入有效的邮箱地址")
    if _email_taken(email):
        return fail("该邮箱已注册，请直接登录")
    if registration_quota_exceeded():
        return fail("今日注册名额已满，请明天再试或联系管理员开通", 429)

    client_ip = get_client_ip()
    email_digest = hashlib.sha256(email.encode()).hexdigest()
    limited = consume_rate_limits([
        (f"auth:email-code:email:{email_digest}", 1, EMAIL_CODE_RESEND_SECONDS),
        (f"auth:email-code:email-day:{email_digest}", 5, 86400),
        (f"auth:email-code:ip:{client_ip}", 5, 3600),
        (f"auth:email-code:ip-day:{client_ip}", 20, 86400),
    ])
    if limited is not None:
        return fail("发送过于频繁，请稍后再试", 429)

    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.now(timezone.utc)
    db = get_db()
    db.execute(
        "INSERT INTO email_verification_codes(email,purpose,code_hash,attempts,expires_at,created_at,request_ip) "
        "VALUES(?,?,?,0,?,?,?) ON CONFLICT(email,purpose) DO UPDATE SET "
        "code_hash=excluded.code_hash, attempts=0, expires_at=excluded.expires_at, "
        "created_at=excluded.created_at, request_ip=excluded.request_ip",
        (email, "register", _hash_email_code(email, code),
         (now + timedelta(seconds=EMAIL_CODE_TTL_SECONDS)).isoformat(timespec="seconds"),
         now.isoformat(timespec="seconds"), client_ip),
    )
    db.commit()
    try:
        send_mail(
            email,
            f"【Media Parser】注册验证码 {code}",
            f"您好！\n\n您正在注册 Media Parser 账号，验证码为：{code}\n\n"
            f"验证码 {EMAIL_CODE_TTL_SECONDS // 60} 分钟内有效，请勿泄露给他人。如非本人操作，请忽略本邮件。\n",
        )
    except Exception as exc:
        current_app.logger.error("[邮件发送失败] %s: %s", type(exc).__name__, exc)
        db.execute("DELETE FROM email_verification_codes WHERE email = ? AND purpose = 'register'", (email,))
        db.commit()
        return fail("验证码发送失败，请稍后再试或联系管理员", 502)
    return jsonify({"succ": True, "message": "验证码已发送，请查收邮箱", "resend_after": EMAIL_CODE_RESEND_SECONDS})


@bp.route("/register", methods=("GET", "POST"))
def register():
    if setting("registration_enabled", "1") != "1":
        flash("当前未开放注册", "error")
        return redirect(url_for("auth.login"))
    email_required = email_verification_required()

    def render_register(status=200):
        return render_template(
            "auth/register.html",
            email_required=email_required,
            form_username=request.form.get("username", "").strip(),
            form_email=request.form.get("email", "").strip(),
        ), status

    if request.method == "POST":
        if not validate_csrf():
            flash("页面已过期，请重试", "error")
        elif auth_rate_limited("register"):
            flash("注册尝试过于频繁，请稍后再试", "error")
            return render_register(429)
        elif registration_quota_exceeded():
            flash("今日注册名额已满，请明天再试或联系管理员开通", "error")
            return render_register(429)
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            email = normalize_email(request.form.get("email")) if email_required else None
            email_error = None
            if email_required:
                if not email:
                    email_error = "请输入有效的邮箱地址"
                elif _email_taken(email):
                    email_error = "该邮箱已注册，请直接登录"
            if len(username) < 3 or len(password) < 6:
                flash("用户名至少 3 位，密码至少 6 位", "error")
            elif password != confirm_password:
                flash("两次输入的密码不一致", "error")
            elif email_error:
                flash(email_error, "error")
            elif email_required and (code_error := verify_email_code(email, request.form.get("email_code", "").strip())):
                flash(code_error, "error")
            else:
                try:
                    trial_days = int(setting("default_trial_days", "365"))
                    initial_credits = int(setting("default_initial_credits", "100"))
                    expires_at = None
                    if trial_days > 0:
                        expires_at = (datetime.now(timezone.utc) + timedelta(days=trial_days)).isoformat(timespec="seconds")
                    db = get_db()
                    cur = db.execute(
                        "INSERT INTO users(username,password_hash,qps_limit,expires_at,credits,created_at,register_ip,last_login_ip,last_login_at,email) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (username, generate_password_hash(password), int(setting("default_user_qps", "2")), expires_at, initial_credits, utcnow(),
                         _client_ip(), _client_ip(), utcnow(), email),
                    )
                    user_id = cur.lastrowid
                    if email:
                        consume_email_code(db, email)
                    db.commit()

                    # 自动登录并签发会话
                    session.clear()
                    session["user_id"] = user_id
                    session.permanent = True

                    # 对应场景文案：
                    # A（赠送额度，无时间限制）: 欢迎使用 Media Parser！已发放 {credits} 点免费额度，前往「API 密钥」获取凭证
                    # B（无限额度，无到期）: 欢迎使用 Media Parser！无限额度已启用，前往「API 密钥」获取凭证
                    # C（限时试用，固定额度）: 欢迎使用 Media Parser！试用开通，{credits} 点额度已发放，前往「API 密钥」获取凭证
                    # D（限时试用，无限额度）: 欢迎使用 Media Parser！试用开通，无限额度已启用，前往「API 密钥」获取凭证
                    if trial_days > 0:
                        if initial_credits == -1:
                            msg = "欢迎使用 Media Parser！试用开通，无限额度已启用，前往「API 密钥」获取凭证"
                        else:
                            msg = f"欢迎使用 Media Parser！试用开通，{initial_credits} 点额度已发放，前往「API 密钥」获取凭证"
                    else:
                        if initial_credits == -1:
                            msg = "欢迎使用 Media Parser！无限额度已启用，前往「API 密钥」获取凭证"
                        else:
                            msg = f"欢迎使用 Media Parser！已发放 {initial_credits} 点免费额度，前往「API 密钥」获取凭证"

                    flash(msg, "success")
                    return redirect(url_for("portal.dashboard"))
                except Exception as exc:
                    if "UNIQUE" not in str(exc).upper():
                        raise
                    get_db().rollback()
                    flash("该邮箱已注册，请直接登录" if "email" in str(exc).lower() else "用户名已存在", "error")
    return render_register()


@bp.route("/login", methods=("GET", "POST"))
def login():
    has_admin = bool(get_db().execute("SELECT 1 FROM users WHERE role='admin'").fetchone())
    homepage_enabled = (setting("homepage_enabled", "1") == "1")
    registration_enabled = (setting("registration_enabled", "1") == "1")
    if request.method == "POST":
        if not validate_csrf():
            flash("页面已过期，请重试", "error")
        else:
            username = request.form.get("username", "").strip()
            if auth_rate_limited("login", username):
                flash("登录尝试过于频繁，请稍后再试", "error")
                return render_template(
                    "auth/login.html",
                    has_admin=has_admin,
                    homepage_enabled=homepage_enabled,
                    registration_enabled=registration_enabled,
                ), 429
            user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user is None or not check_password_hash(user["password_hash"], request.form.get("password", "")):
                flash("用户名或密码错误", "error")
            elif not user["active"]:
                flash("账号已被停用", "error")
            else:
                db = get_db()
                db.execute(
                    "UPDATE users SET last_login_ip=?, last_login_at=? WHERE id=?",
                    (_client_ip(), utcnow(), user["id"]),
                )
                db.commit()
                session.clear()
                session["user_id"] = user["id"]
                session.permanent = request.form.get("remember_me") in {"1", "on", "true"}
                target = request.args.get("next", "")
                if (
                    not target.startswith("/")
                    or target.startswith("//")
                    or target.startswith("/auth/")
                    or (user["role"] != "admin" and target.startswith("/admin"))
                ):
                    target = url_for("admin.dashboard") if user["role"] == "admin" else url_for("portal.dashboard")
                return redirect(target)
    return render_template(
        "auth/login.html",
        has_admin=has_admin,
        homepage_enabled=homepage_enabled,
        registration_enabled=registration_enabled,
    )


@bp.post("/logout")
@csrf_protected
def logout():
    session.clear()
    return redirect(url_for("web.index"))


@bp.post("/change-password")
@login_required
@csrf_protected
def change_password():
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(g.user["password_hash"], old_password):
        flash("原密码错误", "error")
    elif len(new_password) < 6:
        flash("新密码至少需要 6 位", "error")
    elif new_password != confirm_password:
        flash("两次输入的新密码不一致", "error")
    else:
        db = get_db()
        db.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(new_password), g.user["id"]),
        )
        db.commit()
        flash("密码修改成功", "success")

    target = request.referrer
    if not target:
        target = url_for("admin.dashboard") if g.user["role"] == "admin" else url_for("portal.dashboard")
    return redirect(target)




def user_is_expired(user):
    if user["role"] == "admin":
        return False
    if not user["expires_at"]:
        return False
    try:
        return datetime.fromisoformat(user["expires_at"]).replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    except ValueError:
        return True


def format_user_expiry(user):
    if not user:
        return "-"
    if user["role"] == "admin" or not user["expires_at"]:
        return "永久有效"
    formatted = format_local_date(user["expires_at"])
    if formatted == "-":
        return "永久有效"
    if user_is_expired(user):
        return f"{formatted} (已到期)"
    return formatted


def format_log_time(value):
    """将数据库中以 UTC 保存的时间展示为北京时间。"""
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)[:19].replace("T", " ")


def format_local_date(value):
    """将 UTC 时间转换为北京时间日期，供日期型表单和状态使用。"""
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    except ValueError:
        return str(value)[:10]


def api_base_url():
    """获取对外 API 基础根地址，智能识别反向代理协议（如 Nginx X-Forwarded-Proto）并自适应环境。"""
    import os
    env_base = os.getenv("API_BASE_URL") or os.getenv("BASE_URL")
    if env_base:
        return env_base.rstrip("/") + "/"
    try:
        if not request:
            return "http://localhost:8051/"
        proto = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)
        return f"{proto}://{host}/"
    except RuntimeError:
        return "http://localhost:8051/"


def is_api_enabled():
    """检查全局 API 服务开关是否开启。"""
    return setting("global_api_enabled", "1") == "1"


def render_icon(name, class_name="w-4 h-4"):
    from markupsafe import Markup
    return Markup(f'<svg class="{class_name}" aria-hidden="true" focusable="false"><use href="/static/icons.svg#icon-{name}"></use></svg>')


def register_template_helpers(app):
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["user_is_expired"] = user_is_expired
    app.jinja_env.globals["format_user_expiry"] = format_user_expiry
    app.jinja_env.globals["format_log_time"] = format_log_time
    app.jinja_env.globals["format_local_date"] = format_local_date
    app.jinja_env.globals["api_base_url"] = api_base_url
    app.jinja_env.globals["is_api_enabled"] = is_api_enabled
    app.jinja_env.globals["icon"] = render_icon

