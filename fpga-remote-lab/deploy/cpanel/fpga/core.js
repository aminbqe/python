/* Browser-only adapter generator. Submitted HDL is treated as text, never run. */
const IDENT='[A-Za-z_][A-Za-z0-9_$]*';
function inspectHDL(source){
 if(typeof source!=='string'||!source.trim()||new TextEncoder().encode(source).length>128000)throw Error('سورس باید غیرخالی و حداکثر ۱۲۸ کیلوبایت باشد');
 const clean=source.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g,'');
 if(/[`\\]/.test(clean))throw Error('ماکرو، include و نام escape‌شده پشتیبانی نمی‌شود');
 const modules=[];
 const pattern=new RegExp('\\bmodule\\s+('+IDENT+')\\s*([\\s\\S]*?)\\bendmodule\\b','g');
 for(const match of clean.matchAll(pattern)){
  const name=match[1],text=match[2];
  if(text.trimStart().startsWith('#'))throw Error('پارامترهای ماژول فعلاً پشتیبانی نمی‌شوند');
  const header=text.match(/^\s*\(([\s\S]*?)\)\s*;([\s\S]*)$/);
  if(!header)throw Error('سرآیند ماژول پشتیبانی نمی‌شود: '+name);
  if(/\binout\b/.test(header[1]+header[2]))throw Error('پورت inout پشتیبانی نمی‌شود');
  let ports=[];
  function declarations(items){
   let direction=null,msb=0,lsb=0;
   for(let item of items){
    item=item.trim();let m=item.match(/^(input|output)\b\s*([\s\S]*)$/);
    if(m){direction=m[1];item=m[2];msb=lsb=0}
    item=item.replace(/\b(wire|reg|signed|unsigned)\b/g,'').trim();
    m=item.match(/^\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*([\s\S]*)$/);
    if(m){msb=Number(m[1]);lsb=Number(m[2]);item=m[3];if(msb<lsb)throw Error('بازهٔ صعودی پشتیبانی نمی‌شود')}
    if(!direction||!new RegExp('^'+IDENT+'$').test(item)||!Number.isSafeInteger(msb)||msb-lsb+1>32)throw Error('پورت نامعتبر یا پشتیبانی‌نشده: '+item.slice(0,80));
    ports.push({name:item,direction,width:msb-lsb+1,lsb});
   }
  }
  if(/\b(input|output)\b/.test(header[1]))declarations(header[1].split(','));
  else{
   const names=header[1].split(',').map(s=>s.trim()).filter(Boolean);
   for(const d of header[2].matchAll(/\b(input|output)\s+([^;]+);/g)){
    const items=d[2].split(',');items[0]=d[1]+' '+items[0];declarations(items);
   }
   const byName=new Map(ports.map(p=>[p.name,p]));
   if(names.length!==ports.length||names.some(n=>!byName.has(n)))throw Error('تعریف پورت‌ها کامل نیست');
   ports=names.map(n=>byName.get(n));
  }
  if(!ports.length||new Set(ports.map(p=>p.name)).size!==ports.length)throw Error('پورت خالی یا تکراری است');
  if(['lab_top','user_logic','lab_uart_tx','lab_uart_rx','lab_bridge'].includes(name))throw Error('نام ماژول با قالب ثابت تداخل دارد');
  modules.push({name,ports});
 }
 if(!modules.length||new Set(modules.map(m=>m.name)).size!==modules.length)throw Error('ماژول معتبر با نام یکتا پیدا نشد');
 return modules;
}
function generateHDL(source,top,mapping){
 const module=inspectHDL(source).find(m=>m.name===top);
 if(!module||!mapping||Object.keys(mapping).length!==module.ports.length||module.ports.some(p=>!Object.hasOwn(mapping,p.name)))throw Error('برای همهٔ پورت‌ها نگاشت انتخاب کنید');
 const lines=['// Generated adapter. Edit mapping in the website, not this file.',
 'module user_logic(input wire clk, reset, input wire [3:0] switches, buttons,',
 ' input wire [31:0] input_a, input_b, output wire [3:0] leds, output wire [31:0] result);'];
 const outputs={leds:Array(4).fill("1'b0"),result:Array(32).fill("1'b0")},used=new Set(),connections=[];
 module.ports.forEach((p,index)=>{
  const choice=mapping[p.name],width=p.width;let expr;
  if(typeof choice!=='string')throw Error('نگاشت نامعتبر');
  if(p.direction==='input'){
   if(choice==='zero')expr=`${width}'d0`;
   else if(['clk','reset'].includes(choice)&&width===1)expr=choice;
   else{
    const m=choice.match(/^(switches|buttons|input_a|input_b):(\d+)$/);
    if(!m)throw Error('نگاشت ورودی نامعتبر: '+p.name);
    const start=Number(m[2]),capacity=['switches','buttons'].includes(m[1])?4:32;
    if(start+width>capacity)throw Error('عرض ورودی بیشتر از ظرفیت قالب است');
    expr=`${m[1]}[${start+width-1}:${start}]`;
   }
  }else{
   expr=`port_${index}`;lines.push(`wire [${width-1}:0] ${expr};`);
   if(choice!=='unused'){
    const m=choice.match(/^(leds|result):(\d+)$/);if(!m)throw Error('نگاشت خروجی نامعتبر: '+p.name);
    const bus=m[1],start=Number(m[2]);if(start+width>outputs[bus].length)throw Error('عرض خروجی بیشتر از ظرفیت قالب است');
    for(let bit=0;bit<width;bit++){
     const key=bus+':'+(start+bit);if(used.has(key))throw Error('دو خروجی روی بیت مشترک نگاشت شده‌اند');
     used.add(key);outputs[bus][start+bit]=`${expr}[${bit}]`;
    }
   }
  }
  connections.push(`.${p.name}(${expr})`);
 });
 lines.push(`${top} design_instance (${connections.join(', ')});`);
 for(const [bus,bits]of Object.entries(outputs))lines.push(`assign ${bus} = {${[...bits].reverse().join(', ')}};`);
 lines.push('endmodule\n');
 return [...Object.entries(LAB_TEMPLATES).map(([name,content])=>({name,content})),
 {name:'design.v',content:source},{name:'user_logic.v',content:lines.join('\n')},
 {name:'mapping.json',content:JSON.stringify({top,ports:module.ports,mapping},null,2)}];
}
// ZIP STORE writer: no CDN, dependency or backend required.
function projectZIP(files){
 const enc=new TextEncoder(),parts=[],central=[];let offset=0;
 const crc=data=>{let c=0xffffffff;for(const b of data){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0)}return(c^0xffffffff)>>>0};
 const record=(size)=>{const bytes=new Uint8Array(size);return{bytes,view:new DataView(bytes.buffer)}};
 for(const file of files){
  const name=enc.encode(file.name),data=enc.encode(file.content),sum=crc(data),local=record(30+name.length),v=local.view;
  v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(12,33,true);
  v.setUint32(14,sum,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);local.bytes.set(name,30);
  parts.push(local.bytes,data);
  const c=record(46+name.length),w=c.view;w.setUint32(0,0x02014b50,true);w.setUint16(4,20,true);w.setUint16(6,20,true);w.setUint16(8,0x800,true);w.setUint16(14,33,true);
  w.setUint32(16,sum,true);w.setUint32(20,data.length,true);w.setUint32(24,data.length,true);w.setUint16(28,name.length,true);w.setUint32(42,offset,true);c.bytes.set(name,46);central.push(c.bytes);
  offset+=local.bytes.length+data.length;
 }
 const size=central.reduce((n,b)=>n+b.length,0),end=record(22),v=end.view;
 v.setUint32(0,0x06054b50,true);v.setUint16(8,files.length,true);v.setUint16(10,files.length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);
 return new Blob([...parts,...central,end.bytes],{type:'application/zip'});
}
