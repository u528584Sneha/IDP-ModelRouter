"""
Common utilities for the Image Model Routing tool.

Image detection + dimension sniffing + token estimation, ported from
llm-router-platform's app/services/attachments.py (AttachmentProcessor).
Dimensions are read directly from PNG/JPEG headers (no Pillow dependency),
purely for token-budget estimation -- the image bytes themselves are never
decoded, resized, or recompressed here.
"""
import struct
import sys
import os
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from helper.config_loader import get_config, load_config_for_file

load_config_for_file(__file__)
config = get_config(__file__, validation_level="tool")

_DEBUG = False

def _debug(*args, **kwargs):
    """Print debug output to stderr only when debug mode is enabled"""
    if _DEBUG:
        print(*args, file=sys.stderr, **kwargs)


def image_dimensions(data: bytes, ext: str) -> Optional[Tuple[int, int]]:
    """Sniff (width, height) from raw PNG/JPEG bytes without decoding the image."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            # IHDR chunk: width/height are 4-byte big-endian ints at offset 16/20
            width, height = struct.unpack(">II", data[16:24])
            return width, height

        if data[:2] == b"\xff\xd8":
            # JPEG: scan markers for an SOF (Start Of Frame) segment
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    height, width = struct.unpack(">HH", data[i + 5:i + 9])
                    return width, height
                if marker in (0xD8, 0xD9):
                    i += 2
                    continue
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg_len
            return None

        return None
    except (struct.error, IndexError):
        return None


def estimate_image_tokens(data: Optional[bytes], ext: str) -> Tuple[int, Optional[Tuple[int, int]]]:
    """
    Estimate vision-model input tokens for an image, OpenAI-tile-style.
    Returns (estimated_tokens, (width, height) or None).
    """
    tile_px = config.get_int("IMR_TOKEN_TILE_PX", 512)
    base = config.get_int("IMR_TOKEN_BASE", 85)
    per_tile = config.get_int("IMR_TOKEN_PER_TILE", 170)
    default_tokens = config.get_int("IMR_DEFAULT_TOKEN_ESTIMATE", 512)

    _debug("=== IMAGE TOKEN ESTIMATION ===")
    _debug(f"Config: tile_size={tile_px}px, base_tokens={base}, per_tile={per_tile}")

    dims = image_dimensions(data, ext) if data else None
    if dims:
        width, height = dims
        _debug(f"Image dimensions: {width}x{height} px")

        total_pixels = width * height
        tile_size_pixels = tile_px * tile_px
        tiles = max(1, total_pixels // tile_size_pixels)

        _debug(f"Formula: tokens = base + (pixels / tile_size) × per_tile")
        _debug(f"  Total pixels: {width} × {height} = {total_pixels:,}")
        _debug(f"  Tile size: {tile_px} × {tile_px} = {tile_size_pixels:,} px")
        _debug(f"  Tiles: max(1, {total_pixels:,} / {tile_size_pixels:,}) = {tiles}")

        estimated = base + tiles * per_tile
        _debug(f"  Token estimate: {base} + {tiles} × {per_tile} = {estimated}")

        return estimated, dims

    _debug(f"No image dimensions detected (unsupported format or missing data)")
    _debug(f"Using default: {default_tokens} tokens")
    return default_tokens, None


def supported_extensions() -> list:
    ext_str = config.get("IMR_SUPPORTED_IMAGE_EXTENSIONS", ".png,.jpg,.jpeg")
    return [e.strip().lower() for e in ext_str.split(",") if e.strip()]


def is_supported_image(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in supported_extensions()


def format_tool_error(tool_name: str, error: Exception, context: str = "") -> dict:
    return {
        config.get("IMR_ERROR_SUCCESS_KEY", "success"): False,
        config.get("IMR_ERROR_TOOL_KEY", "tool"): tool_name,
        config.get("IMR_ERROR_ERROR_KEY", "error"): str(error),
        config.get("IMR_ERROR_ERROR_TYPE_KEY", "error_type"): type(error).__name__,
        config.get("IMR_ERROR_CONTEXT_KEY", "context"): context,
    }


def format_tool_success(tool_name: str, data: dict) -> dict:
    return {
        config.get("IMR_ERROR_SUCCESS_KEY", "success"): True,
        config.get("IMR_ERROR_TOOL_KEY", "tool"): tool_name,
        config.get("IMR_ERROR_DATA_KEY", "data"): data,
    }
