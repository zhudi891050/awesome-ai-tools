#!/usr/bin/env python3
"""仅测试邮件发送"""
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).parent
env_path = ROOT / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

user = os.environ.get("EMAIL_USER", "zhudi891050@126.com")
passwd = os.environ.get("EMAIL_PASS", "")
msg = MIMEText("GEO cron 通知通道测试通过 ✅", "plain", "utf-8")
msg["Subject"] = "[GEO测试] 定时任务通知通道验证"
msg["From"] = user
msg["To"] = user

with smtplib.SMTP_SSL("smtp.126.com", 465, timeout=30) as s:
    s.login(user, passwd)
    s.send_message(msg)
print("ok")
