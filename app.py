import os
import secrets
import fcntl
from datetime import timedelta
from flask import Flask
from src.api.parse import bp as api_bp
from src.web.views import bp as web_bp
from src.auth import bp as auth_bp, register_template_helpers
from src.web.portal import bp as portal_bp
from src.web.admin import bp as admin_bp
from src.db import init_app as init_database
from configs.logging_config import get_logger

logger = get_logger(__name__)


def _load_or_create_secret(data_dir):
    """为零配置部署生成可持久化的随机会话密钥。"""
    secret_path = os.path.join(data_dir, ".secret_key")
    try:
        descriptor = os.open(secret_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "r+", encoding="utf-8") as secret_file:
            fcntl.flock(secret_file.fileno(), fcntl.LOCK_EX)
            saved = secret_file.read().strip()
            if saved:
                return saved
            generated = secrets.token_hex(32)
            secret_file.seek(0)
            secret_file.write(generated)
            secret_file.flush()
            os.fsync(secret_file.fileno())
            return generated
    except (PermissionError, OSError) as e:
        logger.warning(f"无法读写密钥文件 {secret_path}，使用临时随机会话密钥: {e}")
        return secrets.token_hex(32)


def create_app(config=None):
    """应用工厂函数"""
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
    app = Flask(__name__, instance_path=data_dir, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or None
    app.config['DATABASE'] = os.getenv(
        'DATABASE_PATH', os.path.join(app.instance_path, 'media_parser.db')
    )
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['JSON_SORT_KEYS'] = False
    app.config['TRUST_PROXY_HEADERS'] = os.getenv(
        'TRUST_PROXY_HEADERS', ''
    ).strip().lower() in {'1', 'true', 'yes', 'on'}
    if hasattr(app, 'json'):
        app.json.sort_keys = False
    if config:
        app.config.update(config)

    database_dir = os.path.dirname(app.config['DATABASE'])
    if database_dir:
        os.makedirs(database_dir, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = _load_or_create_secret(database_dir or app.instance_path)
    init_database(app)
    register_template_helpers(app)

    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(admin_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051)
