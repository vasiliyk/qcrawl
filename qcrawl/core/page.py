"""Browser page interaction utilities for qCrawl."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PageMethod:
    """Represents a method to execute on a browser page.

    PageMethod allows you to perform actions on browser pages before or after navigation,
    such as clicking elements, waiting for selectors, taking screenshots, or executing
    custom JavaScript.

    Examples:
        Simple click::

            PageMethod("click", "#button")

        With keyword arguments::

            PageMethod("screenshot", path="/tmp/page.png", full_page=True)

        Execute before navigation::

            PageMethod("evaluate", "navigator.webdriver = false", timing="before")

        Wait for element::

            PageMethod("wait_for_selector", ".quote", timing="after")

        Multiple actions in sequence::

            yield Request(url, meta={
                "camoufox_page_methods": [
                    PageMethod("wait_for_selector", "h1"),
                    PageMethod("evaluate", "window.scrollTo(0, 500)"),
                    PageMethod("wait_for_timeout", 1000),
                ]
            })

    Note:
        For complex custom logic, use ``camoufox_include_page=True`` to get
        direct access to the page object in your parse method.

    Attributes:
        method: Method name (e.g., "click", "wait_for_selector", "evaluate")
        args: Positional arguments to pass to the method
        kwargs: Keyword arguments to pass to the method
        timing: When to execute - "before" navigation or "after" (default: "after")
        result: Result returned by the method (set after execution)
    """

    method: str
    args: tuple[object, ...] = field(default_factory=tuple)
    kwargs: dict[str, object] = field(default_factory=dict)
    timing: str = "after"
    result: object = field(default=None, init=False, repr=False)

    def __init__(
        self,
        method: str,
        *args: object,
        timing: str = "after",
        **kwargs: object,
    ):
        """Create a PageMethod.

        Args:
            method: Method name (e.g., "click", "screenshot", "evaluate")
            *args: Positional arguments for the method
            timing: When to execute ("before" or "after" navigation)
            **kwargs: Keyword arguments for the method

        Raises:
            ValueError: If timing is not "before" or "after"
            TypeError: If method is not a string

        Example:
            >>> PageMethod("click", "#submit-btn")
            PageMethod(method='click', args=('#submit-btn',), timing='after')

            >>> PageMethod("screenshot", path="/tmp/page.png", full_page=True)
            PageMethod(method='screenshot', kwargs={'path': '/tmp/page.png', 'full_page': True})
        """
        if not isinstance(method, str):
            raise TypeError(
                f"PageMethod.method must be a string, got {type(method).__name__}. "
                f"Custom callables are not supported. Use camoufox_include_page=True "
                f"for custom page interactions."
            )

        if timing not in ("before", "after"):
            raise ValueError(f"timing must be 'before' or 'after', got {timing!r}")

        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.timing = timing
        self.result = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dict for serialization/config files.

        Returns:
            Dictionary representation suitable for JSON/TOML serialization

        Example:
            >>> method = PageMethod("click", "#button", timing="after")
            >>> method.to_dict()
            {'method': 'click', 'timing': 'after', 'args': ['#button']}
        """
        result: dict[str, object] = {
            "method": self.method,
            "timing": self.timing,
        }
        if self.args:
            result["args"] = list(self.args)
        if self.kwargs:
            result["kwargs"] = self.kwargs
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PageMethod:
        """Create PageMethod from dict (for loading from config files).

        Args:
            data: Dictionary with 'method', optional 'args', 'kwargs', 'timing'

        Returns:
            PageMethod instance

        Example:
            >>> data = {"method": "click", "args": ["#button"], "timing": "after"}
            >>> PageMethod.from_dict(data)
            PageMethod(method='click', args=('#button',), timing='after')
        """
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        timing = data.get("timing", "after")

        # Validate and normalize types
        if not isinstance(args, list):
            args = []
        if not isinstance(kwargs, dict):
            kwargs = {}
        if not isinstance(timing, str) or timing not in ("before", "after"):
            timing = "after"

        return cls(
            data["method"],  # type: ignore[arg-type]
            *args,
            timing=timing,
            **kwargs,
        )
