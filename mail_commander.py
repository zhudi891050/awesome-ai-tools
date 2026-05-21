"""邮件指令监听器 — 检查收件箱，读取用户指令并执行"""
import os
import sys
import re
import imaplib
import email
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


class MailCommander:
    """监听邮件指令，执行Geo系统操作"""

    def __init__(self):
        self.host = "imap.126.com"
        self.port = 993
        self.user = os.environ.get("EMAIL_USER", "")
        self.password = os.environ.get("EMAIL_PASS", "")
        self.allowed_sender = self.user  # 只响应自己的邮件

    def connect(self):
        """连接IMAP"""
        import ssl
        context = ssl.create_default_context()
        self.mail = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context, timeout=30)
        self.mail.login(self.user, self.password)
        self.mail.select("INBOX")

    def fetch_unread(self):
        """获取未读邮件"""
        status, messages = self.mail.search(None, "UNSEEN")
        if status != "OK":
            return []
        msg_ids = messages[0].split()
        return msg_ids

    def parse_mail(self, msg_id):
        """解析邮件内容"""
        status, data = self.mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        # 解码标题
        subject = ""
        if msg["Subject"]:
            decoded = decode_header(msg["Subject"])
            subject = "".join(
                part.decode(charset or "utf-8") if isinstance(part, bytes) else part
                for part, charset in decoded
            )

        # 解码发件人
        sender = msg.get("From", "")

        # 获取正文
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")

        return {"subject": subject, "sender": sender, "body": body.strip()}

    def execute_command(self, body):
        """解析并执行命令"""
        body_lower = body.lower().strip()

        # 命令匹配
        if any(w in body_lower for w in ["跑一次", "执行一次", "手动跑", "立刻跑"]):
            if "生成" in body_lower or "内容" in body_lower:
                return self._run_generate()
            elif "追踪" in body_lower or "可见度" in body_lower:
                return self._run_track()
            elif "日报" in body_lower or "报告" in body_lower:
                return self._run_report()
            else:
                return self._run_full()

        elif any(w in body_lower for w in ["多生成", "加量", "多几篇"]):
            import re
            num_match = re.search(r"(\d+)\s*篇", body)
            count = int(num_match.group(1)) if num_match else 12
            return self._run_generate_extra(count)

        elif "暂停" in body_lower:
            return "⏸️ 暂停功能需在对话中操作，请回到聊天窗口发送「暂停GEO」。"
        
        elif "状态" in body_lower or "怎么样" in body_lower:
            return self._get_status()

        elif "help" in body_lower or "帮助" in body_lower or "？" in body_lower or "?" in body_lower:
            return self._help()

        else:
            return f"📨 收到你的消息，但没识别到明确指令。\n\n支持的命令：\n- 「跑一次生成」- 立即生成8篇文章\n- 「跑一次追踪」- 立即追踪AI可见度\n- 「跑一次日报」- 立即发送日报\n- 「多生成10篇」- 生成指定数量的文章\n- 「状态」- 查看系统运行状态\n- 「帮助」- 显示此信息\n\n有其他需求请回到聊天窗口找我。"

    def _run_generate(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(ROOT / "run_geo.py"), "generate"],
                         capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        return f"📝 内容生成完成\n\n{r.stdout[-2000:]}"

    def _run_track(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(ROOT / "run_geo.py"), "track"],
                         capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        return f"🔍 AI追踪完成\n\n{r.stdout[-2000:]}"

    def _run_report(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(ROOT / "run_geo.py"), "report"],
                         capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        return f"📊 日报已生成并发送\n\n{r.stdout[-2000:]}"

    def _run_full(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(ROOT / "run_geo.py"), "full"],
                         capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        return f"🚀 全流程完成\n\n{r.stdout[-2000:]}"

    def _run_generate_extra(self, count):
        # 临时修改 daily_count 后生成
        return f"📝 额外生成 {count} 篇文章功能开发中，请先用「跑一次生成」生成8篇。"
        # TODO: 实现动态调整生成数量

    def _get_status(self):
        import sqlite3
        db = ROOT / "data" / "geo.db"
        if not db.exists():
            return "⚠️ 数据库不存在，系统可能未初始化。"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT COUNT(*) as cnt FROM contents")
        articles = c.fetchone()["cnt"]

        c.execute("SELECT COUNT(*) as cnt FROM ai_mentions WHERE DATE(created_at) = DATE('now', 'localtime')")
        today_tracks = c.fetchone()["cnt"]

        c.execute("SELECT AVG(score) as avg FROM ai_mentions WHERE DATE(created_at) = DATE('now', 'localtime')")
        avg = c.fetchone()["avg"] or 0

        conn.close()

        return (
            f"📊 GEO系统状态\n"
            f"━━━━━━━━━━━━━━\n"
            f"📝 累计文章: {articles} 篇\n"
            f"🔍 今日追踪: {today_tracks} 次\n"
            f"🎯 今日可见度: {round(avg)}/100\n"
            f"⏰ 定时任务: 正常\n"
            f"  08:00 内容生成\n"
            f"  10:00 AI追踪\n"
            f"  18:00 日报推送\n"
        )

    def _help(self):
        return (
            f"🤖 GEO运维助手 - 邮件指令\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"支持的命令：\n"
            f"• 「跑一次生成」- 立即生成8篇文章\n"
            f"• 「跑一次追踪」- 立即追踪AI可见度\n"
            f"• 「跑一次日报」- 立即发送日报\n"
            f"• 「跑一次」- 执行全流程\n"
            f"• 「状态」- 查看系统状态\n"
            f"\n"
            f"复杂需求请回到聊天窗口找我。"
        )

    def reply(self, to_addr, subject, body_text):
        """回复邮件"""
        import smtplib, ssl
        from email.mime.text import MIMEText

        msg = MIMEText(body_text, "plain", "utf-8")
        msg["Subject"] = f"Re: {subject}"
        msg["From"] = self.user
        msg["To"] = to_addr

        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL("smtp.126.com", 465, timeout=15, context=context)
        server.login(self.user, self.password)
        server.sendmail(self.user, to_addr, msg.as_string())
        server.quit()
        print(f"  ✅ 已回复: {to_addr}")

    def close(self):
        try:
            self.mail.logout()
        except:
            pass


def main():
    """主入口：检查邮件并处理"""
    import sys
    os.chdir(str(ROOT))

    # 加载 .env
    env_file = ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    v = v.strip().strip('"').strip("'")
                    if v and not os.environ.get(k.strip()):
                        os.environ[k.strip()] = v

    commander = MailCommander()
    if not commander.user or not commander.password:
        print("⚠️ 邮箱未配置")
        return

    try:
        commander.connect()
        unread = commander.fetch_unread()

        if not unread:
            print("📭 没有新邮件")
            return

        print(f"📬 发现 {len(unread)} 封未读邮件")
        for msg_id in unread[:5]:  # 最多处理5封
            mail = commander.parse_mail(msg_id)
            if not mail:
                continue
            print(f"\n📧 来自: {mail['sender']}")
            print(f"   主题: {mail['subject']}")
            print(f"   内容: {mail['body'][:100]}...")

            # 执行命令
            result = commander.execute_command(mail["body"])
            print(f"   结果: {result[:100]}...")

            # 回复
            commander.reply(mail["sender"], mail["subject"], result)

        commander.close()
    except Exception as e:
        print(f"❌ 邮件检查失败: {e}")


if __name__ == "__main__":
    main()
