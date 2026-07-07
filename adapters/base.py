"""平台适配器抽象基类

每个 AI 平台继承此类，实现：
  - ask(question: str) -> AnswerResult
  - login_if_needed()          登录检测与引导
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnswerResult:
    """一次查询的结果"""
    success: bool
    answer_text: str = ""
    model_name: str = ""
    citations: list[dict] = field(default_factory=list)  # [{url, title, domain, snippet}]
    error: str = ""
    duration_ms: int = 0


class BaseAdapter:
    """所有平台适配器的基类"""

    def __init__(self, name: str, base_url: str, profile_dir: str,
                 headless: bool = True, viewport: dict | None = None,
                 timeout_ms: int = 60000, answer_wait_ms: int = 30000):
        self.name = name
        self.base_url = base_url
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.timeout_ms = timeout_ms
        self.answer_wait_ms = answer_wait_ms

    async def ask(self, question: str) -> AnswerResult:
        """提问并获取回答（子类必须实现）"""
        raise NotImplementedError

    async def login_if_needed(self) -> bool:
        """检测是否需要登录，如果需要则引导用户登录。
        返回 True 表示登录态正常/已完成。"""
        raise NotImplementedError

    async def close(self):
        """清理资源"""
        pass
