from flask import Blueprint, render_template

bp = Blueprint('web', __name__)


@bp.route('/')
def index():
    """前台展示页面（Landing Page）"""
    return render_template('landing.html')
