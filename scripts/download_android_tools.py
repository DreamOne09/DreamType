from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,urllib.request,zipfile,json
root=Path(__file__).resolve().parents[1]/'work/android-tools'
root.mkdir(parents=True,exist_ok=True)
items=[
 ('platform36.zip','https://dl.google.com/android/repository/platform-36_r02.zip','sha1','2c1a80dd4d9f7d0e6dd336ec603d9b5c55a6f576','platform'),
 ('platform.zip','https://dl.google.com/android/repository/platform-35_r02.zip','sha1','0bb560a90a7a2cbd0dd8348224d518b638fe7949','platform'),
 ('build-tools.zip','https://dl.google.com/android/repository/build-tools_r35_windows.zip','sha1','af059bb67cf7786f45ee0db85e2d24985df1b4b6','build-tools'),
 ('jdk.zip','https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip','sha256','f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e','jdk')]
def download(item):
 name,url,algorithm,expected,directory=item
 target=root/name
 urllib.request.urlretrieve(url,target)
 digest=hashlib.new(algorithm)
 with target.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
 if digest.hexdigest()!=expected:raise RuntimeError(name+' checksum mismatch')
 with zipfile.ZipFile(target) as z:z.extractall(root/directory)
 print(name+' verified and extracted',flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(download,items))
(root/'sources.json').write_text(json.dumps(items,indent=2))
