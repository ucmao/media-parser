from flask import Flask, jsonify, render_template
import os
from src.api import parse
from configs.logging_config import get_logger

logger = get_logger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

# 注册API蓝图
app.register_blueprint(parse.bp, url_prefix='/api')


@app.route('/api/health')
def health():
    """供容器编排、反向代理和监控系统检查服务状态。"""
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def index():
    """前台展示页面（Landing Page）"""
    return render_template('landing.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8051)
