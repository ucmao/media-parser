import csv
from datetime import datetime, time, timezone
import io
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, flash, g, redirect, render_template, request, session, url_for

from configs.general_constants import DOMAIN_TO_NAME
from src.auth import csrf_protected, format_log_time, generate_api_key, hash_api_key, login_required, user_is_expired
from src.db import get_daily_trend, get_db, get_platform_distribution, get_top_keys, utcnow
from src.utils.table_query import paginate_memory_list, query_paginated_table


bp = Blueprint("portal", __name__, url_prefix="/console")


def _positive_page(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _parse_shanghai_to_utc_iso(val: str, is_end: bool = False) -> str | None:
    if not val:
        return None
    val = val.strip()
    if not val:
        return None
    if len(val) == 10 and val.count("-") == 2:
        try:
            d = datetime.strptime(val, "%Y-%m-%d").date()
            t = time.max if is_end else time.min
            dt = datetime.combine(d, t, tzinfo=ZoneInfo("Asia/Shanghai"))
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            return None
    return None


# ----------------------------------------------------------------------
# 1. 客户概览 (Overview)
# ----------------------------------------------------------------------

@bp.get("", endpoint="dashboard")
@bp.get("/overview", endpoint="overview")
@login_required
def overview():
    try:
        days = int(request.args.get("days", 7))
        if days not in (7, 30, 90, 180, 0):
            days = 7
    except (TypeError, ValueError):
        days = 7

    db = get_db()
    stats = db.execute(
        "SELECT COUNT(*) calls, SUM(status_code < 400) successes FROM request_logs "
        "WHERE user_id=? AND datetime(created_at) >= datetime('now','-1 day')",
        (g.user["id"],),
    ).fetchone()
    chart_data = get_daily_trend(user_id=g.user["id"], days=days)
    pie_data = get_platform_distribution(user_id=g.user["id"], days=days)
    top_keys = get_top_keys(user_id=g.user["id"], days=days, limit=10)

    return render_template(
        "portal/overview.html",
        stats=stats,
        chart_data=chart_data,
        pie_data=pie_data,
        top_keys=top_keys,
        current_days=days,
        active_nav="overview",
    )


# ----------------------------------------------------------------------
# 2. API 密钥 (Keys)
# ----------------------------------------------------------------------

@bp.get("/keys")
@login_required
def keys():
    db = get_db()
    keys_where, keys_params = ["k.user_id = ?"], [g.user["id"]]
    if k_q := request.args.get("keys_q", request.args.get("q", "")).strip():
        keys_where.append("k.name LIKE ?")
        keys_params.append(f"%{k_q}%")
    if k_active := request.args.get("keys_active", "").strip():
        try:
            val = int(k_active)
            keys_where.append("k.active = ?")
            keys_params.append(val)
        except ValueError:
            pass

    keys_allowed_sorts = {
        "id": "k.id",
        "name": "k.name",
        "created_at": "k.created_at",
        "last_used_at": "k.last_used_at",
        "active": "k.active",
    }
    keys_table = query_paginated_table(
        db,
        base_from_sql="api_keys k",
        select_fields="k.*",
        allowed_sorts=keys_allowed_sorts,
        default_sort="id",
        default_order="desc",
        where_clauses=keys_where,
        where_params=keys_params,
        request_args=request.args,
        prefix="keys_",
    )

    return render_template(
        "portal/keys.html",
        keys=keys_table["items"],
        keys_table=keys_table,
        my_keys=keys_table["items"],
        new_api_key=session.pop("new_api_key", None),
        active_nav="keys",
    )


@bp.post("/keys/batch")
@login_required
@csrf_protected
def batch_keys():
    db = get_db()
    ids_raw = request.form.get("ids", "").strip()
    action = request.form.get("action", "").strip()

    if not ids_raw or not action:
        flash("请先勾选需要批量操作的 API Key", "error")
        return redirect(url_for("portal.keys"))

    try:
        key_ids = [int(i.strip()) for i in ids_raw.split(",") if i.strip().isdigit()]
    except ValueError:
        key_ids = []

    if not key_ids:
        flash("未获取到有效的密钥 ID 列表", "error")
        return redirect(url_for("portal.keys"))

    placeholders = ",".join(["?"] * len(key_ids))

    if action == "enable":
        db.execute(f"UPDATE api_keys SET active=1 WHERE id IN ({placeholders}) AND user_id=?", key_ids + [g.user["id"]])
        flash(f"已批量启用选中的 {len(key_ids)} 个 API Key", "success")
    elif action == "disable":
        db.execute(f"UPDATE api_keys SET active=0 WHERE id IN ({placeholders}) AND user_id=?", key_ids + [g.user["id"]])
        flash(f"已批量停用选中的 {len(key_ids)} 个 API Key", "success")
    elif action == "delete":
        db.execute(f"DELETE FROM api_keys WHERE id IN ({placeholders}) AND user_id=?", key_ids + [g.user["id"]])
        flash(f"已批量删除选中的 {len(key_ids)} 个 API Key", "success")

    db.commit()
    return redirect(url_for("portal.keys"))


@bp.post("/keys")
@login_required
@csrf_protected
def create_key():
    if user_is_expired(g.user):
        flash("账号尚未开通或已到期，不能创建密钥", "error")
        return redirect(url_for("portal.keys"))
    name = request.form.get("name", "").strip()[:40] or "默认密钥"
    count = get_db().execute(
        "SELECT COUNT(*) count FROM api_keys WHERE user_id=?", (g.user["id"],)
    ).fetchone()["count"]
    if count >= 10:
        flash("每个账号最多创建 10 个密钥", "error")
        return redirect(url_for("portal.keys"))
    raw_key = generate_api_key()
    db = get_db()
    db.execute(
        "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
        (g.user["id"], name, hash_api_key(raw_key), raw_key[:11], utcnow()),
    )
    db.commit()
    session["new_api_key"] = raw_key
    flash("密钥创建成功，请立即复制；离开页面后无法再次查看", "success")
    return redirect(url_for("portal.keys"))


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
    return redirect(url_for("portal.keys"))


@bp.post("/keys/<int:key_id>/update")
@login_required
@csrf_protected
def update_key(key_id):
    name = request.form.get("name", "").strip()[:40]
    if not name:
        flash("密钥名称不能为空", "error")
        return redirect(url_for("portal.keys"))
    db = get_db()
    db.execute(
        "UPDATE api_keys SET name=? WHERE id=? AND user_id=?",
        (name, key_id, g.user["id"]),
    )
    db.commit()
    flash("密钥名称已成功修改", "success")
    return redirect(url_for("portal.keys"))


@bp.post("/keys/<int:key_id>/delete")
@login_required
@csrf_protected
def delete_key(key_id):
    db = get_db()
    db.execute("DELETE FROM api_keys WHERE id=? AND user_id=?", (key_id, g.user["id"]))
    db.commit()
    flash("密钥已删除，相关调用日志会保留", "success")
    return redirect(url_for("portal.keys"))


# ----------------------------------------------------------------------
# 3. 开发者文档 (Docs)
# ----------------------------------------------------------------------

@bp.get("/docs")
@login_required
def docs():
    db = get_db()
    keys_list = db.execute(
        "SELECT * FROM api_keys WHERE user_id=? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()
    return render_template(
        "portal/docs.html",
        keys=keys_list,
        my_keys=keys_list,
        active_nav="docs",
    )


# ----------------------------------------------------------------------
# 4. 支持平台 (Platforms)
# ----------------------------------------------------------------------

@bp.get("/platforms")
@login_required
def platforms():
    db = get_db()
    configured = {row["platform"]: row for row in db.execute("SELECT * FROM platform_settings")}

    # 平台与域名映射
    platform_to_domains = {}
    for domain, pname in DOMAIN_TO_NAME.items():
        platform_to_domains.setdefault(pname, []).append(domain)
    for pname in platform_to_domains:
        platform_to_domains[pname].sort()

    # 当前客户近 24 小时各平台解析调用统计
    stats_rows = db.execute(
        "SELECT platform, COUNT(*) as calls, SUM(status_code < 400) as successes "
        "FROM request_logs "
        "WHERE user_id=? AND datetime(created_at) >= datetime('now', '-1 day') "
        "GROUP BY platform",
        (g.user["id"],),
    ).fetchall()
    stats_by_platform = {}
    for r in stats_rows:
        p = r["platform"]
        calls = r["calls"] or 0
        successes = r["successes"] or 0
        stats_by_platform[p] = {
            "calls": calls,
            "successes": successes,
            "success_rate": round(successes * 100.0 / calls, 1) if calls > 0 else 0,
        }

    platforms_list = []
    for name in sorted(set(DOMAIN_TO_NAME.values())):
        row = configured.get(name)
        p_stats = stats_by_platform.get(name, {"calls": 0, "successes": 0, "success_rate": 0})
        platforms_list.append({
            "name": name,
            "enabled": True if row is None else bool(row["enabled"]),
            "domains": platform_to_domains.get(name, []),
            "domain_count": len(platform_to_domains.get(name, [])),
            "my_calls_24h": p_stats["calls"],
            "my_successes_24h": p_stats["successes"],
            "my_success_rate_24h": p_stats["success_rate"],
        })

    # 过滤条件筛选
    p_q = request.args.get("platforms_q", "").strip().lower()
    p_status = request.args.get("platforms_status", "").strip()

    filtered_platforms = []
    for p in platforms_list:
        if p_q:
            match_name = p_q in p["name"].lower()
            match_domains = any(p_q in d.lower() for d in p["domains"])
            if not (match_name or match_domains):
                continue
        if p_status == "enabled" and not p["enabled"]:
            continue
        elif p_status == "disabled" and p["enabled"]:
            continue
        filtered_platforms.append(p)

    platforms_allowed_sorts = {
        "name": "name",
        "domains": "domain_count",
        "calls": "my_calls_24h",
        "rate": "my_success_rate_24h",
        "success_rate": "my_success_rate_24h",
        "status": lambda x: (not x["enabled"], x["name"]),
    }

    platforms_table = paginate_memory_list(
        filtered_platforms,
        allowed_sorts=platforms_allowed_sorts,
        default_sort="name",
        default_order="asc",
        request_args=request.args,
        default_page_size=50,
        prefix="platforms_",
    )

    return render_template(
        "portal/platforms.html",
        platforms=platforms_table["items"],
        platforms_table=platforms_table,
        active_nav="platforms",
    )


# ----------------------------------------------------------------------
# 4. 请求日志 (Logs)
# ----------------------------------------------------------------------

@bp.get("/logs")
@login_required
def logs():
    db = get_db()
    logs_where, logs_params = ["l.user_id = ?"], [g.user["id"]]
    if l_q := request.args.get("logs_q", request.args.get("q", "")).strip():
        logs_where.append("(l.input_url LIKE ? OR l.error_code LIKE ? OR k.name LIKE ?)")
        logs_params.extend([f"%{l_q}%", f"%{l_q}%", f"%{l_q}%"])
    if l_status := request.args.get("logs_status", request.args.get("status_code", "")).strip():
        if l_status == "200":
            logs_where.append("l.status_code < 400")
        elif l_status == "error":
            logs_where.append("l.status_code >= 400")
        elif l_status.isdigit():
            logs_where.append("l.status_code = ?")
            logs_params.append(int(l_status))
    if l_platform := request.args.get("logs_platform", request.args.get("platform", "")).strip():
        logs_where.append("l.platform = ?")
        logs_params.append(l_platform)
    if utc_start := _parse_shanghai_to_utc_iso(request.args.get("logs_start_date", request.args.get("start_date", "")), is_end=False):
        logs_where.append("l.created_at >= ?")
        logs_params.append(utc_start)
    if utc_end := _parse_shanghai_to_utc_iso(request.args.get("logs_end_date", request.args.get("end_date", "")), is_end=True):
        logs_where.append("l.created_at <= ?")
        logs_params.append(utc_end)

    logs_allowed_sorts = {
        "id": "l.id",
        "created_at": "l.created_at",
        "duration_ms": "l.duration_ms",
        "status_code": "l.status_code",
        "platform": "l.platform",
    }

    req_args = dict(request.args)
    if "page" in req_args and "logs_page" not in req_args:
        req_args["logs_page"] = req_args["page"]

    logs_table = query_paginated_table(
        db,
        base_from_sql="request_logs l LEFT JOIN api_keys k ON k.id=l.api_key_id",
        select_fields="l.*, k.key_prefix, k.name as key_name",
        allowed_sorts=logs_allowed_sorts,
        default_sort="id",
        default_order="desc",
        where_clauses=logs_where,
        where_params=logs_params,
        request_args=req_args,
        prefix="logs_",
    )

    platform_rows = db.execute(
        "SELECT DISTINCT platform FROM request_logs WHERE user_id=? AND platform IS NOT NULL AND platform != '' ORDER BY platform ASC",
        (g.user["id"],),
    ).fetchall()
    platforms = [r["platform"] for r in platform_rows]

    return render_template(
        "portal/logs.html",
        logs=logs_table["items"],
        logs_table=logs_table,
        platforms=platforms,
        active_nav="logs",
    )


def _safe_csv_cell(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@bp.get("/logs/export.csv")
@login_required
def export_logs():
    db = get_db()
    export_type = request.args.get("export_type", "all")
    ids_param = request.args.get("ids", "").strip()

    where_clauses, params = ["l.user_id = ?"], [g.user["id"]]

    if export_type == "selected" and ids_param:
        try:
            id_list = [int(i.strip()) for i in ids_param.split(",") if i.strip().isdigit()]
            if id_list:
                placeholders = ",".join(["?"] * len(id_list))
                where_clauses.append(f"l.id IN ({placeholders})")
                params.extend(id_list)
        except ValueError:
            pass
    else:
        if l_q := request.args.get("logs_q", request.args.get("q", "")).strip():
            where_clauses.append("(l.input_url LIKE ? OR l.error_code LIKE ? OR k.name LIKE ?)")
            params.extend([f"%{l_q}%", f"%{l_q}%", f"%{l_q}%"])
        if l_status := request.args.get("logs_status", request.args.get("status_code", "")).strip():
            if l_status == "200":
                where_clauses.append("l.status_code < 400")
            elif l_status == "error":
                where_clauses.append("l.status_code >= 400")
            elif l_status.isdigit():
                where_clauses.append("l.status_code = ?")
                params.append(int(l_status))
        if l_platform := request.args.get("logs_platform", request.args.get("platform", "")).strip():
            where_clauses.append("l.platform = ?")
            params.append(l_platform)
        if utc_start := _parse_shanghai_to_utc_iso(request.args.get("logs_start_date", request.args.get("start_date", "")), is_end=False):
            where_clauses.append("l.created_at >= ?")
            params.append(utc_start)
        if utc_end := _parse_shanghai_to_utc_iso(request.args.get("logs_end_date", request.args.get("end_date", "")), is_end=True):
            where_clauses.append("l.created_at <= ?")
            params.append(utc_end)

    where_sql = " WHERE " + " AND ".join(where_clauses)

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("时间", "调用 Key", "平台", "请求路径", "请求 URL", "状态码", "耗时（毫秒）", "错误码"))

    sql = f"""SELECT l.*, k.key_prefix, k.name as key_name
              FROM request_logs l
              LEFT JOIN api_keys k ON l.api_key_id = k.id
              {where_sql}
              ORDER BY l.id DESC"""
    cursor = db.execute(sql, params)
    while rows := cursor.fetchmany(1000):
        for row in rows:
            key_display = f"{row['key_name']} ({row['key_prefix']}...)" if row["key_prefix"] else "Web 免鉴权"
            writer.writerow((
                _safe_csv_cell(format_log_time(row["created_at"])),
                _safe_csv_cell(key_display),
                _safe_csv_cell(row["platform"] or ""),
                _safe_csv_cell(row["path"]),
                _safe_csv_cell(row["input_url"] or ""),
                _safe_csv_cell(row["status_code"]),
                _safe_csv_cell(row["duration_ms"]),
                _safe_csv_cell(row["error_code"] or ""),
            ))

    csv_bytes = output.getvalue().encode("utf-8")
    filename = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("my-request-logs-%Y%m%d-%H%M%S.csv")
    return Response(
        csv_bytes,
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(csv_bytes)),
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
