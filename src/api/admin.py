from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
import os
import json
from datetime import datetime, timedelta
from configs.general_constants import DATABASE_CONFIG, SAVE_VIDEO_PATH
from src.database.db_manager import DBManager
from configs.logging_config import logger

bp = Blueprint('admin_modern', __name__, url_prefix='/admin')


def get_db():
    db = DBManager(**DATABASE_CONFIG)
    db.connect()
    return db


def delete_video_files(video_ids):
    """Delete corresponding .mp4 files from static/videos for given video_ids."""
    if not video_ids:
        return 0
    deleted_count = 0
    for vid in video_ids:
        filename = f"{vid}.mp4"
        path = os.path.join(SAVE_VIDEO_PATH, filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
                deleted_count += 1
            except OSError as e:
                logger.warning(f"Failed to delete video file {path}: {e}")
    return deleted_count


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_modern.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_only(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('admin_role') != 'admin':
            return jsonify({'success': False, 'message': '权限不足：演示账号仅供查看，无法修改数据'}), 403
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_modern.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 账号配置
        admin_user = os.getenv('ADMIN_USER', 'admin')
        admin_pwd = os.getenv('ADMIN_PASSWORD', 'admin123')
        demo_user = os.getenv('DEMO_USER', 'guest')
        demo_pwd = os.getenv('DEMO_PASSWORD', 'guest123')
        
        if username == admin_user and password == admin_pwd:
            session['admin_logged_in'] = True
            session['admin_user'] = username
            session['admin_role'] = 'admin'
            return redirect(url_for('admin_modern.dashboard'))
        elif username == demo_user and password == demo_pwd:
            session['admin_logged_in'] = True
            session['admin_user'] = username
            session['admin_role'] = 'viewer'
            return redirect(url_for('admin_modern.dashboard'))
        else:
            flash('用户名或密码错误', 'error')
            
    return render_template('admin_modern/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_modern.login'))

@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    cursor = db.conn.cursor(dictionary=True)
    
    # 获取统计数据
    cursor.execute("SELECT COUNT(*) as count FROM parse_library")
    video_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()['count']
    
    # 今日活跃 (DAU)
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(updated_at) = CURDATE()")
    active_user_count = cursor.fetchone()['count']
    
    # 最近 10 条视频 (关联用户信息)
    cursor.execute("""
        SELECT pl.*, u.nickname as last_user_name 
        FROM parse_library pl 
        LEFT JOIN users u ON pl.last_user_id = u.user_id 
        ORDER BY pl.create_at DESC 
        LIMIT 10
    """)
    recent_videos = cursor.fetchall()
    
    db.disconnect()
    return render_template('admin_modern/dashboard.html', 
                           video_count=video_count, 
                           user_count=user_count, 
                           active_user_count=active_user_count,
                           recent_videos=recent_videos)

@bp.route('/videos')
@login_required
def videos():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'create_at')
    order = request.args.get('order', 'desc')
    limit = 20
    offset = (page - 1) * limit
    
    db = get_db()
    cursor = db.conn.cursor(dictionary=True)
    
    # 搜索
    search = request.args.get('search', '')
    platform = request.args.get('platform', '')
    visibility = request.args.get('visibility', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    min_score = request.args.get('min_score', '')
    max_score = request.args.get('max_score', '')
    
    query = "SELECT pl.*, u.nickname as last_user_name FROM parse_library pl LEFT JOIN users u ON pl.last_user_id = u.user_id WHERE 1=1"
    params = []
    
    if search:
        query += " AND (title LIKE %s OR video_id LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    if platform:
        query += " AND platform = %s"
        params.append(platform)
    if visibility != '':
        query += " AND is_visible = %s"
        params.append(visibility)
    if start_date:
        query += " AND DATE(create_at) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND DATE(create_at) <= %s"
        params.append(end_date)
    if min_score:
        query += " AND score >= %s"
        params.append(min_score)
    if max_score:
        query += " AND score <= %s"
        params.append(max_score)
        
    # 获取总数用于分页
    cursor.execute(f"SELECT COUNT(*) as count FROM ({query}) as t", params)
    total = cursor.fetchone()['count']
    
    # 排序逻辑
    allowed_sort_fields = ['create_at', 'score', 'platform']
    if sort_by not in allowed_sort_fields:
        sort_by = 'create_at'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'
        
    query += f" ORDER BY {sort_by} {order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    video_list = cursor.fetchall()
    
    db.disconnect()
    return render_template('admin_modern/videos.html', 
                           videos=video_list, 
                           page=page, 
                           total=total, 
                           limit=limit,
                           search=search,
                           platform=platform,
                           visibility=visibility,
                           start_date=start_date,
                           end_date=end_date,
                           min_score=min_score,
                           max_score=max_score,
                           sort_by=sort_by,
                           order=order)

@bp.route('/users')
@login_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    limit = 20
    offset = (page - 1) * limit
    
    db = get_db()
    cursor = db.conn.cursor(dictionary=True)
    
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    
    if search:
        query += " AND (nickname LIKE %s OR open_id LIKE %s OR city LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
    # 获取总数用于分页
    cursor.execute(f"SELECT COUNT(*) as count FROM ({query}) as t", params)
    total = cursor.fetchone()['count']
    
    # 排序处理
    allowed_sort_fields = ['user_id', 'created_at', 'updated_at']
    if sort_by not in allowed_sort_fields:
        sort_by = 'created_at'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'
        
    query += f" ORDER BY {sort_by} {order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    user_list = cursor.fetchall()
    
    db.disconnect()
    return render_template('admin_modern/users.html', 
                           users=user_list,
                           page=page,
                           total=total,
                           limit=limit,
                           search=search,
                           sort_by=sort_by,
                           order=order)

@bp.route('/api/user_records/<open_id>')
@login_required
def get_user_records(open_id):
    db = get_db()
    try:
        cursor = db.conn.cursor(dictionary=True)
        # 获取用户的 video_records JSON 字段
        cursor.execute("SELECT video_records FROM users WHERE open_id = %s", (open_id,))
        user = cursor.fetchone()
        
        if not user or not user['video_records']:
            return jsonify({'success': True, 'records': []})
            
        record_map = json.loads(user['video_records'])
        if not record_map:
            return jsonify({'success': True, 'records': []})
            
        # 获取所有视频详情
        video_ids = list(record_map.keys())
        format_strings = ','.join(['%s'] * len(video_ids))
        cursor.execute(f"SELECT video_id, title, cover_url, video_url, platform, create_at FROM parse_library WHERE video_id IN ({format_strings})", tuple(video_ids))
        videos = cursor.fetchall()
        
        # 合并解析时间
        results = []
        for v in videos:
            vid = v['video_id']
            results.append({
                **v,
                'parse_time': record_map[vid],
                'create_at': v['create_at'].strftime('%Y-%m-%d %H:%M') if v['create_at'] else '-'
            })
            
        # 按解析时间排序
        results.sort(key=lambda x: x['parse_time'], reverse=True)
        
        return jsonify({'success': True, 'records': results})
    except Exception as e:
        logger.error(f"Get user records error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/delete_user_record', methods=['POST'])
@login_required
@admin_only
def delete_user_record():
    data = request.json
    open_id = data.get('open_id')
    video_id = data.get('video_id')
    
    if not open_id or not video_id:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        
    db = get_db()
    try:
        cursor = db.conn.cursor(dictionary=True)
        cursor.execute("SELECT video_records FROM users WHERE open_id = %s", (open_id,))
        user = cursor.fetchone()
        
        if user and user['video_records']:
            records = json.loads(user['video_records'])
            if video_id in records:
                del records[video_id]
                cursor.execute("UPDATE users SET video_records = %s WHERE open_id = %s", (json.dumps(records), open_id))
                db.conn.commit()
                return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'Record not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/clear_user_records', methods=['POST'])
@login_required
@admin_only
def clear_user_records():
    open_id = request.json.get('open_id')
    if not open_id:
        return jsonify({'success': False, 'message': 'Missing open_id'}), 400
        
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE users SET video_records = '{}' WHERE open_id = %s", (open_id,))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/analysis')
@login_required
def analysis():
    return render_template('admin_modern/analysis.html')

@bp.route('/api/analysis_data')
@login_required
def analysis_data():
    db = get_db()
    cursor = db.conn.cursor(dictionary=True)
    try:
        # 1. 最近 14 天活跃解析趋势 (基于 parse_library.create_at)
        cursor.execute("""
            SELECT DATE_FORMAT(create_at, '%m-%d') as date, COUNT(*) as count 
            FROM parse_library 
            WHERE create_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(create_at)
            ORDER BY DATE(create_at) ASC
        """)
        parse_trend = cursor.fetchall()

        # 2. 最近 14 天新用户增长趋势
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%m-%d') as date, COUNT(*) as count 
            FROM users 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
        """)
        user_trend = cursor.fetchall()

        # 3. 平台分布 (饼图)
        cursor.execute("""
            SELECT platform, COUNT(*) as count 
            FROM parse_library 
            GROUP BY platform
        """)
        platform_dist = cursor.fetchall()

        # 4. 用户解析贡献排行 (Top 10 Users)
        cursor.execute("""
            SELECT u.nickname as name, COUNT(pl.video_id) as count 
            FROM parse_library pl 
            JOIN users u ON pl.last_user_id = u.user_id 
            WHERE pl.last_user_id IS NOT NULL 
            GROUP BY pl.last_user_id 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_users = cursor.fetchall()

        # 5. 总计数据
        cursor.execute("SELECT COUNT(*) as total FROM parse_library")
        total_parses = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']

        # 今日解析
        cursor.execute("SELECT COUNT(*) as total FROM parse_library WHERE DATE(create_at) = CURDATE()")
        today_parses = cursor.fetchone()['total']

        # 今日新用户
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE DATE(created_at) = CURDATE()")
        today_new_users = cursor.fetchone()['total']
        
        # 今日活跃用户 (DAU)
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE DATE(updated_at) = CURDATE()")
        today_active_users = cursor.fetchone()['total']

        return jsonify({
            'success': True,
            'parse_trend': parse_trend,
            'user_trend': user_trend,
            'platform_dist': platform_dist,
            'top_users': top_users,
            'stats': {
                'total_parses': total_parses,
                'total_users': total_users,
                'today_parses': today_parses,
                'today_new_users': today_new_users,
                'today_active_users': today_active_users
            }
        })
    except Exception as e:
        logger.error(f"Analysis data error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/scores')
@login_required
def scores():
    sort_by = request.args.get('sort_by', 'config_value')
    order = request.args.get('order', 'desc')
    
    db = get_db()
    cursor = db.conn.cursor(dictionary=True)
    
    allowed_sort_fields = ['config_key', 'config_value', 'is_enabled']
    if sort_by not in allowed_sort_fields:
        sort_by = 'config_value'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'
        
    cursor.execute(f"SELECT * FROM score_config ORDER BY {sort_by} {order}")
    score_list = cursor.fetchall()
    db.disconnect()
    return render_template('admin_modern/scores.html', 
                           scores=score_list,
                           sort_by=sort_by,
                           order=order)

# 功能性接口
@bp.route('/api/update_score', methods=['POST'])
@login_required
@admin_only
def update_score():
    data = request.json
    key = data.get('key')
    value = data.get('value')
    
    if not key or value is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE score_config SET config_value = %s WHERE config_key = %s", (value, key))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update score error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/toggle_score_status', methods=['POST'])
@login_required
@admin_only
def toggle_score_status():
    data = request.json
    key = data.get('key')
    is_enabled = data.get('is_enabled')
    
    if not key or is_enabled is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE score_config SET is_enabled = %s WHERE config_key = %s", (1 if is_enabled else 0, key))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Toggle score status error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()
@bp.route('/api/update_video_title', methods=['POST'])
@login_required
@admin_only
def update_video_title():
    data = request.json
    video_id = data.get('video_id')
    new_title = data.get('title')
    
    if not video_id or new_title is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE parse_library SET title = %s WHERE video_id = %s", (new_title, video_id))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update title error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/update_video_score', methods=['POST'])
@login_required
@admin_only
def update_video_score():
    data = request.json
    video_id = data.get('video_id')
    new_score = data.get('score')
    
    if not video_id or new_score is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE parse_library SET score = %s WHERE video_id = %s", (new_score, video_id))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Update score error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/toggle_visibility', methods=['POST'])
@login_required
@admin_only
def toggle_visibility():
    data = request.json
    video_id = data.get('video_id')
    is_visible = data.get('is_visible')
    
    if not video_id or is_visible is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE parse_library SET is_visible = %s WHERE video_id = %s", (1 if is_visible else 0, video_id))
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Toggle visibility error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/bulk_visibility', methods=['POST'])
@login_required
@admin_only
def bulk_visibility():
    data = request.json
    video_ids = data.get('video_ids', [])
    is_visible = data.get('is_visible')
    
    if is_visible is None:
        return jsonify({'success': False, 'message': 'Missing is_visible parameter'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        
        # 如果提供了 video_ids，执行批量操作
        if video_ids:
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(f"UPDATE parse_library SET is_visible = %s WHERE video_id IN ({format_strings})", 
                           [1 if is_visible else 0] + video_ids)
        # 如果 video_ids 为空，执行全局操作（支持结合当前筛选条件）
        else:
            search = data.get('search', '')
            platform = data.get('platform', '')
            
            query = "UPDATE parse_library SET is_visible = %s WHERE 1=1"
            params = [1 if is_visible else 0]
            
            if search:
                query += " AND (title LIKE %s OR video_id LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            if platform:
                query += " AND platform = %s"
                params.append(platform)
                
            cursor.execute(query, params)
            
        db.conn.commit()
        return jsonify({'success': True, 'count': cursor.rowcount})
    except Exception as e:
        logger.error(f"Bulk visibility error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/bulk_update_score', methods=['POST'])
@login_required
@admin_only
def bulk_update_score():
    data = request.json
    video_ids = data.get('video_ids', [])
    score_delta = data.get('score_delta', 0)
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        if video_ids:
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(f"UPDATE parse_library SET score = score + %s WHERE video_id IN ({format_strings})", 
                           [score_delta] + video_ids)
        else:
            search = data.get('search', '')
            platform = data.get('platform', '')
            query = "UPDATE parse_library SET score = score + %s WHERE 1=1"
            params = [score_delta]
            if search:
                query += " AND (title LIKE %s OR video_id LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            if platform:
                query += " AND platform = %s"
                params.append(platform)
            cursor.execute(query, params)
            
        db.conn.commit()
        return jsonify({'success': True, 'count': cursor.rowcount})
    except Exception as e:
        logger.error(f"Bulk update score error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/bulk_delete', methods=['POST'])
@login_required
@admin_only
def bulk_delete():
    data = request.json
    video_ids = data.get('video_ids', [])
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        # 如果前端传入了明确的 video_ids，优先按 ID 删除
        if video_ids:
            # 先删除本地文件
            delete_video_files(video_ids)
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(f"DELETE FROM parse_library WHERE video_id IN ({format_strings})", tuple(video_ids))
        else:
            # 否则按当前筛选条件查出 video_id，再删除文件和记录
            search = data.get('search', '')
            platform = data.get('platform', '')
            select_query = "SELECT video_id FROM parse_library WHERE 1=1"
            params = []
            if search:
                select_query += " AND (title LIKE %s OR video_id LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            if platform:
                select_query += " AND platform = %s"
                params.append(platform)
            cursor.execute(select_query, params)
            rows = cursor.fetchall()
            ids_to_delete = [row[0] for row in rows]
            if ids_to_delete:
                delete_video_files(ids_to_delete)
                format_strings = ','.join(['%s'] * len(ids_to_delete))
                delete_query = f"DELETE FROM parse_library WHERE video_id IN ({format_strings})"
                cursor.execute(delete_query, tuple(ids_to_delete))
        count = cursor.rowcount
        db.conn.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"Bulk delete error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/delete_video', methods=['POST'])
@login_required
@admin_only
def delete_video():
    video_id = request.json.get('video_id')
    if not video_id:
        return jsonify({'success': False, 'message': 'Missing video_id'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM parse_library WHERE video_id = %s", (video_id,))
        # 同步删除本地缓存文件
        delete_video_files([video_id])
        db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete video error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/cleanup_empty', methods=['POST'])
@login_required
@admin_only
def cleanup_empty():
    db = get_db()
    try:
        cursor = db.conn.cursor()
        # 先查出需要清理的 video_id，用于删除本地文件
        cursor.execute("SELECT video_id FROM parse_library WHERE title IS NULL OR title = ''")
        rows = cursor.fetchall()
        video_ids = [row[0] for row in rows]
        if video_ids:
            delete_video_files(video_ids)
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(f"DELETE FROM parse_library WHERE video_id IN ({format_strings})", tuple(video_ids))
        count = cursor.rowcount
        db.conn.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

@bp.route('/api/cleanup_keywords', methods=['POST'])
@login_required
@admin_only
def cleanup_keywords():
    data = request.json
    keywords = data.get('keywords', [])
    if not keywords:
        return jsonify({'success': False, 'message': 'No keywords provided'}), 400
    
    db = get_db()
    try:
        cursor = db.conn.cursor()
        like_conditions = " OR ".join(["title LIKE %s"] * len(keywords))
        params = [f"%{kw}%" for kw in keywords]
        
        # 查找匹配的视频ID
        cursor.execute(f"SELECT video_id FROM parse_library WHERE {like_conditions}", params)
        rows = cursor.fetchall()
        video_ids = [row[0] for row in rows]
        
        if not video_ids:
            return jsonify({'success': True, 'count': 0})
        
        # 删除本地缓存文件 + 视频记录
        delete_video_files(video_ids)
        format_strings = ','.join(['%s'] * len(video_ids))
        cursor.execute(f"DELETE FROM parse_library WHERE video_id IN ({format_strings})", tuple(video_ids))
        count = cursor.rowcount
        
        # 同步更新用户记录 (简单实现)
        cursor.execute("SELECT user_id, video_records FROM users WHERE video_records IS NOT NULL")
        users = cursor.fetchall()
        for user_id, records_json in users:
            if records_json:
                records = json.loads(records_json)
                changed = False
                for vid in video_ids:
                    if vid in records:
                        del records[vid]
                        changed = True
                if changed:
                    cursor.execute("UPDATE users SET video_records = %s WHERE user_id = %s", (json.dumps(records), user_id))
        
        db.conn.commit()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"Cleanup keywords error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()


@bp.route('/storage')
@login_required
def storage():
    """视频文件管理页面"""
    return render_template('admin_modern/storage.html')


@bp.route('/api/storage_list')
@login_required
def storage_list():
    """列出 static/videos 下的视频文件及其在库状态"""
    # 简单分页参数
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    sort_by = request.args.get('sort_by', 'video_id')
    order = request.args.get('order', 'asc').lower()
    if page < 1:
        page = 1
    if limit <= 0:
        limit = 50
    if limit > 200:
        limit = 200
    files = []
    if os.path.isdir(SAVE_VIDEO_PATH):
        for name in os.listdir(SAVE_VIDEO_PATH):
            # 仅处理 .mp4 文件
            if not name.lower().endswith('.mp4'):
                continue
            video_id = name[:-4]
            path = os.path.join(SAVE_VIDEO_PATH, name)
            try:
                size_bytes = os.path.getsize(path)
            except OSError:
                size_bytes = 0
            files.append({
                'video_id': video_id,
                'filename': name,
                'size_bytes': size_bytes,
            })

    video_ids = [f['video_id'] for f in files]

    db = get_db()
    try:
        in_db_map = {}
        if video_ids:
            cursor = db.conn.cursor(dictionary=True)
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(
                f"SELECT video_id, title, score FROM parse_library WHERE video_id IN ({format_strings})",
                tuple(video_ids)
            )
            for row in cursor.fetchall():
                in_db_map[row['video_id']] = row
            cursor.close()

        # 先填充库内信息（含积分），再排序
        total_size = sum(f['size_bytes'] for f in files)
        in_db_count = 0
        for f in files:
            vid = f['video_id']
            meta = in_db_map.get(vid)
            f['in_db'] = bool(meta)
            if meta:
                in_db_count += 1
            f['title'] = meta['title'] if meta else None
            f['score'] = meta['score'] if meta and meta.get('score') is not None else None

        # 排序后再分页，避免前端一次性加载所有数据
        allowed_sort_fields = ['video_id', 'size', 'score']
        if sort_by not in allowed_sort_fields:
            sort_by = 'video_id'
        reverse = order == 'desc'
        if sort_by == 'size':
            files.sort(key=lambda f: f['size_bytes'], reverse=reverse)
        elif sort_by == 'score':
            # 无库记录的视为无积分，排序时排到最后；升序低→高，降序高→低
            def score_key(f):
                has = f.get('score') is not None
                s = f.get('score') or 0
                if order == 'desc':
                    return (0 if has else 1, -s)
                return (0 if has else 1, s)
            files.sort(key=score_key)
        else:
            files.sort(key=lambda f: f['video_id'], reverse=reverse)

        total_files = len(files)
        orphan_count = total_files - in_db_count
        stats = {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'in_db_count': in_db_count,
            'orphan_count': orphan_count,
        }

        # 分页切片
        start = (page - 1) * limit
        end = start + limit
        paged_files = files[start:end]
        total_pages = (total_files + limit - 1) // limit if total_files else 1

        return jsonify({
            'success': True,
            'files': paged_files,
            'stats': stats,
            'page': page,
            'limit': limit,
            'total_files': total_files,
            'total_pages': total_pages,
        })
    except Exception as e:
        logger.error(f"Storage list error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()


@bp.route('/api/delete_storage', methods=['POST'])
@login_required
@admin_only
def delete_storage():
    """删除选中的视频文件，可选同时删除数据库记录"""
    data = request.json or {}
    video_ids = data.get('video_ids', [])
    delete_db = bool(data.get('delete_db', False))

    if not video_ids:
        return jsonify({'success': False, 'message': 'Missing video_ids'}), 400

    # 先删除本地文件
    deleted_files = delete_video_files(video_ids)

    deleted_db = 0
    if delete_db:
        db = get_db()
        try:
            cursor = db.conn.cursor()
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(
                f"DELETE FROM parse_library WHERE video_id IN ({format_strings})",
                tuple(video_ids)
            )
            deleted_db = cursor.rowcount
            db.conn.commit()
        except Exception as e:
            logger.error(f"Delete storage DB error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            db.disconnect()

    return jsonify({
        'success': True,
        'deleted_files': deleted_files,
        'deleted_db': deleted_db,
    })


@bp.route('/api/cleanup_orphans', methods=['POST'])
@login_required
@admin_only
def cleanup_orphans():
    """删除 static/videos 中所有没有对应数据库记录的孤儿文件"""
    files = []
    if os.path.isdir(SAVE_VIDEO_PATH):
        for name in os.listdir(SAVE_VIDEO_PATH):
            if not name.lower().endswith('.mp4'):
                continue
            video_id = name[:-4]
            files.append(video_id)

    if not files:
        return jsonify({'success': True, 'deleted_files': 0})

    db = get_db()
    try:
        cursor = db.conn.cursor()
        format_strings = ','.join(['%s'] * len(files))
        cursor.execute(
            f"SELECT video_id FROM parse_library WHERE video_id IN ({format_strings})",
            tuple(files)
        )
        rows = cursor.fetchall()
        in_db_ids = {row[0] for row in rows}

        orphan_ids = [vid for vid in files if vid not in in_db_ids]
        deleted_files = delete_video_files(orphan_ids)
        return jsonify({'success': True, 'deleted_files': deleted_files})
    except Exception as e:
        logger.error(f"Cleanup orphans error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.disconnect()

