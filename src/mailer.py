"""可选的 SMTP 发信模块：未配置 SMTP_HOST 时整体处于关闭状态，不影响任何现有功能。"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from flask import current_app


def load_smtp_config():
    """从环境变量读取 SMTP 配置，供 create_app 写入 app.config。"""
    port_raw = (os.getenv("SMTP_PORT") or "").strip()
    security = (os.getenv("SMTP_SECURITY") or "").strip().lower()
    try:
        port = int(port_raw) if port_raw else 0
    except ValueError:
        port = 0
    if security not in {"ssl", "starttls", "none"}:
        security = "ssl" if port in (0, 465) else "starttls"
    if not port:
        port = {"ssl": 465, "starttls": 587, "none": 25}[security]
    user = (os.getenv("SMTP_USER") or "").strip()
    return {
        "SMTP_HOST": (os.getenv("SMTP_HOST") or "").strip(),
        "SMTP_PORT": port,
        "SMTP_SECURITY": security,
        "SMTP_USER": user,
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD") or "",
        "SMTP_FROM": (os.getenv("SMTP_FROM") or "").strip() or user,
        "SMTP_FROM_NAME": (os.getenv("SMTP_FROM_NAME") or "").strip() or "Media Parser",
    }


def smtp_configured():
    config = current_app.config
    return bool(config.get("SMTP_HOST") and config.get("SMTP_FROM"))


def send_mail(to_address, subject, body):
    """同步发送纯文本邮件，失败时抛出异常由调用方处理。"""
    config = current_app.config
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config.get("SMTP_FROM_NAME") or "Media Parser", config["SMTP_FROM"]))
    message["To"] = to_address
    message["Message-ID"] = make_msgid()
    message.set_content(body)

    host, port, security = config["SMTP_HOST"], config["SMTP_PORT"], config["SMTP_SECURITY"]
    context = ssl.create_default_context()
    if security == "ssl":
        client = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
    else:
        client = smtplib.SMTP(host, port, timeout=15)
    try:
        if security == "starttls":
            client.starttls(context=context)
        if config.get("SMTP_USER"):
            client.login(config["SMTP_USER"], config.get("SMTP_PASSWORD") or "")
        client.send_message(message)
    finally:
        try:
            client.quit()
        except Exception:
            pass
