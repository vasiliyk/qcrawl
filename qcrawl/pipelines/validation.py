import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from qcrawl.pipelines.base import DropItem, ItemPipeline

if TYPE_CHECKING:
    from qcrawl.core.item import Item
    from qcrawl.core.spider import Spider

logger = logging.getLogger(__name__)


class ValidationPipeline(ItemPipeline):
    """Validate presence of required fields on items.

    The spider may define `REQUIRED_FIELDS` as an iterable of field names
    (list/tuple/set). Items missing a required field or containing a
    falsy value for that field are dropped with a descriptive reason.
    """

    async def process_item(self, item: "Item", spider: "Spider") -> "Item":
        # Basic shape validation
        if not hasattr(item, "data"):
            logger.error("ValidationPipeline received object without .data: %r", item)
            raise DropItem("missing .data attribute")

        data = item.data
        if not isinstance(data, dict):
            logger.error("ValidationPipeline item.data is not a dict: %r", item)
            raise DropItem("invalid item.data type")

        required: Iterable[str] = getattr(spider, "REQUIRED_FIELDS", []) or []
        for field in required:
            if field not in data:
                logger.debug(
                    "ValidationPipeline: missing required field %s for item %r", field, item
                )
                raise DropItem(f"Missing required field: {field}")
            if not data[field]:
                logger.debug(
                    "ValidationPipeline: required field %s is empty/falsy for item %r", field, item
                )
                raise DropItem(f"Required field empty: {field}")

        return item


__all__ = ["ValidationPipeline"]
