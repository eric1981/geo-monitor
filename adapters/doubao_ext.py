"""豆包适配器 — Chrome Extension + Native Messaging"""

import asyncio
import json
import subprocess
import time
from pathlib import Path

from .base import BaseAdapter, AnswerResult

CLI = Path(__file__).parent.parent / 'native-host' / 'doubao_cli.py'


class DoubaoExtAdapter(BaseAdapter):
    """通过 Chrome 扩展（Native Messaging）操作真实浏览器"""

    def __init__(self, **kwargs):
        super().__init__(
            name="豆包",
            base_url="https://www.doubao.com/chat/",
            profile_dir="sessions/doubao",
        )

    async def ask(self, question: str) -> AnswerResult:
        start = time.time()
        result = AnswerResult(success=False)

        try:
            cmd = json.dumps({
                "action": "geo_query",
                "question": question,
                "_id": str(int(time.time() * 1000)),
            }, ensure_ascii=False)

            proc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ['python3', str(CLI), cmd],
                    capture_output=True, text=True, timeout=200,
                )
            )

            if proc.returncode != 0:
                result.error = f"CLI error: {proc.stderr.strip()}"
                result.duration_ms = int((time.time() - start) * 1000)
                return result

            resp = json.loads(proc.stdout.strip())

            if resp.get('success'):
                result.success = True
                result.answer_text = resp.get('answer_text', '')
                result.citations = resp.get('citations', [])
                result.model_name = resp.get('model_name', 'doubao')
            else:
                result.error = resp.get('error') or resp.get('message') or 'Unknown'

        except subprocess.TimeoutExpired:
            result.error = "CLI timeout (200s)"
        except json.JSONDecodeError as e:
            result.error = f"Invalid response: {e}"
        except Exception as e:
            result.error = str(e)

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    async def login_if_needed(self) -> bool:
        print("[豆包] 请在 Chrome 中打开 https://www.doubao.com/chat/ 并登录")
        print("登录完成后按 Enter 继续...")
        await asyncio.get_event_loop().run_in_executor(None, input, "")
        return True
