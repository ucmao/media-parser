import math
from typing import Any, Dict, List, Tuple


ALLOWED_PAGE_SIZES = [20, 50, 100, 200]


def parse_table_params(
    args: Dict[str, Any],
    default_sort: str = "id",
    default_order: str = "desc",
    default_page_size: int = 50,
    prefix: str = "",
    cookies: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    从请求参数中解析通用表格参数（页码、每页条数、排序字段、排序方向、关键字等）。
    支持从浏览器持久化 Cookie 中自动恢复用户上次选择的每页条数偏好。
    """
    page_key = f"{prefix}page" if prefix else "page"
    page_size_key = f"{prefix}page_size" if prefix else "page_size"
    sort_key = f"{prefix}sort_by" if prefix else "sort_by"
    order_key = f"{prefix}order" if prefix else "order"
    q_key = f"{prefix}q" if prefix else "q"

    try:
        page = max(1, int(args.get(page_key, 1)))
    except (TypeError, ValueError):
        page = 1

    # 尝试从请求上下文或参数中获取 Cookie 偏好
    if cookies is None:
        try:
            from flask import has_request_context, request
            if has_request_context() and hasattr(request, "cookies"):
                cookies = request.cookies
        except Exception:
            cookies = None

    clean_prefix = prefix.rstrip("_") if prefix else "default"
    cookie_key = f"mp_page_size_{clean_prefix}"
    pref_size = None
    if cookies and cookie_key in cookies:
        try:
            pref_size = int(cookies[cookie_key])
        except (TypeError, ValueError):
            pref_size = None

    raw_size = args.get(page_size_key, pref_size if pref_size is not None else default_page_size)
    try:
        page_size = int(raw_size)
        if page_size not in ALLOWED_PAGE_SIZES:
            page_size = default_page_size
    except (TypeError, ValueError):
        page_size = default_page_size

    sort_by = str(args.get(sort_key, default_sort)).strip()
    order = str(args.get(order_key, default_order)).strip().lower()
    if order not in ("asc", "desc"):
        order = default_order.lower()

    q = str(args.get(q_key, "")).strip()

    return {
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "order": order,
        "q": q,
        "page_key": page_key,
        "page_size_key": page_size_key,
        "sort_key": sort_key,
        "order_key": order_key,
        "q_key": q_key,
    }


def query_paginated_table(
    db,
    base_from_sql: str,
    select_fields: str,
    allowed_sorts: Dict[str, str],
    default_sort: str = "id",
    default_order: str = "desc",
    where_clauses: List[str] = None,
    where_params: Tuple[Any, ...] = None,
    group_by: str = None,
    request_args: Dict[str, Any] = None,
    default_page_size: int = 50,
    prefix: str = "",
) -> Dict[str, Any]:
    """
    统一的数据库表格分页、排序和数据查询方法。
    """
    if request_args is None:
        request_args = {}

    params = parse_table_params(
        request_args,
        default_sort=default_sort,
        default_order=default_order,
        default_page_size=default_page_size,
        prefix=prefix,
    )

    # 防御性处理：如果 base_from_sql 中误包含了 GROUP BY，提取出来以确保 WHERE 子句在 GROUP BY 之前
    import re

    if not group_by and " GROUP BY " in base_from_sql.upper():
        parts = re.split(r"\s+GROUP\s+BY\s+", base_from_sql, maxsplit=1, flags=re.IGNORECASE)
        base_from_sql = parts[0]
        group_by = parts[1]

    # 1. 校验排序字段（白名单机制，防止 SQL 注入）
    sort_by_key = params["sort_by"]
    if sort_by_key not in allowed_sorts:
        sort_by_key = default_sort
    sort_column = allowed_sorts.get(sort_by_key, list(allowed_sorts.values())[0])

    order_dir = params["order"].upper()

    # 2. 构造 WHERE 与 GROUP BY 语句
    clauses = list(where_clauses) if where_clauses else []
    sql_params = list(where_params) if where_params else []

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    group_sql = f" GROUP BY {group_by}" if group_by else ""

    # 3. 统计总行数
    if group_by:
        count_sql = f"SELECT COUNT(*) FROM (SELECT 1 FROM {base_from_sql}{where_sql}{group_sql})"
    else:
        count_sql = f"SELECT COUNT(*) FROM {base_from_sql}{where_sql}"
    total_count = db.execute(count_sql, sql_params).fetchone()[0]

    total_pages = math.ceil(total_count / params["page_size"]) if total_count > 0 else 1
    page = min(params["page"], total_pages) if total_pages > 0 else 1
    offset = (page - 1) * params["page_size"]

    # 4. 执行翻页与排序查询
    data_sql = (
        f"SELECT {select_fields} FROM {base_from_sql}{where_sql}{group_sql} "
        f"ORDER BY {sort_column} {order_dir} LIMIT ? OFFSET ?"
    )
    data_params = sql_params + [params["page_size"], offset]
    rows = db.execute(data_sql, data_params).fetchall()

    return {
        "items": rows,
        "pagination": {
            "page": page,
            "page_size": params["page_size"],
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "page_sizes": ALLOWED_PAGE_SIZES,
        },
        "sorting": {
            "sort_by": sort_by_key,
            "order": params["order"],
        },
        "query_params": params,
    }


def paginate_memory_list(
    items: List[Dict[str, Any]],
    allowed_sorts: Dict[str, Any],
    default_sort: str = "name",
    default_order: str = "asc",
    request_args: Dict[str, Any] = None,
    default_page_size: int = 50,
    prefix: str = "",
) -> Dict[str, Any]:
    """
    通用内存列表（List[dict]）分页、排序与切片方法。
    """
    if request_args is None:
        request_args = {}

    params = parse_table_params(
        request_args,
        default_sort=default_sort,
        default_order=default_order,
        default_page_size=default_page_size,
        prefix=prefix,
    )

    sort_by_key = params["sort_by"]
    if sort_by_key not in allowed_sorts:
        sort_by_key = default_sort
    sort_spec = allowed_sorts.get(sort_by_key)

    reverse = params["order"].lower() == "desc"

    if callable(sort_spec):
        key_func = sort_spec
    elif isinstance(sort_spec, str):
        def key_func(x):
            val = x.get(sort_spec)
            if val is None:
                return (1, "")
            if isinstance(val, (int, float)):
                return (0, val)
            return (0, str(val).lower())
    else:
        key_func = None

    if key_func:
        sorted_items = sorted(items, key=key_func, reverse=reverse)
    else:
        sorted_items = list(items)

    total_count = len(sorted_items)
    total_pages = math.ceil(total_count / params["page_size"]) if total_count > 0 else 1
    page = min(params["page"], total_pages) if total_pages > 0 else 1
    offset = (page - 1) * params["page_size"]
    paginated_items = sorted_items[offset : offset + params["page_size"]]

    return {
        "items": paginated_items,
        "pagination": {
            "page": page,
            "page_size": params["page_size"],
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "page_sizes": ALLOWED_PAGE_SIZES,
        },
        "sorting": {
            "sort_by": sort_by_key,
            "order": params["order"],
        },
        "query_params": params,
    }

