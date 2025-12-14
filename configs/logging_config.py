import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 使用 pathlib 创建目录
log_path = Path('logs/parse_ucmao.log')
log_path.parent.mkdir(parents=True, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            str(log_path),  # pathlib.Path 转字符串
            maxBytes=1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
