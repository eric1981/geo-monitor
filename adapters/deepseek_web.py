"""DeepSeek Web 适配器 — chat.deepseek.com"""

import asyncio
import time
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth

from .base import BaseAdapter, AnswerResult

# 全局 stealth 实例
_stealth = Stealth()


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek 网页版适配器

    策略：
    1. 导航到 chat.deepseek.com
    2. 找到输入框，键入问题
    3. 按 Enter 发送
    4. 等待回答完成（新消息出现 + 停止按钮消失）
    5. 提取回答文本 + 引用来源
    """

    # —— CSS 选择器（需 F12 验证） ——
    SEL_INPUT = 'textarea[placeholder*="Message"], textarea[placeholder*="DeepSeek"], textarea[placeholder*="输入"], textarea:not([hidden]), [class*="chat"] textarea'
    SEL_ANSWER = '[class*="assistant"], [class*="ds-message"]:has([class*="markdown"])'
    SEL_ANSWER_TEXT = '[class*="assistant-message-main-content"], .ds-markdown:not(.ds-markdown-cite)'
    SEL_CITATIONS = '[class*="assistant"] a[href^="http"], [class*="ds-message"] a[href^="http"]'
    SEL_STOP_BTN = 'button:has-text("停止"), [data-testid="stop-button"]'
    SEL_MODEL = '[class*="model"], [class*="Model"]'

    async def ask(self, question: str) -> AnswerResult:
        start = time.time()
        result = AnswerResult(success=False)

        pw = await async_playwright().start()
        context: BrowserContext | None = None

        try:
            # 启动持久化浏览器
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                viewport=self.viewport,
            )
            page = await context.new_page()

            # 全局超时 90s 防卡死
            timeout = max(self.timeout_ms, self.answer_wait_ms) * 2 // 1000 + 30
            result = await asyncio.wait_for(
                self._do_ask(page, question), timeout=timeout
            )

        except asyncio.TimeoutError:
            result.error = f"查询超时 ({timeout}s)"
        except Exception as e:
            result.error = str(e)
        finally:
            if context:
                await context.close()
            await pw.stop()

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    async def _do_ask(self, page: Page, question: str) -> AnswerResult:
        result = AnswerResult(success=False)

        print(f"  [debug] 1.goto...", flush=True)
        await page.goto(self.base_url, timeout=self.timeout_ms,
                        wait_until="domcontentloaded")
        await _stealth.apply_stealth_async(page)
        print(f"  [debug] 2.stable...", flush=True)
        await self._wait_stable(page)

        print(f"  [debug] 3.login...", flush=True)
        if not await self._is_logged_in(page):
            result.error = "未登录，请先手动运行: python3 monitor.py login deepseek"
            return result

        print(f"  [debug] 4.model...", flush=True)
        result.model_name = await self._extract_model(page)

        print(f"  [debug] 5.old_text...", flush=True)
        old_text = await self._extract_answer(page)
        print(f"  [debug]   old={len(old_text)}c", flush=True)

        print(f"  [debug] 6.type...", flush=True)
        await self._type_question(page, question)
        print(f"  [debug] 7.enter...", flush=True)
        await page.keyboard.press("Enter")

        print(f"  [debug] 8.wait_answer...", flush=True)
        answer_text, citations = await self._wait_answer(page, old_text)
        print(f"  [debug] 9.done: ans={len(answer_text)}c cit={len(citations)}", flush=True)
        result.answer_text = answer_text
        result.citations = citations
        result.success = True
        return result
    async def login_if_needed(self) -> bool:
        """打开浏览器让用户手动登录 — 登录完成后按 Enter"""
        pw = await async_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=False,
            viewport=self.viewport,
        )
        page = await context.new_page()
        await page.goto(self.base_url, timeout=self.timeout_ms,
                        wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # 简单检测：如果没有登录按钮，可能已登录
        try:
            login_btn = await page.query_selector('button:has-text("登录"), [class*="login"]')
            if login_btn is None:
                print(f"[{self.name}] 检测到登录态，可能已登录。如需重新登录请先清除 sessions/{self.name}/")
        except Exception:
            pass

        print(f"[{self.name}] 请在打开的浏览器窗口中完成登录（扫码/手机号）")
        print(f"登录完成后回到此处按 Enter 继续...")
        await asyncio.get_event_loop().run_in_executor(None, input, "")

        print(f"[{self.name}] 会话已保存到 {self.profile_dir}")
        await context.close()
        await pw.stop()
        return True

    # —— 内部方法 ——

    async def _wait_stable(self, page: Page, seconds: float = 2.0):
        """等待页面 JS 初始化完成"""
        await asyncio.sleep(seconds)

    async def _is_logged_in(self, page: Page) -> bool:
        """检测是否已登录：有输入框且无登录按钮"""
        try:
            inp = await page.query_selector(self.SEL_INPUT)
            if not inp:
                return False
            # 检查是否有登录按钮（有的话说明未登录）
            login_btn = await page.query_selector(
                'button:has-text("登录"), a:has-text("登录"), [class*="login-btn"]'
            )
            return login_btn is None
        except Exception:
            return False

    async def _extract_model(self, page: Page) -> str:
        """提取当前使用的模型名称"""
        try:
            el = await page.query_selector(self.SEL_MODEL)
            if el:
                text = await el.inner_text()
                return text.strip()
        except Exception:
            pass
        return "unknown"

    async def _type_question(self, page: Page, question: str):
        """找到输入框并用 keyboard.type 输入（触发 React onChange）"""
        inp = await page.wait_for_selector(self.SEL_INPUT, timeout=10000)
        await inp.click()
        await page.keyboard.type(question, delay=30)

    async def _wait_answer(self, page: Page, old_text: str = "") -> tuple[str, list[dict]]:
        """等待新回答出现并稳定"""
        print(f"    [wait] old={len(old_text)}c, polling...", flush=True)
        for i in range(15):
            await asyncio.sleep(2)
            current = await self._extract_answer(page)
            changed = current != old_text
            if i == 0 or changed:
                print(f"    [wait]   {i*2}s: len={len(current)} changed={changed}", flush=True)
            if current and changed and len(current) > 20:
                print(f"    [wait] new answer detected!", flush=True)
                break

        # 等待文本稳定
        last_text = ""
        stable_count = 0
        for _ in range(15):
            await asyncio.sleep(2)
            current = await self._extract_answer(page)
            if current == last_text and len(current) > 20:
                stable_count += 1
                if stable_count >= 2:
                    break
            else:
                stable_count = 0
            last_text = current

        answer_text = await self._extract_answer(page)
        citations = await self._extract_citations(page)
        return answer_text, citations

    async def _extract_answer(self, page: Page) -> str:
        """提取最新一条 AI 回答"""
        # 优先取 assistant-message-main-content
        content = await page.query_selector('[class*="assistant-message-main-content"]')
        if content:
            return (await content.inner_text()).strip()

        # fallback: 最后一条 assistant 消息
        answers = await page.query_selector_all(self.SEL_ANSWER)
        if answers:
            last = answers[-1]
            text_el = await last.query_selector(self.SEL_ANSWER_TEXT)
            if text_el:
                return (await text_el.inner_text()).strip()
            return (await last.inner_text()).strip()

        return (await page.inner_text("body")).strip()

    async def _extract_citations(self, page: Page) -> list[dict]:
        """提取回答中的引用链接（去重）"""
        from urllib.parse import urlparse
        seen = set()
        citations = []
        # 从最后一条 assistant 消息中取引用链接
        links = await page.query_selector_all(
            '[class*="assistant"] a[href^="http"], [class*="ds-message"] a[href^="http"]'
        )
        if not links:
            links = await page.query_selector_all('a[href^="http"]')

        for link in links:
            try:
                url = await link.get_attribute("href")
                if not url or url in seen:
                    continue
                if "deepseek.com" in url or url == self.base_url:
                    continue
                seen.add(url)
                title = (await link.inner_text()).strip().replace("\n", " ")
                domain = urlparse(url).netloc
                citations.append({
                    "url": url,
                    "title": title or domain,
                    "domain": domain,
                    "snippet": ""
                })
            except Exception:
                continue
        return citations

    async def _page_text(self, page: Page) -> str:
        return (await page.inner_text("body")).strip()
