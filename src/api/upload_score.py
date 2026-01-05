from flask import Blueprint, request
from configs.logging_config import logger
from utils.common_utils import make_response, validate_request
from src.database.data_storage_manager import DataStorageManager
from configs.general_constants import DATABASE_CONFIG
import mysql.connector

bp = Blueprint('upload_score', __name__)

def get_score_configs():
    """从数据库实时读取积分配置，仅返回已启用的"""
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT config_key, config_value, is_enabled FROM score_config")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        # 仅包含已启用的配置 (is_enabled = 1)
        return {row['config_key']: row['config_value'] for row in rows if row.get('is_enabled', 1) == 1}
    except Exception as e:
        logger.error(f"Failed to fetch score configs: {e}")
        # 降级处理：如果数据库查询失败，返回原始默认值
        return {
            "parse": 10, "shareFriend": 8, "shareTimeline": 12,
            "videoDownload": 5, "imageDownload": 3, "copyAllInfo": 4,
            "copyTitle": 1, "copyCoverUrl": 2, "copyVideoUrl": 3,
            "batchCopyTitle": 1, "batchCopyImageLink": 1, "batchCopyVideoLink": 1,
            "batchCopyAllInfo": 2, "validPlay": 1
        }

@bp.route('/upload_score', methods=['POST'])
def upload_record():
    try:
        data = request.json
        video_ids = data.get('video_ids')  # 支持单个/多个视频ID
        action_type = data.get('action_type')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        # 验证请求参数
        validation_result = validate_request(video_ids, action_type)
        if validation_result:
            return validation_result

        # 实时获取配置的分值
        action_score_map = get_score_configs()

        # 统一视频ID为列表格式（兼容单个/多个视频）
        video_ids = video_ids if isinstance(video_ids, list) else [video_ids]
        if not video_ids:  # 确保视频ID列表不为空
            return make_response(400, '视频ID不能为空', None, None, False), 400

        # 验证行为类型并获取对应积分
        if action_type not in action_score_map:
            logger.warning(f'{wx_open_id} 提交无效行为类型: {action_type}')
            return make_response(400, '无效的行为类型', None, None, False), 400
        current_score = action_score_map[action_type]

        # 初始化数据管理器
        score_manager = DataStorageManager()
        
        # 调用批量添加积分的方法
        batch_result = score_manager.batch_add_score(video_ids=video_ids, add_score=current_score)
        
        # 计算总增加的积分
        total_added = sum(result['added_score'] for result in batch_result if result['success'])
        
        logger.info(f'[{wx_open_id}] 本次为{len(video_ids)}个视频{"各加" if len(video_ids) > 1 else "加"}{total_added // len(video_ids) if video_ids else 0}分，共+{total_added}分（{action_type}操作完成）')
        return make_response(
            200, 
            '积分更新成功', 
            {
                'total_added': total_added,
                'video_results': batch_result
            }, 
            None, 
            True
        ), 200

    except Exception as e:
        logger.error(f'积分上传接口异常: {str(e)}', exc_info=True)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
