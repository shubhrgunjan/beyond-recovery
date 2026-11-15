"""Correct NVIDIA's invalid `sbsa` wheel metadata tag, without changing binaries.

The upstream filename is tagged aarch64, but its embedded WHEEL tag says sbsa.
pip installs the wheel and subsequently rejects that embedded tag in `pip check`.
The post1 release avoids the tag problem but violates Torch's exact 0.8.1 pin.
Repack the original pinned wheel, updating its RECORD hashes and writing provenance.
"""

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "nvidia_cusparselt_cu13-0.8.1-py3-none-manylinux2014_aarch64.whl"
URL = "https://pypi.nvidia.com/nvidia-cusparselt-cu13/" + NAME
SHA256 = "4dca476c50bf4780d46cd0bfbd82e2bc10a08e4fef7950917ce8d7578d22a23f"
cache = ROOT / ".cache/wheels"
cache.mkdir(parents=True, exist_ok=True)
original = cache / NAME
if not original.exists():
    urllib.request.urlretrieve(URL, original)
assert hashlib.sha256(original.read_bytes()).hexdigest() == SHA256, "Upstream hash changed"
output = cache / "corrected" / NAME
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(original) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dest:
    wheel_name = next(n for n in source.namelist() if n.endswith(".dist-info/WHEEL"))
    record_name = next(n for n in source.namelist() if n.endswith(".dist-info/RECORD"))
    rows = []
    for item in source.infolist():
        if item.filename == record_name:
            continue
        data = source.read(item.filename)
        if item.filename == wheel_name:
            assert b"Tag: py3-none-manylinux2014_sbsa" in data
            data = data.replace(b"Tag: py3-none-manylinux2014_sbsa",
                                b"Tag: py3-none-manylinux2014_aarch64")
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append([item.filename, "sha256=" + digest, str(len(data))])
        dest.writestr(item, data)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerows(rows + [[record_name, "", ""]])
    dest.writestr(record_name, stream.getvalue())
manifest = {"url": URL, "original_sha256": SHA256,
            "corrected_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "change": "Only WHEEL platform tag and RECORD; binary payload unchanged"}
(ROOT / "artifacts").mkdir(exist_ok=True)
(ROOT / "artifacts/wheel-repack.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(output)
