#
#  -*- File: documents/tests/test_image_utils.py -*-
#
import base64
import os
import importlib.util


def load_module():
    path = os.path.join(os.path.dirname(__file__), '..', 'services', 'image_utils.py')
    path = os.path.normpath(path)
    spec = importlib.util.spec_from_file_location('image_utils_mod', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_is_base64_and_conversion():
    mod = load_module()
    data = b'A' * 64
    b64 = base64.b64encode(data).decode('utf-8')
    assert mod.is_base64_string(b64)
    decoded = mod.to_bytes(b64)
    assert decoded == data
    b64_out = mod.to_base64(data)
    assert mod.is_base64_string(b64_out)


def test_detect_mime_and_prepare_inline():
    mod = load_module()
    # fake png bytes (magic header + payload)
    png_bytes = b'\x89PNG\r\n\x1a\n' + b'0' * 100
    mime = mod.detect_mime(png_bytes)
    assert mime == 'image/png'

    inline = mod.prepare_inline_data(png_bytes, normalize=False)
    assert inline is not None
    assert inline.get('mime_type') == 'image/png'
    assert mod.is_base64_string(inline.get('data'))


def test_safe_truncate():
    mod = load_module()
    s = 'x' * 20000
    t = mod.safe_truncate(s, 1000)
    assert len(t) <= 1005
# End of file documents/tests/test_image_utils.py
