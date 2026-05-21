#!/usr/bin/env python3
"""GEO cron 通知脚本 — 运行任务并发送邮件通知"""
import os
import sys
import subprocess
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
VENV = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3"
CMD = sys.argv[1] if len(sys.argv) > 1 else "generate"

# 加载 .env
env_path = ROOT / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

os.makedirs(str(ROOT / "logs"), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ROOT / "logs" / f"cron_{CMD}.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")

def send_email(subject, body):
    user = os.environ.get("EMAIL_USER", "zhudi891050@126.com")
    passwd = os.environ.get("EMAIL_PASS", "")
    to = os.environ.get("REPORT_EMAIL", user)
    if not passwd:
        log("EMAIL_PASS 未配置，跳过邮件通知")
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    try:
        with smtplib.SMTP_SSL("smtp.126.com", 465, timeout=30) as s:
            s.login(user, passwd)
            s.send_message(msg)
        log("邮件通知发送成功")
        return True
    except Exception as e:
        log(f"邮件发送失败: {e}")
        return False

# 执行任务
log(f"开始执行 GEO {CMD}...")
result = subprocess.run(
    [str(VENV), str(ROOT / "run_geo.py"), CMD],
    capture_output=True, text=True, timeout=300
)
output = result.stdout + result.stderr
log(output)
log(f"退出码: {result.returncode}")

# 提取摘要
summary_lines = []
for line in output.split("\n"):
    if any(line.startswith(p) for p in ("✅", "📝", "📊", "❌", "[GEO]", "[RSS]", "[百度SiteMap]")):
        summary_lines.append(line.strip())
summary = "\n".join(summary_lines[:15])

# 发送邮件
status = "✅ 成功" if result.returncode == 0 else "❌ 失败"
date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
subject = f"[GEO] {CMD} {status} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
body = f"""GEO 定时任务报告
━━━━━━━━━━━━━━━━━━
任务: {CMD}
时间: {date_str}
状态: {status}

执行摘要:
{summary or '(无摘要)'}

完整日志: {ROOT / 'logs' / f'cron_{CMD}.log'}
"""

send_email(subject, body)
print(output)
sys.exit(result.returncode)
