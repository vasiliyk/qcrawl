import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qcrawl.core.item import Item
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)


class DropItem(Exception):
    """Raised to drop an item from the pipeline."""

    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason

    def __repr__(self) -> str:
        return f"DropItem(reason={self.reason!r})"

    def __str__(self) -> str:
        return f"DropItem: {self.reason or 'no reason'}"


class ItemPipeline:
    """Base item pipeline for processing scraped items.

    Subclasses should override `process_item` (async). `process_item` must
    return the item (possibly transformed) or raise `DropItem` to discard it.
    `open_spider` and `close_spider` are async lifecycle hooks.
    """

    async def process_item(self, item: "Item", spider: "Spider") -> "Item":
        """Process an item.

        Default implementation performs a sanity check and returns the item unchanged.

        Raises:
            DropItem: if the item is invalid and should be discarded.
        """
        if not hasattr(item, "data"):
            logger.error("Pipeline received object without .data: %r", item)
            raise DropItem("missing .data attribute")
        return item

    async def open_spider(self, spider: "Spider") -> None:
        """Called when a spider is opened. Override to allocate resources."""
        return None

    async def close_spider(self, spider: "Spider") -> None:
        """Called when a spider is closed. Override to release resources."""
        return None


__all__ = ["DropItem", "ItemPipeline"]
