"""邮件发送器 — 通过SMTP发送日报"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class EmailSender:
    """日报邮件发送"""

    def __init__(self, config):
        email_cfg = config.get("report", {}).get("email", {})
        self.smtp_host = email_cfg.get("smtp_host", "smtp.qq.com")
        self.smtp_port = int(email_cfg.get("smtp_port", 587))
        self.smtp_user = os.environ.get("EMAIL_USER", email_cfg.get("smtp_user", ""))
        self.smtp_pass = os.environ.get("EMAIL_PASS", email_cfg.get("smtp_pass", ""))
        self.to_email = os.environ.get("REPORT_EMAIL", email_cfg.get("to", ""))
        self.brand = config.get("brand", {})
        self._enabled = bool(self.smtp_user and self.smtp_pass and self.to_email)
        self._use_ssl = self.smtp_port == 465  # 465端口用SSL直连

    @property
    def enabled(self):
        return self._enabled

    def send(self, report):
        """发送日报邮件"""
        if not self.enabled:
            return False, "邮件未配置（需设置 EMAIL_USER, EMAIL_PASS, REPORT_EMAIL）"

        date = report.get("date", datetime.now().strftime("%Y-%m-%d"))
        subject = f"📊 {self.brand.get('name', '新方舟AI')} AI可见度日报 - {date}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.to_email

        # 纯文本版
        text_content = report.get("report_markdown", "")
        msg.attach(MIMEText(text_content, "plain", "utf-8"))

        # HTML版
        html_content = report.get("report_html", "")
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            if self._use_ssl:
                import ssl
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30, context=context)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, self.to_email, msg.as_string())
            server.quit()
            print(f"[Email] 日报已发送到 {self.to_email}")
            return True, f"已发送到 {self.to_email}"
        except Exception as e:
            print(f"[Email] 发送失败: {e}")
            return False, str(e)


def test_send():
    """测试邮件发送"""
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    from .report_generator import ReportGenerator

    gen = ReportGenerator(config)
    report = gen.generate()

    sender = EmailSender(config)
    success, msg = sender.send(report)
    print(f"Result: {success}, {msg}")


if __name__ == "__main__":
    test_send()
