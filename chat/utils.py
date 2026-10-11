import zlib


def crc32_hex(content: str) -> str:
    """CRC32 of the UTF-8 message body as 8 hex chars. Shared with the UCP layer."""
    return format(zlib.crc32(content.encode('utf-8')) & 0xFFFFFFFF, '08x')
