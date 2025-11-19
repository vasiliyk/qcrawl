import logging
from typing import TYPE_CHECKING

from .base import DropItem, ItemPipeline

if TYPE_CHECKING:
    from qcrawl.core.item import Item
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)


class DuplicateFilterPipeline(ItemPipeline):
    """Drop duplicate items based on configurable unique fields.

    By default the pipeline uses the `url` field to detect duplicates. Pass
    `key_fields` to compose a composite key from multiple item fields.
    """

    def __init__(self, key_fields: list[str] | None = None) -> None:
        self.seen: set[str] = set()
        self.key_fields = key_fields or ["url"]

    async def process_item(self, item: "Item", spider: "Spider") -> "Item":
        # Validate item shape
        if not hasattr(item, "data"):
            logger.error("DuplicateFilterPipeline received object without .data: %r", item)
            raise DropItem("missing .data attribute")

        item_data = item.data
        if not isinstance(item_data, dict):
            logger.error("DuplicateFilterPipeline item.data is not a dict: %r", item)
            raise DropItem("invalid item.data type")

        # Build unique id from configured key fields
        parts: list[str] = []
        for key in self.key_fields:
            val = item_data.get(key, "")
            parts.append("" if val is None else str(val))
        unique_id = "|".join(parts).strip()

        # If no identifying data, allow item through (do not drop)
        if not unique_id:
            logger.debug(
                "DuplicateFilterPipeline: no unique key for item, passing through: %r", item
            )
            return item

        # Drop duplicates
        if unique_id in self.seen:
            logger.debug("DuplicateFilterPipeline: dropping duplicate item %s", unique_id)
            raise DropItem(f"Duplicate item: {unique_id}")

        self.seen.add(unique_id)
        return item

    async def close_spider(self, spider: "Spider") -> None:
        """Clear seen cache when spider closes."""
        self.seen.clear()
