"""Audit current Cloudinary state under gms-world-foods/products"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import cloudinary
import cloudinary.api
from app.config import get_settings

s = get_settings()
cloudinary.config(
    cloud_name=s.cloudinary_cloud_name,
    api_key=s.cloudinary_api_key,
    api_secret=s.cloudinary_api_secret,
    secure=True,
)

all_resources = []
next_cursor = None
while True:
    kwargs = dict(type='upload', prefix='gms-world-foods/products', max_results=500)
    if next_cursor:
        kwargs['next_cursor'] = next_cursor
    result = cloudinary.api.resources(**kwargs)
    all_resources.extend(result['resources'])
    next_cursor = result.get('next_cursor')
    if not next_cursor:
        break

print(f"Total resources under gms-world-foods/products: {len(all_resources)}")

# Categorise by path depth
flat = []      # gms-world-foods/products/<product_id>
in_cat = []    # gms-world-foods/products/<category>/<product_id>

for r in all_resources:
    pid = r['public_id']
    parts = pid.replace('gms-world-foods/products/', '').split('/')
    if len(parts) == 1:
        flat.append(pid)
    else:
        in_cat.append(pid)

print(f"\nFlat (need moving): {len(flat)}")
print(f"Already in sub-folder: {len(in_cat)}")

# Show unique subfolders already present
subfolders = set()
for pid in in_cat:
    parts = pid.replace('gms-world-foods/products/', '').split('/')
    if len(parts) >= 2:
        subfolders.add(parts[0])
print(f"\nExisting sub-folders: {sorted(subfolders)}")

# Sample flat
if flat:
    print(f"\nSample flat public_ids (first 5):")
    for p in flat[:5]:
        print(f"  {p}")
