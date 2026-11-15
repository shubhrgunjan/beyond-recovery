"""Download and hash-check the pinned public G1 AMP policy and interface sources."""
import hashlib,json
from pathlib import Path
import urllib.request
root=Path(__file__).resolve().parents[1]
meta=json.loads((root/'configs/recovery_reference.json').read_text())
base=f'https://raw.githubusercontent.com/ccrpRepo/wbc_fsm/{meta["revision"]}/'
files={'policy.onnx':'model/loco/Unitree-G1-AMP-Flat_model_30000.onnx',
       'controller.h':'include/FSM/State_MJAmp.h','controller.cpp':'src/FSM/State_MJAmp.cpp',
       'constants.h':'include/common/mathTypes.h'}
target=root/'third_party/g1_amp';target.mkdir(parents=True,exist_ok=True)
for name,path in files.items():
    output=target/name
    if not output.exists():
        with urllib.request.urlopen(base+path,timeout=30) as response:output.write_bytes(response.read())
    assert hashlib.sha256(output.read_bytes()).hexdigest()==meta['files'][name],name
print(target)
