"""微信推送器 — 支持企业微信机器人和Server酱"""
import os
import httpx


class WeChatSender:
    """微信消息推送"""

    def __init__(self, config):
        report_cfg = config.get("report", {})

        # 企业微信机器人
        wechat_cfg = report_cfg.get("wechat", {})
        self.webhook_url = os.environ.get(
            "WECHAT_WEBHOOK_URL", wechat_cfg.get("webhook_url", "")
        )

        # Server酱（备用通道）
        serverchan_cfg = report_cfg.get("serverchan", {})
        self.serverchan_key = os.environ.get(
            "SERVERCHAN_SEND_KEY", serverchan_cfg.get("send_key", "")
        )

        self.brand = config.get("brand", {})
        self._enabled = bool(self.webhook_url or self.serverchan_key)

    @property
    def enabled(self):
        return self._enabled

    async def send(self, report):
        """发送日报到微信"""
        if not self.enabled:
            return False, "微信推送未配置"

        results = []

        # 优先使用企业微信机器人
        if self.webhook_url:
            result = await self._send_wework(report)
            results.append(("企业微信", result))

        # 备用Server酱
        if self.serverchan_key:
            result = await self._send_serverchan(report)
            results.append(("Server酱", result))

        if not results:
            return False, "无可用推送通道"

        ok_results = [msg for _, (ok, msg) in results if ok]
        fail_results = [msg for _, (ok, msg) in results if not ok]

        return (True, " | ".join(ok_results)) if ok_results else (False, " | ".join(fail_results))

    async def _send_wework(self, report):
        """企业微信机器人推送"""
        date = report.get("date", "")
        score = report.get("visibility_score", 0)
        change = report.get("score_change", 0)
        mentions = report.get("total_mentions", 0)
        queries = report.get("total_queries", 0)

        change_str = f"+{change}" if change > 0 else str(change)
        mention_rate = f"{mentions}/{queries}" if queries > 0 else "0/0"

        markdown = f"""## 📊 {self.brand.get('name', '新方舟AI')} AI可见度日报
> {date}

🎯 **AI可见度得分：{score}/100** ({change_str} vs 昨日)
📊 品牌提及：{mention_rate}
📈 趋势：持续监控中

[查看详情](https://{self.brand.get('domain', 'xinfangzhouai.com')}/geo-report)"""

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "markdown",
                        "markdown": {"content": markdown},
                    },
                )
                if resp.status_code == 200:
                    print("[微信] 企业微信推送成功")
                    return True, "企业微信推送成功"
                else:
                    return False, f"企业微信错误: {resp.status_code}"
        except Exception as e:
            return False, f"企业微信异常: {str(e)}"

    async def _send_serverchan(self, report):
        """Server酱推送（备用）"""
        date = report.get("date", "")
        score = report.get("visibility_score", 0)
        mentions = report.get("total_mentions", 0)
        queries = report.get("total_queries", 0)

        title = f"📊 {self.brand.get('name', '新方舟AI')} AI可见度日报"
        content = report.get("report_markdown", "")[:500]

        url = f"https://sctapi.ftqq.com/{self.serverchan_key}.send"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json={"title": title, "desp": content},
                )
                if resp.status_code == 200:
                    print("[Server酱] 推送成功")
                    return True, "Server酱推送成功"
                else:
                    return False, f"Server酱错误: {resp.status_code}"
        except Exception as e:
            return False, f"Server酱异常: {str(e)}"
