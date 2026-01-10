import base64
import binascii
import io
import logging
from typing import Optional, Union, Dict

_logger = logging.getLogger(__name__)


def is_base64_string(s: str) -> bool:
    """Quick heuristic: check if `s` looks like base64 (try decoding)."""
    if not isinstance(s, str):
        return False
    # Remove data URI prefix if present
    if s.startswith('data:'):
        try:
            s = s.split(',', 1)[1]
        except Exception:
            return False
    # Short-circuit
    if len(s) < 16:
        return False
    try:
        base64.b64decode(s, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def detect_mime_from_bytes(b: bytes) -> Optional[str]:
    if not b or not isinstance(b, (bytes, bytearray)):
        return None
    if b.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    # Relaxed JPEG check: just SOI is enough
    if b.startswith(b'\xff\xd8'):
        return 'image/jpeg'
    if b.startswith(b'RIFF') and len(b) > 12 and b[8:12] == b'WEBP':
        return 'image/webp'
    if b.startswith(b'%PDF'):
        return 'application/pdf'
    if b.startswith(b'GIF8'):
        return 'image/gif'
    if b.startswith(b'BM'):
        return 'image/bmp'
    if b.startswith(b'II*\x00') or b.startswith(b'MM\x00*'):
        return 'image/tiff'

    # Fallback to imghdr if available
    try:
        import imghdr
        fmt = imghdr.what(None, h=b)
        if fmt:
            return f'image/{fmt}'
    except ImportError:
        pass
    
    return None


def detect_mime(image: Union[bytes, str]) -> Optional[str]:
    """Detect MIME type from bytes or data URI/base64 string."""
    if isinstance(image, (bytes, bytearray)):
        return detect_mime_from_bytes(bytes(image))
    if isinstance(image, str):
        # data URI
        if image.startswith('data:'):
            try:
                prefix = image.split(';', 1)[0]
                if prefix.startswith('data:'):
                    return prefix[len('data:'):]
            except Exception:
                pass
        # base64 string -> decode first bytes
        try:
            snippet = image[:100]
            decoded = base64.b64decode(snippet)
            return detect_mime_from_bytes(decoded)
        except Exception:
            return None
    return None


def to_base64(image: Union[bytes, str]) -> Optional[str]:
    """Return base64 string (no data: prefix) for bytes or base64 input.

    Returns None on failure.
    """
    if image is None:
        return None
    # If bytes and look like raw image bytes -> encode
    if isinstance(image, (bytes, bytearray)):
        try:
            # Fast check: if magic bytes present -> treat as raw
            if detect_mime_from_bytes(bytes(image)):
                return base64.b64encode(bytes(image)).decode('utf-8')
            # else maybe ascii bytes containing base64
            try:
                s = bytes(image).decode('ascii')
                if is_base64_string(s):
                    return s
            except Exception:
                pass
            # fallback: encode
            return base64.b64encode(bytes(image)).decode('utf-8')
        except Exception as e:
            _logger.warning(f"to_base64: failed to encode bytes: {e}")
            return None

    if isinstance(image, str):
        # strip data URI
        if image.startswith('data:'):
            try:
                _, rest = image.split(',', 1)
                image = rest
            except Exception:
                pass
        # if already base64
        if is_base64_string(image):
            return image
        # maybe it's a path or other string - not supported here
        return None


def to_bytes(image: Union[bytes, str]) -> Optional[bytes]:
    """Return raw bytes for image. If input is base64 string - decode it."""
    if image is None:
        return None
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    if isinstance(image, str):
        # strip data URI
        if image.startswith('data:'):
            try:
                _, rest = image.split(',', 1)
                image = rest
            except Exception:
                pass
        try:
            return base64.b64decode(image)
        except Exception as e:
            _logger.warning(f"to_bytes: failed to decode base64: {e}")
            return None
    return None


def normalize_image(image_bytes: bytes, max_dimension: int = 2048, quality: int = 85) -> bytes:
    """Resize/convert image using PIL if available. Returns bytes (JPEG by default).

    If PIL is not available or processing fails, returns original bytes.
    """
    try:
        from PIL import Image
    except Exception:
        _logger.debug("PIL not available, skipping normalization")
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Resize if too large
        max_dim = max(img.size)
        if max_dim > max_dimension:
            ratio = max_dimension / max_dim
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            _logger.info(f"normalize_image: resized to {new_size}")

        # Convert to RGB/JPEG to save space if possible
        fmt = img.format or 'JPEG'
        out = io.BytesIO()
        if fmt.upper() in ('PNG', 'WEBP') or img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(out, format='JPEG', quality=quality, optimize=True)
        return out.getvalue()
    except Exception as e:
        _logger.warning(f"normalize_image failed: {e}")
        return image_bytes


def prepare_inline_data(image: Union[bytes, str], normalize: bool = True) -> Optional[Dict[str, str]]:
    """Prepare {'mime_type': ..., 'data': '<base64>'} from image bytes or base64 string.

    - Detect mime
    - Normalize bytes if requested
    - Return None on error (e.g. invalid base64, empty bytes, unknown format)
    """
    if image is None:
        return None

    b = None
    mime = None

    try:
        # 1. Convert input to bytes and initial mime detection
        if isinstance(image, (bytes, bytearray)):
            b = bytes(image)
            # CRITICAL FIX (2026-01-10): Check if bytes are actually double-encoded base64 string
            # Example: b'iVBORw0KGgo...' (which is base64 of PNG) instead of b'\x89PNG...'
            if len(b) > 4:
                # Check for PNG base64 signature "iVBORw"
                if b.startswith(b'iVBORw'):
                    try:
                        decoded = base64.b64decode(b)
                        if detect_mime_from_bytes(decoded) == 'image/png':
                            b = decoded
                    except Exception:
                        pass
                # Check for JPEG base64 signature "/9j/4"
                elif b.startswith(b'/9j/4'):
                    try:
                        decoded = base64.b64decode(b)
                        if detect_mime_from_bytes(decoded) == 'image/jpeg':
                            b = decoded
                    except Exception:
                        pass
                # Generic check: if it looks like base64 ascii bytes
                elif (b[0] not in [0x89, 0xFF, 0x25, 0x47, 0x42, 0x49, 0x4D]) and is_base64_string(b.decode('ascii', errors='ignore')):
                     try:
                        decoded = base64.b64decode(b)
                        if detect_mime_from_bytes(decoded):
                             b = decoded
                     except Exception:
                        pass

        elif isinstance(image, str):
            if image.startswith('data:'):
                try:
                    prefix, rest = image.split(',', 1)
                    mime_candidate = prefix.split(';')[0][len('data:'):]
                    if mime_candidate:
                        mime = mime_candidate
                    b = base64.b64decode(rest)
                except Exception:
                    _logger.warning("prepare_inline_data: failed to parse data URI")
                    return None
            else:
                # Try to decode base64 directly, skipping is_base64_string check to allow newlines
                try:
                    b = base64.b64decode(image)
                except Exception:
                    _logger.warning("prepare_inline_data: failed to decode base64")
                    return None
        else:
            return None  # Unknown type

        if not b:
            return None

        # 2. Detect MIME from bytes (most reliable)
        detected_mime = detect_mime_from_bytes(b)
        # 2. Detect MIME from bytes (most reliable)
        detected_mime = detect_mime_from_bytes(b)
        if detected_mime:
            mime = detected_mime
        else:
            _logger.warning(f"prepare_inline_data: Native MIME detection failed. Header bytes: {b[:32].hex() if b else 'None'}")
        
        # If still no mime, and we have the one from data URI, use it.
        # But if even that is missing/generic, we have a problem.
        # Fallback: Try to let PIL identify it
        if not mime:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(b))
                # Image.open only identifies. format isn't set until we load or if it's already there?
                # Actually Image.open reads the header.
                pkt_format = img.format
                if pkt_format:
                    # Mappings for common PIL formats to Mime
                    fmt = pkt_format.upper()
                    if fmt == 'JPEG': mime = 'image/jpeg'
                    elif fmt == 'PNG': mime = 'image/png'
                    elif fmt == 'WEBP': mime = 'image/webp'
                    elif fmt == 'TIFF': mime = 'image/tiff'
                    elif fmt == 'BMP': mime = 'image/bmp'
                    elif fmt == 'GIF': mime = 'image/gif'
                    else: mime = f'image/{fmt.lower()}'
                else:
                    _logger.warning("prepare_inline_data: PIL opened image but format is None")
            except ImportError:
                 _logger.warning("prepare_inline_data: PIL (Pillow) library not found - fallback disabled")
            except Exception as e:
                _logger.warning(f"prepare_inline_data: PIL fallback detection failed: {e}")
                
        
        # If still None -> we cannot send this to Gemini safely.
        if not mime:
            _logger.warning("prepare_inline_data: Could not determine MIME type, skipping image.")
            return None

        # 3. Normalize if requested (AND if it is an image we can normalize)
        # Skip normalization for non-image types like PDF
        if normalize and mime.startswith('image/') and mime != 'image/gif':
            # normalize_image returns bytes (usually JPEG)
            b_norm = normalize_image(b)
            # Check if normalization actually happened/worked
            if b_norm and b_norm != b:
                b = b_norm
                # Since normalize_image ALWAYS converts to JPEG, we can safely set mime to jpeg
                mime = 'image/jpeg'
            
        # 4. Encode result
        b64 = base64.b64encode(b).decode('utf-8')
        return {'mime_type': mime, 'data': b64}

    except Exception as e:
        _logger.error(f"prepare_inline_data unexpected error: {e}")
        return None


def safe_truncate(s: str, max_len: int = 10000) -> str:
    if not isinstance(s, str):
        return s
    if len(s) <= max_len:
        return s
    return s[:max_len] + "\n\n... (обрізано)"
