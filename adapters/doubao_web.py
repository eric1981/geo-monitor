"""豆包适配器 — doubao.com/chat"""

from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth

from .base import BaseAdapter, AnswerResult

import asyncio
import time

_stealth = Stealth()


class DoubaoAdapter(BaseAdapter):
    """豆包网页版适配器

    策略：
    1. 导航到 doubao.com/chat
    2. 找到输入框，键入问题
    3. 发送并等待回答完成
    4. 提取回答 + 引用来源（豆包通常在回答末尾标注参考来源）
    """

    SEL_INPUT = 'textarea[placeholder*="发消息"], textarea[placeholder*="输入"], textarea:not([hidden])'
    SEL_SEND_BTN = 'button:has(svg), [class*="send"]'
    SEL_ANSWER = '[class*="message"], [class*="bubble"], [class*="answer"]'
    SEL_ANSWER_TEXT = '[class*="content"], [class*="text"], .markdown'
    SEL_CITATIONS = '[class*="reference"], [class*="source"], [class*="citation"], a[href^="http"]'
    SEL_STOP_BTN = 'button:has-text("停止"), [class*="stop"]'
    SEL_LOGIN_BTN = 'button:has-text("登录")'

    async def ask(self, question: str) -> AnswerResult:
        start = time.time()
        result = AnswerResult(success=False)
        pw = await async_playwright().start()
        context: BrowserContext | None = None

        _timeout_s = 120
        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,  # Doubao 反 headless 检测太严，强制可见
                viewport=self.viewport,
            )
            page = await context.new_page()
            result = await asyncio.wait_for(
                self._do_ask(page, question), timeout=_timeout_s
            )

        except asyncio.TimeoutError:
            result.error = f"查询超时 ({_timeout_s}s)"
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

        await page.goto(self.base_url, timeout=self.timeout_ms,
                        wait_until="domcontentloaded")
        await _stealth.apply_stealth_async(page)
        await self._wait_stable(page)

        if not await self._is_logged_in(page):
            result.error = "未登录，请先手动运行: python3 monitor.py login doubao"
            return result

        result.model_name = await self._extract_model(page)

        # 4. 记录发送前的回答文本
        old_text = await self._extract_answer(page)

        await self._type_question(page, question)
        await page.keyboard.press("Enter")

        answer_text, citations = await self._wait_answer(page, old_text)
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

    # —— 内部 ——

    async def _wait_stable(self, page: Page, seconds: float = 3.0):
        await asyncio.sleep(seconds)

    async def _is_logged_in(self, page: Page) -> bool:
        # 有输入框且没有登录按钮 = 已登录
        try:
            await page.wait_for_selector(self.SEL_INPUT, timeout=5000)
            login_btn = await page.query_selector(self.SEL_LOGIN_BTN)
            return login_btn is None
        except Exception:
            return False

    async def _extract_model(self, page: Page) -> str:
        try:
            el = await page.query_selector('[class*="model"]')
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return "unknown"

    async def _type_question(self, page: Page, question: str):
        inp = await page.wait_for_selector(self.SEL_INPUT, timeout=10000)
        await inp.click()
        await page.keyboard.type(question, delay=30)

    async def _wait_answer(self, page: Page, old_text: str = "") -> tuple[str, list[dict]]:
        """等待新回答出现并稳定"""
        for _ in range(15):
            await asyncio.sleep(2)
            current = await self._extract_answer(page)
            if current and current != old_text and len(current) > 20:
                break

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
        answers = await page.query_selector_all(self.SEL_ANSWER)
        if not answers:
            return await page.inner_text("body")

        last = answers[-1]
        try:
            content = await last.query_selector(self.SEL_ANSWER_TEXT)
            if content:
                return (await content.inner_text()).strip()
        except Exception:
            pass
        return (await last.inner_text()).strip()

    async def _extract_citations(self, page: Page) -> list[dict]:
        citations = []
        # 豆包的引用通常在回答末尾的「参考来源」区域
        ref_area = await page.query_selector('[class*="reference"], [class*="source"]')
        if ref_area:
            links = await ref_area.query_selector_all('a[href^="http"]')
        else:
            # fallback: 取所有外部链接
            # 只取最后一条回答区域内的链接
            answers = await page.query_selector_all(self.SEL_ANSWER)
            if answers:
                links = await answers[-1].query_selector_all('a[href^="http"]')
            else:
                links = []

        for link in links:
            try:
                url = await link.get_attribute("href")
                title = (await link.inner_text()).strip()
                if url and url.startswith("http"):
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    citations.append({
                        "url": url,
                        "title": title or "",
                        "domain": domain,
                        "snippet": ""
                    })
            except Exception:
                continue
        return citations
