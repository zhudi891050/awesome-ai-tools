"""知乎发布器 (修复版: 资源清理)

知乎是中国AI最重要的引用源之一，权重极高。
"""
import os
import json
import asyncio
from pathlib import Path
from .base import BasePublisher


class ZhihuPublisher(BasePublisher):
    """知乎内容发布"""

    def __init__(self, config):
        super().__init__("zhihu", config)
        pub_cfg = config.get("publishers", {}).get("zhihu", {})
        self.cookie_file = Path(__file__).parent.parent / pub_cfg.get(
            "cookie_file", "data/zhihu_cookie.json"
        )
        self._enabled = pub_cfg.get("enabled", False)
        self._headless = pub_cfg.get("headless", True)  # 默认无头模式
        self._playwright = None
        self._browser = None
        self._page = None

    @property
    def enabled(self):
        return self._enabled

    async def _init_browser(self):
        """初始化Playwright浏览器"""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )

                # 加载Cookie
                if self.cookie_file.exists():
                    cookies = json.loads(self.cookie_file.read_text())
                    await context.add_cookies(cookies)

                self._page = await context.new_page()
                print("[知乎] 浏览器已启动")

            except ImportError:
                print("[知乎] Playwright 未安装，使用模拟模式")
                self._enabled = False

    async def _save_cookies(self):
        """保存Cookie"""
        if self._page:
            cookies = await self._page.context.cookies()
            self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
            self.cookie_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))

    async def publish(self, content):
        """发布知乎文章"""
        if not self.enabled:
            return False, "知乎发布未启用"

        try:
            await self._init_browser()
            if not self._browser:
                return False, "浏览器初始化失败"

            title = content.get("title", "AI工具推荐")
            body = content.get("content", "")

            # 进入创作中心
            await self._page.goto("https://zhuanlan.zhihu.com/write")
            await asyncio.sleep(3)

            # 检查是否需要登录
            if "login" in self._page.url:
                print("[知乎] 需要登录，请手动扫码登录...")
                await self._page.wait_for_url("**/write**", timeout=120000)
                await self._save_cookies()

            # 填写标题
            title_input = await self._page.wait_for_selector(
                '[placeholder="请输入标题"]', timeout=10000
            )
            await title_input.fill(title)

            # 填写内容
            editor = await self._page.wait_for_selector(
                ".public-DraftEditor-content", timeout=10000
            )
            await editor.click()
            await self._page.keyboard.type(body[:1000])

            print(f"[知乎] 文章已填好，等待手动发布...")
            return True, f"https://zhuanlan.zhihu.com/p/draft"

        except Exception as e:
            return False, f"知乎发布失败: {str(e)}"

    async def close(self):
        """关闭浏览器（释放资源）"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._page = None
        self._playwright = None

    def __del__(self):
        """析构时同步清理（不依赖事件循环）"""
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is None:
                # 无运行中的事件循环，在新线程中清理
                import threading
                def _sync_close():
                    try:
                        new_loop = asyncio.new_event_loop()
                        new_loop.run_until_complete(self.close())
                        new_loop.close()
                    except Exception:
                        pass
                t = threading.Thread(target=_sync_close, daemon=True)
                t.start()
                t.join(timeout=5)
        except Exception:
            pass
