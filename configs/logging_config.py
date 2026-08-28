import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 使用 pathlib 创建目录
log_path = Path('logs/media_parser.log')
log_path.parent.mkdir(parents=True, exist_ok=True)

# 配置日志格式
# %(asctime)s: 时间
# %(levelname)s: 日志级别
# %(name)s: logger 名称（包含项目与模块名）
# %(lineno)d: 行号
# %(message)s: 日志内容
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s'

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        RotatingFileHandler(
            str(log_path),
            maxBytes=10 * 1024 * 1024,  # 每个日志文件最大 10MB
            backupCount=5,              # 保留 5 个备份文件
            encoding='utf-8'
        ),
        logging.StreamHandler()         # 同时输出到控制台
    ]
)

def get_logger(name: str) -> logging.Logger:
    """
    获取项目命名空间下的模块 logger。
    推荐用法：在每个模块开头使用
    from configs.logging_config import get_logger
    logger = get_logger(__name__)
    """
    return logging.getLogger(f'media_parser.{name}')
