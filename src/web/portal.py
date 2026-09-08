import csv
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, flash, g, redirect, render_template, request, session, stream_with_context, url_for

from src.auth import csrf_protected, format_log_time, generate_api_key, hash_api_key, login_required, user_is_expired
from src.db import get_daily_trend, get_db, get_platform_distribution, get_top_keys, utcnow


bp = Blueprint("portal", __name__, url_prefix="/console")


def _positive_page(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


@bp.get("")
@login_required
def dashboard():
    try:
        days = int(request.args.get("days", 7))
        if days not in (7, 30, 90, 180, 0):
            days = 7
    except (TypeError, ValueError):
        days = 7

    db = get_db()
    keys = db.execute(
        "SELECT * FROM api_keys WHERE user_id=? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()
    stats = db.execute(
        "SELECT COUNT(*) calls, SUM(status_code < 400) successes FROM request_logs "
        "WHERE user_id=? AND datetime(created_at) >= datetime('now','-1 day')",
        (g.user["id"],),
    ).fetchone()
    logs_page = _positive_page(request.args.get("logs_page"))
    logs_page_size = 50
    log_rows = db.execute(
        "SELECT * FROM request_logs WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
        (g.user["id"], logs_page_size + 1, (logs_page - 1) * logs_page_size),
    ).fetchall()
    logs = log_rows[:logs_page_size]
    chart_data = get_daily_trend(user_id=g.user["id"], days=days)
    pie_data = get_platform_distribution(user_id=g.user["id"], days=days)
    top_keys = get_top_keys(user_id=g.user["id"], days=days, limit=10)
    return render_template(
        "portal/dashboard.html",
        keys=keys,
        stats=stats,
        logs=logs,
        new_api_key=session.pop("new_api_key", None),
        chart_data=chart_data,
        pie_data=pie_data,
        top_keys=top_keys,
        current_days=days,
        logs_page=logs_page,
        logs_has_next=len(log_rows) > logs_page_size,
    )




def _safe_csv_cell(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


class _CsvRowBuffer:
    def write(self, value):
        return value


@bp.get("/logs/export.csv")
@login_required
def export_logs():
    def generate():
        writer = csv.writer(_CsvRowBuffer())
        yield "\ufeff"
        yield writer.writerow(("时间", "平台", "请求路径", "请求 URL", "状态码", "耗时（毫秒）", "错误码"))
        cursor = get_db().execute(
            "SELECT * FROM request_logs WHERE user_id=? ORDER BY id DESC",
            (g.user["id"],),
        )
        while rows := cursor.fetchmany(1000):
            for row in rows:
                yield writer.writerow(tuple(_safe_csv_cell(value) for value in (
                    format_log_time(row["created_at"]), row["platform"] or "", row["path"],
                    row["input_url"] or "", row["status_code"], row["duration_ms"],
                    row["error_code"] or "",
                )))
    filename = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("my-request-logs-%Y%m%d-%H%M%S.csv")
    return Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.post("/keys")
@login_required
@csrf_protected
def create_key():
    if user_is_expired(g.user):
        flash("账号尚未开通或已到期，不能创建密钥", "error")
        return redirect(url_for("portal.dashboard") + "#keys")
    name = request.form.get("name", "").strip()[:40] or "默认密钥"
    count = get_db().execute(
        "SELECT COUNT(*) count FROM api_keys WHERE user_id=?", (g.user["id"],)
    ).fetchone()["count"]
    if count >= 10:
        flash("每个账号最多创建 10 个密钥", "error")
        return redirect(url_for("portal.dashboard") + "#keys")
    raw_key = generate_api_key()
    db = get_db()
    db.execute(
        "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
        (g.user["id"], name, hash_api_key(raw_key), raw_key[:11], utcnow()),
    )
    db.commit()
    session["new_api_key"] = raw_key
    flash("密钥创建成功，请立即复制；离开页面后无法再次查看", "success")
    return redirect(url_for("portal.dashboard") + "#keys")


@bp.post("/keys/<int:key_id>/toggle")
@login_required
@csrf_protected
def toggle_key(key_id):
    db = get_db()
    db.execute(
        "UPDATE api_keys SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=? AND user_id=?",
        (key_id, g.user["id"]),
    )
    db.commit()
    flash("密钥状态已更新", "success")
    return redirect(url_for("portal.dashboard") + "#keys")


@bp.post("/keys/<int:key_id>/update")
@login_required
@csrf_protected
def update_key(key_id):
    name = request.form.get("name", "").strip()[:40]
    if not name:
        flash("密钥名称不能为空", "error")
        return redirect(url_for("portal.dashboard") + "#keys")
    db = get_db()
    db.execute(
        "UPDATE api_keys SET name=? WHERE id=? AND user_id=?",
        (name, key_id, g.user["id"]),
    )
    db.commit()
    flash("密钥名称已成功修改", "success")
    return redirect(url_for("portal.dashboard") + "#keys")


@bp.post("/keys/<int:key_id>/delete")
@login_required
@csrf_protected
def delete_key(key_id):
    db = get_db()
    db.execute("DELETE FROM api_keys WHERE id=? AND user_id=?", (key_id, g.user["id"]))
    db.commit()
    flash("密钥已删除，相关调用日志会保留", "success")
    return redirect(url_for("portal.dashboard") + "#keys")
