#!/bin/bash
# GEO任务执行+邮件通知包装脚本
# 用法: ./run_and_notify.sh <generate|track|report>

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="/home/judy/.hermes/hermes-agent/venv/bin/python3"
CMD="$1"
LOG="$ROOT/logs/cron_${CMD}.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$ROOT/logs"

# 加载 .env
export $(grep -v '^\s*#' "$ROOT/.env" | grep -v '^\s*$' | xargs)

echo "[$TIMESTAMP] 开始执行 GEO $CMD ..." >> "$LOG"

# 执行任务
OUTPUT=$($VENV "$ROOT/run_geo.py" "$CMD" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT" >> "$LOG"
echo "[$TIMESTAMP] 退出码: $EXIT_CODE" >> "$LOG"

# 提取摘要（首几行有用信息）
SUMMARY=$(echo "$OUTPUT" | grep -E '^(✅|📝|📊|❌|\[GEO\])' | head -10 | tr '\n' '; ')

# 发送邮件通知
SUBJECT="[GEO] ${CMD} 任务完成 - $(date '+%Y-%m-%d %H:%M')"
BODY="任务: GEO $CMD
时间: $TIMESTAMP
状态: $([ $EXIT_CODE -eq 0 ] && echo '成功' || echo '失败')
退出码: $EXIT_CODE

执行摘要:
$SUMMARY

完整日志: $LOG"

# 使用Python发送邮件
$VENV -c "
import smtplib
from email.mime.text import MIMEText

user = '$EMAIL_USER'
passwd = '$EMAIL_PASS'
to = '$REPORT_EMAIL' or '$EMAIL_USER'

msg = MIMEText('''$BODY''', 'plain', 'utf-8')
msg['Subject'] = '$SUBJECT'
msg['From'] = user
msg['To'] = to

try:
    with smtplib.SMTP_SSL('smtp.126.com', 465, timeout=30) as s:
        s.login(user, passwd)
        s.send_message(msg)
    print('邮件发送成功')
except Exception as e:
    print(f'邮件发送失败: {e}')
" >> "$LOG" 2>&1

exit $EXIT_CODE
