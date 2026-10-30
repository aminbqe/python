"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import hashlib, urllib.request
from train_breast_histology import OUT, EXPECTED_SHA

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'breakhis_mirror.zip'
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED_SHA:
            raise ValueError('Existing archive checksum mismatch')
        print('Verified existing archive')
        return
    url = 'https://huggingface.co/datasets/hirundo-io/BreaKHis-original/resolve/main/breakhis.zip'
    part = target.with_suffix('.zip.part')
    with urllib.request.urlopen(url, timeout=60) as response, part.open('wb') as f:
        while True:
            b = response.read(2 ** 20)
            if not b:
                break
            f.write(b)
    if hashlib.sha256(part.read_bytes()).hexdigest() != EXPECTED_SHA:
        raise ValueError('Downloaded archive checksum mismatch')
    part.replace(target)
    print('Downloaded and verified', target)
if __name__ == '__main__':
    main()
