"""Build standalone /fpga converter assets for ordinary static cPanel hosting."""
from pathlib import Path
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'deploy/cpanel/fpga'
DEST.mkdir(parents=True, exist_ok=True)
for name in ('style.css', 'converter.css'):
    (DEST/name).write_bytes((ROOT/'static'/name).read_bytes())
templates = {p.name: p.read_text(encoding='utf-8') for p in (ROOT/'hardware/template').iterdir() if p.is_file()}
(DEST/'templates.js').write_text('const LAB_TEMPLATES = '+json.dumps(templates, ensure_ascii=False)+';\n', encoding='utf-8')
page = (ROOT/'static/converter.html').read_text(encoding='utf-8')
page = page.replace('/static/', './').replace('href="/"', 'href="/fpga/"')
page = page.replace('href="/fpga/">پنل برد ←', 'href="https://aminbagheri.com/rasp/">پنل برد ←')
page = page.replace('این بخش سورس پروژه می‌سازد؛ کامپایل و تولید بیت‌فایل با ISE روی کامپیوتر شماست. اتصال UART و عامل کنترل برد هنوز راه‌اندازی نشده‌اند.',
                    'تبدیل کد داخل مرورگر شما انجام می‌شود. برای دریافت کدها از دکمهٔ نمایش و کپی استفاده کنید. ساخت بیت‌فایل با ISE روی کامپیوتر شماست؛ ارتباط UART سخت‌افزار هنوز راه‌اندازی نشده است.')
page = page.replace('سورس شما روی سرور اجرا نمی‌شود.', 'تبدیل و کپی کد در مرورگر انجام می‌شود؛ فقط برای دانلود ZIP، پروژه حداکثر ۳۰ دقیقه روی هاست نگهداری می‌شود.')
page = page.replace('<script src="./converter.js?v=3">', '<script src="./templates.js?v=2"></script><script src="./core.js?v=1"></script><script src="./converter.js?v=7">')
(DEST/'index.html').write_text(page, encoding='utf-8')
js = (ROOT/'static/converter.js').read_text(encoding='utf-8')
local_post = '''let activeDownload=null;
async function post(path,body){
 let data;
 if(path.endsWith('/inspect'))data={modules:inspectHDL(body.source)};
 else {
  const files=generateHDL(body.source,body.top,body.mapping);
  if(path.endsWith('/files'))data={files};
  else if(path.endsWith('/prepare-download')){
   const response=await fetch('./download.php',{method:'POST',headers:{'Content-Type':'application/zip'},body:projectZIP(files)});
   data=await response.json();
   if(!response.ok)throw Error(data.error||'آماده‌سازی دانلود ناموفق بود');
  }else throw Error('Unsupported action');
 }
 return {json:async()=>data};
}'''
js = re.sub(r'^async function post\(path,body\).*$', lambda _: local_post, js, count=1, flags=re.M)
(DEST/'converter.js').write_text(js, encoding='utf-8')
with zipfile.ZipFile(ROOT/'deploy/fpga-cpanel.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in DEST.iterdir():
        if path.is_file(): archive.write(path, 'fpga/'+path.name)
print('Built deploy/fpga-cpanel.zip')
