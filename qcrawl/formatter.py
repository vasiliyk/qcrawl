import csv
import io

import lxml.etree as ET
import orjson


class BaseExporter:
    """Abstract base class for item exporters.

    Purpose:
        Defines the interface for all exporters that serialize scraped items
        to various output formats (e.g., JSON, CSV, XML).

    Methods:
        serialize_item(item):
            Serialize a single item to the target format.
            Must be implemented by subclasses.

        close():
            Finalize export and return any remaining serialized data (bytes or None).
            Must be implemented by subclasses.
    """

    def serialize_item(self, item):
        """Serialize a single item to the target format."""
        raise NotImplementedError

    def close(self):
        """Finalize export and return any remaining serialized data."""
        raise NotImplementedError


class JsonBufferedExporter(BaseExporter):
    """Buffered JSON exporter that accumulates items in a buffer and writes them as a JSON array.

    Args:
        buffer_size (int): Number of items to buffer before flushing.

    Behavior:
      - Items are buffered in-memory. When buffer reaches `buffer_size` it is
        serialized with `orjson.OPT_INDENT_2` for readable UTF-8 bytes.
      - `serialize_item` returns `None` while buffering; when a flush occurs it
        returns `bytes` to write.
      - `close()` flushes any remaining items and returns bytes (or b"" if none).
    """

    def __init__(self, buffer_size=500):
        self.buffer_size = int(buffer_size)
        self.buffer = []

    def serialize_item(self, item):
        data = item.data if hasattr(item, "data") else item
        self.buffer.append(data)
        if len(self.buffer) >= self.buffer_size:
            return self.flush()
        return None

    def flush(self):
        if not self.buffer:
            return b""
        # orjson.dumps returns bytes; use OPT_INDENT_2 for pretty printing
        out = orjson.dumps(self.buffer, option=orjson.OPT_INDENT_2) + b"\n"
        self.buffer.clear()
        return out

    def close(self):
        return self.flush()


class JsonLinesExporter(BaseExporter):
    """NDJSON exporter (one JSON object per line).

    Behavior:
      - Each `serialize_item` call returns a single newline-terminated JSON line as bytes.
      - `close()` is a no-op and returns empty bytes.
    """

    def serialize_item(self, item):
        data = item.data if hasattr(item, "data") else item
        return orjson.dumps(data) + b"\n"

    def close(self):
        return b""


class CsvExporter(BaseExporter):
    """CSV exporter that writes items as rows to a CSV file.

    Attributes:
        header_written (bool): Whether the header row has been written.
        writer (csv.DictWriter): CSV writer instance.
        output (io.StringIO): In-memory output buffer.

    Methods:
        serialize_item(item) -> bytes
            Write item as a CSV row and return bytes.
        close() -> bytes
            No-op; returns empty bytes.
    """

    def __init__(self):
        self.header_written = False
        self.writer = None
        self.output = io.StringIO()

    def serialize_item(self, item):
        data = item.data if hasattr(item, "data") else item
        if not self.writer:
            self.writer = csv.DictWriter(self.output, fieldnames=list(data.keys()))
            if not self.header_written:
                self.writer.writeheader()
                self.header_written = True
        self.writer.writerow(data)
        value = self.output.getvalue()
        self.output.seek(0)
        self.output.truncate(0)
        return value.encode("utf-8")

    def close(self):
        return b""


class XmlExporter(BaseExporter):
    """XML exporter that accumulates items and writes them as XML elements.

    Behavior:
      - Items are collected in-memory and emitted as an XML document on `close()`.
      - `serialize_item` returns None while accumulating.
      - `close()` returns UTF-8 encoded XML bytes (pretty-printed using lxml).
    """

    def __init__(self):
        self.items = []

    def serialize_item(self, item):
        data = item.data if hasattr(item, "data") else item
        self.items.append(data)
        return None

    def close(self):
        root = ET.Element("items")
        for data in self.items:
            item_elem = ET.SubElement(root, "item")
            for k, v in data.items():
                child = ET.SubElement(item_elem, str(k))
                child.text = "" if v is None else str(v)
        return ET.tostring(root, encoding="utf-8", pretty_print=True)
