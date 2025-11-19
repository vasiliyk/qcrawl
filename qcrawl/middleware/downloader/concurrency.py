import asyncio
import logging
from typing import TYPE_CHECKING

from qcrawl.middleware.base import DownloaderMiddleware, MiddlewareResult
from qcrawl.utils.url import get_domain

if TYPE_CHECKING:
    from qcrawl.core.request import Request
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)


class _DomainSlot:
    __slots__ = ("domain", "semaphore", "active")

    def __init__(self, domain: str, concurrency: int) -> None:
        self.domain = domain
        self.semaphore = asyncio.Semaphore(concurrency)
        self.active = 0

    async def acquire(self) -> None:
        await self.semaphore.acquire()
        self.active += 1

    def release(self) -> None:
        if self.active <= 0:
            logger.warning("Domain concurrency release underflow for %s", self.domain)
            self.active = 0
        else:
            self.active -= 1
        try:
            self.semaphore.release()
        except Exception:
            logger.exception("Domain semaphore.release() failed for %s", self.domain)


class ConcurrencyMiddleware(DownloaderMiddleware):
    """Per-domain concurrency semaphore middleware.

    Arguments:
        concurrency_per_domain: max concurrent requests per domain

    Notes:
      - Honors per-spider override `concurrency_per_domain` when present.
      - Resets internal slot table on spider open to avoid cross-run leakage.
    """

    def __init__(self, concurrency_per_domain: int = 2) -> None:
        try:
            val = int(concurrency_per_domain)
        except Exception:
            raise TypeError("concurrency_per_domain must be an int") from None
        if val < 1:
            raise ValueError("concurrency_per_domain must be >= 1")
        self._default_concurrency = val
        self._concurrency = val
        self._slots: dict[str, _DomainSlot] = {}

    def _domain_key(self, url: str) -> str:
        try:
            d = get_domain(url)
            return d or "default"
        except Exception:
            return "default"

    def _get_slot(self, url: str) -> _DomainSlot:
        key = self._domain_key(url)
        slot = self._slots.get(key)
        if slot is None:
            slot = _DomainSlot(key, self._concurrency)
            self._slots[key] = slot
        return slot

    async def process_request(self, request: "Request", spider: "Spider") -> MiddlewareResult:
        slot = self._get_slot(request.url)
        await slot.acquire()
        if request.meta is None:
            request.meta = {}
        request.meta["_domain_concurrency_key"] = slot.domain
        return MiddlewareResult.continue_()

    async def process_response(
        self, request: "Request", response, spider: "Spider"
    ) -> MiddlewareResult:
        meta = getattr(request, "meta", None)
        slot_key = None
        if isinstance(meta, dict):
            slot_key = meta.pop("_domain_concurrency_key", None)

        if isinstance(slot_key, str):
            slot = self._slots.get(slot_key)
            if slot:
                try:
                    slot.release()
                except Exception:
                    logger.exception("Failed to release domain concurrency slot %s", slot_key)
        return MiddlewareResult.keep(response)

    async def process_exception(
        self, request: "Request", exception, spider: "Spider"
    ) -> MiddlewareResult:
        meta = getattr(request, "meta", None)
        slot_key = None
        if isinstance(meta, dict):
            slot_key = meta.pop("_domain_concurrency_key", None)

        if isinstance(slot_key, str):
            slot = self._slots.get(slot_key)
            if slot:
                try:
                    slot.release()
                except Exception:
                    logger.exception(
                        "Failed to release domain concurrency slot %s on exception", slot_key
                    )
        return MiddlewareResult.continue_()

    async def open_spider(self, spider: "Spider") -> None:
        """Lifecycle hook: honor per-spider override and reset slots."""
        try:
            per_spider = getattr(spider, "concurrency_per_domain", None)
            if per_spider is not None:
                try:
                    per_spider_val = int(per_spider)
                    if per_spider_val >= 1:
                        self._concurrency = per_spider_val
                    else:
                        self._concurrency = self._default_concurrency
                except Exception:
                    self._concurrency = self._default_concurrency
            else:
                self._concurrency = self._default_concurrency

            # Reset slots to ensure a fresh semaphore pool for this spider run.
            self._slots = {}
            logger.debug(
                "ConcurrencyMiddleware opened for spider %s: concurrency_per_domain=%d",
                getattr(spider, "name", "<unknown>"),
                self._concurrency,
            )
        except Exception:
            logger.exception("Error in ConcurrencyMiddleware.open_spider")

    async def close_spider(self, spider: "Spider") -> None:
        """Lifecycle hook: log active slots and clear internal state."""
        try:
            active_slots = {k: v.active for k, v in self._slots.items() if v.active > 0}
            if active_slots:
                logger.debug(
                    "ConcurrencyMiddleware closing for %s; active slots remaining: %r",
                    getattr(spider, "name", "<unknown>"),
                    active_slots,
                )
            # Clear slots to allow GC and avoid cross-spider leakage
            self._slots = {}
        except Exception:
            logger.exception("Error in ConcurrencyMiddleware.close_spider")
