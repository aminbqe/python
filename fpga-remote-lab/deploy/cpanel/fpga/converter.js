const el=id=>document.getElementById(id);
function projectFilename(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Tehran',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(now);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return `${p.year}-${p.month}-${p.day}_${p.hour}-${p.minute}-${p.second}-${String(now.getUTCMilliseconds()).padStart(3,'0')}.zip`;
}
const examples={adder:`module full_adder (
    input wire a, b, cin,
    output wire sum, cout
);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (a & cin) | (b & cin);
endmodule
`,blink:`module blink (
    input wire clk,
    input wire reset,
    output reg led
);
    // Editable: blink interval, counter and circuit logic.
    reg [24:0] counter = 0;
    initial led = 0;
    always @(posedge clk) begin
        if (reset) begin
            counter <= 0;
            led <= 0;
        end else if (counter == 25'd24_999_999) begin
            counter <= 0;
            led <= ~led;
        end else counter <= counter + 1'b1;
    end
endmodule
`};
let modules=[],checkedSource='';
function invalidate(){el('show-code').disabled=true;el('code-output').hidden=true;el('download-link').hidden=true;modules=[];checkedSource='';el('download').disabled=true;el('top').disabled=true;el('mapping').replaceChildren();el('mapping-empty').hidden=false;el('error').textContent=''}
el('source').value=examples.adder;el('source').oninput=invalidate;
for(const name of ['adder','blink'])el('example-'+name).onclick=()=>{el('source').value=examples[name];invalidate()};
el('source-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;if(file.size>128000){el('error').textContent='حداکثر اندازهٔ فایل ۱۲۸ کیلوبایت است';return}el('source').value=await file.text();invalidate()};
let activeDownload=null;
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
}
el('inspect').onclick=async()=>{invalidate();el('inspect').disabled=true;try{const source=el('source').value;const response=await post('/api/verilog/inspect',{source});const data=await response.json();if(source!==el('source').value)return;modules=data.modules;checkedSource=source;el('top').replaceChildren();for(const m of modules)el('top').add(new Option(m.name,m.name));el('top').disabled=false;renderMapping()}catch(error){el('error').textContent=error.message}finally{el('inspect').disabled=false}};
function renderMapping(){el('code-output').hidden=true;el('mapping').replaceChildren();el('mapping-empty').hidden=true;el('error').textContent='';const m=modules.find(m=>m.name===el('top').value);if(!m)return;
for(const p of m.ports){const row=document.createElement('div');row.className='port-row';const label=document.createElement('label');label.className='port-name';label.htmlFor='port-'+p.name;label.textContent=p.name;const detail=document.createElement('small');detail.textContent=`${p.direction==='input'?'ورودی':'خروجی'} · ${p.width} بیت`;label.append(detail);const select=document.createElement('select');select.id='port-'+p.name;select.dataset.port=p.name;
if(p.direction==='input'){select.add(new Option('ثابت صفر — بدون ورودی','zero'));if(p.width===1){select.add(new Option('کلاک ۵۰ مگاهرتز','clk'));select.add(new Option('ریست جلسه','reset'))}for(const [bus,width,title] of [['switches',4,'کلید'],['buttons',4,'دکمه'],['input_a',32,'عدد A'],['input_b',32,'عدد B']])for(let start=0;start+p.width<=width;start++)select.add(new Option(`${title} [${start+p.width-1}:${start}]`,`${bus}:${start}`));const defaults={clk:'clk',clock:'clk',reset:'reset',rst:'reset',a:'switches:0',b:'switches:1',cin:'switches:2',switches:'switches:0',buttons:'buttons:0',input_a:'input_a:0',input_b:'input_b:0'};const value=defaults[p.name];if(value&&[...select.options].some(o=>o.value===value))select.value=value;
}else{select.add(new Option('استفاده نشود','unused'));for(const [bus,width,title]of [['leds',4,'LED مجازی'],['result',32,'نتیجه']])for(let start=0;start+p.width<=width;start++)select.add(new Option(`${title} [${start+p.width-1}:${start}]`,`${bus}:${start}`));const defaults={sum:'leds:0',cout:'leds:1',led:'leds:0',leds:'leds:0',result:'result:0'};const value=defaults[p.name];if(value&&[...select.options].some(o=>o.value===value))select.value=value;}
row.append(label,select);el('mapping').append(row)}el('download').disabled=false;el('show-code').disabled=false;el('mapping').onchange=()=>{el('code-output').hidden=true};}
el('top').onchange=renderMapping;
el('show-code').onclick=async()=>{
 el('show-code').disabled=true;el('error').textContent='';
 try{
  if(checkedSource!==el('source').value)throw Error('کد تغییر کرده؛ دوباره بررسی کنید');
  const source=checkedSource,top=el('top').value,mapping={};
  el('mapping').querySelectorAll('select').forEach(s=>mapping[s.dataset.port]=s.value);
  const response=await post('/api/verilog/files',{source,top,mapping});
  const data=await response.json();
  if(source!==el('source').value||top!==el('top').value)return;
  const current={};el('mapping').querySelectorAll('select').forEach(s=>current[s.dataset.port]=s.value);
  if(JSON.stringify(current)!==JSON.stringify(mapping))return;
  el('code-files').replaceChildren();el('copy-status').textContent='';
  for(const file of data.files){
   const box=document.createElement('details');box.className='code-file';
   const summary=document.createElement('summary');summary.textContent=file.name;box.append(summary);
   const area=document.createElement('textarea');area.readOnly=true;area.dir='ltr';area.spellcheck=false;area.value=file.content;area.setAttribute('aria-label',file.name);
   const copy=document.createElement('button');copy.className='small-button';copy.textContent='کپی کد';
   copy.onclick=async()=>{
    let copied=false;
    try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(file.content);copied=true}}catch(e){}
    if(!copied){area.focus();area.select();try{copied=document.execCommand('copy')}catch(e){}}
    el('copy-status').textContent=copied?`کد ${file.name} کپی شد`:'کد انتخاب شد؛ Ctrl+C بزنید.';
   };
   box.append(copy,area);box.open=file.name==='user_logic.v'||file.name==='lab.ucf';el('code-files').append(box);
  }
  el('code-output').hidden=false;el('code-output').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(error){el('error').textContent=error.message}
 finally{el('show-code').disabled=!checkedSource||checkedSource!==el('source').value}
};
el('download').onclick=async()=>{el('download').disabled=true;el('error').textContent='';try{if(checkedSource!==el('source').value)throw Error('کد تغییر کرده؛ دوباره بررسی کنید');const mapping={};el('mapping').querySelectorAll('select').forEach(s=>mapping[s.dataset.port]=s.value);const response=await post('/api/verilog/prepare-download',{source:checkedSource,top:el('top').value,mapping});const data=await response.json();const a=el('download-link');const filename=projectFilename();a.href=data.url+(data.url.includes('?')?'&':'?')+'name='+encodeURIComponent(filename);a.download=filename;a.hidden=false;a.click()}catch(error){el('error').textContent=error.message}finally{el('download').disabled=checkedSource!==el('source').value||!checkedSource}};
