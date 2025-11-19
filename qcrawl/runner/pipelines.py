import contextlib
import logging

from qcrawl import signals
from qcrawl.pipelines.manager import PipelineManager

logger = logging.getLogger(__name__)


def wire_pipeline_manager(runtime_settings, crawler):
    """Create PipelineManager from runtime settings and wire lifecycle handlers on global dispatcher.
    Records handlers on crawler._cli_signal_handlers and attaches pipeline_mgr to crawler.
    """
    global_dispatcher = signals.signals_dispatcher
    crawler._cli_signal_handlers = getattr(crawler, "_cli_signal_handlers", [])

    pipeline_mgr = PipelineManager.from_settings(runtime_settings)

    async def _pm_open(sender, spider=None, **kwargs):
        try:
            await pipeline_mgr.open_spider(spider or sender)
        except Exception:
            logger.exception(
                "Error opening PipelineManager for %s", getattr(spider or sender, "name", None)
            )

    async def _pm_close(sender, spider=None, **kwargs):
        try:
            await pipeline_mgr.close_spider(spider or sender)
        except Exception:
            logger.exception(
                "Error closing PipelineManager for %s", getattr(spider or sender, "name", None)
            )

    global_dispatcher.connect("spider_opened", _pm_open, weak=False, priority=10)
    global_dispatcher.connect("spider_closed", _pm_close, weak=False)
    crawler._cli_signal_handlers.extend([("spider_opened", _pm_open), ("spider_closed", _pm_close)])

    crawler.pipeline_mgr = pipeline_mgr
    # compatibility helper if crawler implements wiring
    with contextlib.suppress(Exception):
        crawler.wire_pipeline_manager(pipeline_mgr)

    return pipeline_mgr
