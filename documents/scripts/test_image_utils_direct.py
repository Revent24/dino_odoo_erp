#
#  -*- File: documents/scripts/test_image_utils_direct.py -*-
#
import importlib.util
import json

module_path = '/home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp/documents/services/image_utils.py'
spec = importlib.util.spec_from_file_location('image_utils_mod', module_path)
mod = importlib.util.module_from_spec(spec)
loader = spec.loader
loader.exec_module(mod)

print('is_base64_string on garbage:', mod.is_base64_string('notbase64'))
# small png header base64 (first bytes only) - represents \x89PNG
png_header_b64 = 'iVBORw0KGgo'
print('is_base64_string on png header:', mod.is_base64_string(png_header_b64))

# create small jpeg bytes via base64 of minimal jpeg header (might not be valid image)
jpeg_b64 = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAA'
print('is_base64_string jpeg_b64:', mod.is_base64_string(jpeg_b64))

# test prepare_inline_data on base64 header
res = mod.prepare_inline_data(png_header_b64, normalize=False)
print('prepare_inline_data(png_header_b64):', json.dumps(res or {}, ensure_ascii=False))

# test safe_truncate
s = 'x'*20000
print('safe_truncate len:', len(mod.safe_truncate(s, 1000)))
# End of file documents/scripts/test_image_utils_direct.py
