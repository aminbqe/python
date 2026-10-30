const $=id=>document.getElementById(id);
const labBase=new URL('./',location.href);
let socket,connected=false,server=false,job=null,file=null,uartLive=false,jtagConnected=null,fpgaDetected=null,lastUART=0;
const segments=['6,2 26,2 30,6 26,10 6,10 2,6','28,8 32,12 30,25 26,29 24,25 26,12','26,31 30,29 28,45 24,49 22,45 24,35','4,48 24,48 28,52 24,56 4,56 0,52','2,30 6,34 4,45 0,49 0,34','4,8 8,12 6,25 2,29 0,25 2,12','6,25 24,25 28,29 24,33 6,33 2,29'];
for(let i=0;i<4;i++){
 const lamp=document.createElement('div');lamp.className='led-item';lamp.innerHTML=`<i class="led" id="led${i}"></i>LED ${i+1}`;$('leds').append(lamp);
 const sw=document.createElement('button');sw.className='switch';sw.disabled=true;sw.setAttribute('aria-label',`کلید ${i+1}`);sw.setAttribute('aria-pressed','false');sw.onclick=()=>send({type:'input',kind:'switch',index:i,value:sw.getAttribute('aria-pressed')!=='true'});$('switches').append(sw);
 const btn=document.createElement('button');btn.className='push';btn.disabled=true;btn.setAttribute('aria-label',`دکمه ${i+1}`);let held=false;const press=()=>{if(held)return;held=true;send({type:'input',kind:'button',index:i,value:true})};const release=()=>{if(!held)return;held=false;send({type:'input',kind:'button',index:i,value:false})};btn.onpointerdown=e=>{btn.setPointerCapture(e.pointerId);press()};btn.onpointerup=release;btn.onpointercancel=release;btn.onlostpointercapture=release;btn.onkeydown=e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();press()}};btn.onkeyup=release;btn.onblur=release;$('buttons').append(btn);
}
for(let i=0;i<6;i++){$('digits').insertAdjacentHTML('beforeend',`<svg class="digit" viewBox="0 0 38 60" aria-label="رقم ${i+1}">${segments.map(p=>`<polygon class="seg" points="${p}"/>`).join('')}<circle class="seg" cx="35" cy="53" r="2"/></svg>`)}
function log(text){const row=document.createElement('div');row.className='log';const t=document.createElement('time');t.textContent=new Date().toLocaleTimeString('en-GB');const s=document.createElement('span');s.textContent=text;row.append(t,s);$('logs').append(row);while($('logs').children.length>300)$('logs').firstChild.remove();$('logs').scrollTop=$('logs').scrollHeight}
function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').style.display='none',5000)}
function send(message){if(socket?.readyState===1)socket.send(JSON.stringify(message))}
function render(){
 const running=connected&&uartLive&&job?.status==='running';
 $('connection').textContent=!server?'● ارتباط سرور قطع است':!connected?'○ عامل پای قطع است':(fpgaDetected===true||uartLive)?'● برد FPGA پاسخ می‌دهد':fpgaDetected===false?'○ برد FPGA در دسترس نیست':'○ در حال شناسایی FPGA';
 $('connection').style.color=connected&&(fpgaDetected===true||uartLive)?'#65e0bb':'#e5b56c';
 $('hardware').textContent=!connected?'عامل پای قطع':uartLive?'UART برقرار':'UART قطع / طرح بدون داده';
 $('physical').textContent=!connected?'نامشخص':fpgaDetected===true?'XC6SLX9 شناسایی شد':fpgaDetected===false?'بدون پاسخ JTAG':'در حال بررسی';$('programmer').textContent=!connected?'نامشخص':jtagConnected===true?'USB متصل':jtagConnected===false?'USB قطع':'در حال بررسی';
 $('status').textContent=job?(job.status==='running'&&!uartLive?'اجرای برد تأیید نمی‌شود':({programming:'در حال پروگرام',running:'در حال اجرا',error:'خطای اجرا',stopped:'پایان‌یافته'}[job.status]||job.status)):'بدون جلسه';
 $('upload').disabled=!connected||jtagConnected!==true||!!job||!file||!$('upload-password').value;
 $('stop').disabled=!connected||!job||job.status!=='running';$('reset').disabled=!running;
 document.querySelectorAll('.switch,.push').forEach(b=>b.disabled=!running);
}
function telemetry(data){connected=data.connected;uartLive=data.uart_live===true;jtagConnected=data.jtag_connected??null;fpgaDetected=data.fpga_detected??null;if(uartLive)lastUART=Date.now();const known=Array.isArray(data.leds);$('result').textContent=Number.isInteger(data.result)?data.result:'—';document.querySelectorAll('.switch').forEach((b,i)=>{const on=Number.isInteger(data.switches)&&!!(data.switches&(1<<i));b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on))});$('live').textContent=data.uart_live===true?'دادهٔ زندهٔ UART':connected?'منتظر دادهٔ UART':'داده‌ای دریافت نشده';$('unknown').textContent=known?'وضعیت دریافت‌شده از سخت‌افزار':'وضعیت خروجی‌ها نامشخص است';for(let i=0;i<4;i++)$('led'+i).classList.toggle('on',known&&data.leds[i]===true);document.querySelectorAll('.digit').forEach((d,i)=>d.querySelectorAll('.seg').forEach((s,b)=>s.classList.toggle('on',Array.isArray(data.digits)&&!!(data.digits[i]&(1<<b)))));render()}
function connect(){socket=new WebSocket(new URL('ws',labBase).href.replace(/^http/,'ws'));socket.onopen=()=>{server=true;log('ارتباط با سرور برقرار شد');render()};socket.onmessage=e=>{const data=JSON.parse(e.data);if(data.type==='state')telemetry(data);if(data.type==='job'){job=data.job;render()}if(data.type==='log')log(data.text)};socket.onclose=()=>{server=false;job=null;telemetry({connected:false});setTimeout(connect,2500)};socket.onerror=()=>socket.close()}
function select(f){if(!f)return;if(!f.name.toLowerCase().endsWith('.bit')||f.size>8*1024*1024||f.size===0){toast('یک فایل .bit معتبر تا ۸ مگابایت انتخاب کنید');return}file=f;$('filename').textContent=f.name;render()}
$('file').onchange=e=>select(e.target.files[0]);$('drop').ondragover=e=>e.preventDefault();$('drop').ondrop=e=>{e.preventDefault();select(e.dataTransfer.files[0])};$('upload').onclick=async()=>{const form=new FormData();form.append('file',file);$('upload').disabled=true;try{const response=await fetch(new URL('api/upload',labBase),{method:'POST',headers:{'X-Upload-Password':$('upload-password').value},body:form});const data=await response.json();if(!response.ok){if(response.status===401)$('upload-password').value='';throw Error(data.detail||'بارگذاری ناموفق بود')}job=data;log('فایل برای بررسی و پروگرام به عامل ارسال شد')}catch(e){toast(e.message);log(e.message)}finally{render()}};$('stop').onclick=()=>send({type:'stop'});$('clear').onclick=()=>$('logs').replaceChildren();setInterval(()=>{const seconds=job?Math.max(0,Math.floor(Date.now()/1000-job.started)):0;$('timer').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`},1000);connect();

$('reset').onclick=()=>send({type:'reset'});

setInterval(()=>{if(uartLive&&Date.now()-lastUART>2000)telemetry({connected,uart_live:false,jtag_connected:jtagConnected,fpga_detected:fpgaDetected});},300);

$('upload-password').addEventListener('input',render);
