import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 使用 pathlib 创建目录
log_path = Path('logs/parse_ucmao.log')
log_path.parent.mkdir(parents=True, exist_ok=True)

# 配置日志格式
# %(asctime)s: 时间
# %(levelname)s: 日志级别
# %(module)s: 模块名（文件名）
# %(lineno)d: 行号
# %(message)s: 日志内容
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'

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

# 为了兼容现有代码，导出一个通用的 logger
# 虽然它名为 'ucmao'，但由于我们在 format 中使用了 %(module)s，
# 所以日志中会显示调用它的具体文件名，而不是统一显示 'configs.logging_config'
logger = logging.getLogger('ucmao')

def get_logger(name):
    """
    获取带名字的 logger。
    推荐用法：在每个模块开头使用
    from configs.logging_config import get_logger
    logger = get_logger(__name__)
    """
    return logging.getLogger(name)
