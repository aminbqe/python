"""AX309 remote lab. Hardware agent uses the authenticated /agent WebSocket."""
import asyncio
import json
import os
import secrets
import re
import io
import zipfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, RedirectResponse
from pydantic import BaseModel, Field
from converter import inspect as inspect_verilog, generate
from upload_auth import verify_password
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
UPLOADS = ROOT / 'uploads'
UPLOADS.mkdir(exist_ok=True)
app = FastAPI()
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
agent = None
clients = set()
job = None
state = {'connected': False, 'uart_live': False, 'jtag_connected': None, 'fpga_detected': None, 'result': None,
         'leds': None, 'digits': None, 'switches': None}
lock = asyncio.Lock()
MAX_SIZE = 8 * 1024 * 1024
EXPORTS = ROOT / 'exports'
EXPORTS.mkdir(exist_ok=True)
EXPORT_TTL = 24 * 60 * 60


@app.middleware('http')
async def download_diagnostics(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/verilog/download/'):
        entry = {'time': time.time(), 'path': request.url.path,
                 'method': request.method, 'status': response.status_code,
                 'agent': request.headers.get('user-agent', ''),
                 'range': request.headers.get('range'),
                 'length': response.headers.get('content-length')}
        with (ROOT / 'download-diagnostics.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps(entry) + '\n')
    return response


async def broadcast(message):
    for client in tuple(clients):
        try:
            await client.send_json(message)
        except Exception:
            clients.discard(client)


@app.get('/')
async def index():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.post('/api/upload')
async def upload(file: UploadFile, request: Request):
    global job
    password_hash = os.getenv('UPLOAD_PASSWORD_HASH', '')
    if not password_hash:
        raise HTTPException(503, 'آپلود فعلاً فعال نیست')
    if not verify_password(request.headers.get('x-upload-password', ''), password_hash):
        raise HTTPException(401, 'رمز آپلود درست نیست')
    # This local prototype has a single exclusive session, not a multiuser queue.
    if not file.filename or not file.filename.lower().endswith('.bit'):
        raise HTTPException(400, 'فقط فایل .bit پذیرفته می‌شود')
    async with lock:
        if agent is None:
            raise HTTPException(503, 'عامل سخت‌افزار متصل نیست')
        if job is not None:
            raise HTTPException(409, 'برد در حال استفاده است؛ ابتدا جلسه را پایان دهید')
        data = await file.read(MAX_SIZE + 1)
        if not data or len(data) > MAX_SIZE:
            raise HTTPException(400, 'فایل باید بین ۱ بایت و ۸ مگابایت باشد')
        # Xilinx .bit header magic. Device/pin compatibility must also be
        # checked by the hardware agent before programming.
        if not data.startswith(bytes.fromhex('00090ff00ff00ff00ff000')):
            raise HTTPException(400, 'سرآیند فایل بیت‌استریم Xilinx معتبر نیست')
        identifier = secrets.token_hex(16)
        path = UPLOADS / (identifier + '.bit')
        path.write_bytes(data)
        job = {'id': identifier, 'name': Path(file.filename).name, 'status': 'programming', 'started': time.time()}
        try:
            await agent.send_json({'type': 'program', 'job': job, 'download': '/api/bitstream/' + identifier})
        except Exception:
            path.unlink(missing_ok=True)
            job = None
            raise HTTPException(503, 'ارتباط عامل قطع شد')
        await broadcast({'type': 'job', 'job': job})
        return job


class InspectRequest(BaseModel):
    source: str = Field(max_length=128000)


class ConvertRequest(InspectRequest):
    top: str = Field(max_length=128)
    mapping: dict[str, str]


@app.post('/api/verilog/inspect')
async def inspect_design(payload: InspectRequest):
    try:
        return {'modules': inspect_verilog(payload.source)}
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.post('/api/verilog/convert')
async def convert_design(payload: ConvertRequest):
    try:
        archive = generate(payload.source, payload.top, payload.mapping)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return Response(archive, media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="AX309_lab_project.zip"'})


@app.post('/api/verilog/prepare-download')
async def prepare_download(payload: ConvertRequest):
    try:
        archive = generate(payload.source, payload.top, payload.mapping)
    except ValueError as error:
        raise HTTPException(400, str(error))
    now = time.time()
    for path in EXPORTS.glob('*.zip'):
        if now - path.stat().st_mtime > EXPORT_TTL:
            path.unlink(missing_ok=True)
    if len(list(EXPORTS.glob('*.zip'))) >= 128:
        raise HTTPException(429, 'چند دقیقه بعد دوباره تلاش کنید')
    token = secrets.token_urlsafe(24)
    (EXPORTS / (token + '.zip')).write_bytes(archive)
    return {'url': '/api/verilog/download/' + token + '/AX309_lab_project.zip'}


@app.post('/api/verilog/files')
async def project_files(payload: ConvertRequest):
    try:
        archive = generate(payload.source, payload.top, payload.mapping)
    except ValueError as error:
        raise HTTPException(400, str(error))
    with zipfile.ZipFile(io.BytesIO(archive)) as project:
        return {'files': [{'name': name, 'content': project.read(name).decode('utf-8')}
                          for name in project.namelist()]}


@app.api_route('/api/verilog/download/{token}', methods=['GET', 'HEAD'])
@app.api_route('/api/verilog/download/{token}/AX309_lab_project.zip', methods=['GET', 'HEAD'])
async def download_export(token: str, name: str = 'AX309_lab_project.zip'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
        raise HTTPException(404)
    path = EXPORTS / (token + '.zip')
    if not path.is_file() or time.time() - path.stat().st_mtime > EXPORT_TTL:
        raise HTTPException(404, 'لینک منقضی شده؛ پروژه را دوباره آماده کنید')
    filename = name if re.fullmatch(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.zip', name) else 'AX309_lab_project.zip'
    return FileResponse(path, filename=filename, media_type='application/zip', headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@app.get('/api/bitstream/{identifier}')
async def bitstream(identifier: str, request: Request):
    token = os.getenv('AGENT_TOKEN', '')
    if not token or not secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + token):
        raise HTTPException(403)
    if job is None or identifier != job['id']:
        raise HTTPException(404)
    return FileResponse(UPLOADS / (identifier + '.bit'))


@app.websocket('/ws')
async def browser(ws: WebSocket):
    # Reject cross-origin control requests. Put authentication in front of
    # this service before exposing it outside a trusted local network.
    origin = ws.headers.get('origin', '')
    from urllib.parse import urlparse
    if origin and urlparse(origin).netloc != ws.headers.get('host'):
        await ws.close(code=1008)
        return
    await ws.accept()
    clients.add(ws)
    await ws.send_json({'type': 'state', **state})
    await ws.send_json({'type': 'job', 'job': job})
    try:
        while True:
            message = await ws.receive_json()
            if agent is None or job is None or job['status'] != 'running':
                await ws.send_json({'type': 'log', 'text': 'کنترل برد فقط هنگام اجرای جلسه فعال است'})
                continue
            if message.get('type') == 'input' and message.get('kind') in ('button', 'switch'):
                index, value = message.get('index'), message.get('value')
                if type(index) is int and 0 <= index < 4 and type(value) is bool:
                    await agent.send_json({'type': 'input', 'job_id': job['id'], 'kind': message['kind'], 'index': index, 'value': value})
            elif message.get('type') == 'stop':
                await agent.send_json({'type': 'stop', 'job_id': job['id']})
            elif message.get('type') == 'reset':
                await agent.send_json({'type': 'reset', 'job_id': job['id']})
            elif message.get('type') == 'values':
                a, b = message.get('a'), message.get('b')
                if type(a) is int and type(b) is int and 0 <= a <= 0xffffffff and 0 <= b <= 0xffffffff:
                    await agent.send_json({'type': 'values', 'a': a, 'b': b})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        clients.discard(ws)


@app.websocket('/agent')
async def hardware(ws: WebSocket):
    global agent, job
    token = os.getenv('AGENT_TOKEN', '')
    if not token or not secrets.compare_digest(ws.headers.get('authorization', ''), 'Bearer ' + token):
        await ws.close(code=1008)
        return
    if agent is not None:
        await ws.close(code=1008)
        return
    await ws.accept()
    agent = ws
    state.update(connected=True, uart_live=False, jtag_connected=None, fpga_detected=None, result=None,
                 leds=None, digits=None, switches=None)
    await broadcast({'type': 'state', **state})
    try:
        while True:
            message = await ws.receive_json()
            if message.get('type') == 'adopt' and job is None:
                job = {'id': 'live-' + secrets.token_hex(8), 'name': 'طرح فعلی روی برد', 'status': 'running', 'started': time.time()}
                await ws.send_json({'type': 'adopted', 'job_id': job['id']})
                await broadcast({'type': 'job', 'job': job})
            elif message.get('type') == 'hardware':
                if 'jtag_connected' in message:
                    state['jtag_connected'] = message['jtag_connected'] is True
                if 'fpga_detected' in message:
                    state['fpga_detected'] = message['fpga_detected'] is True
                await broadcast({'type': 'state', **state})
            elif message.get('type') == 'telemetry':
                leds, digits = message.get('leds'), message.get('digits')
                if message.get('uart_live') is False:
                    state.update(leds=None, digits=None, result=None, uart_live=False)
                elif message.get('uart_live') is True:
                    state['uart_live'] = True
                    state['result'] = message.get('result')
                    state['switches'] = message.get('switches')
                if isinstance(leds, list) and len(leds) == 4 and all(type(v) is bool for v in leds):
                    state['leds'] = leds
                if isinstance(digits, list) and len(digits) == 6 and all(type(v) is int and 0 <= v <= 255 for v in digits):
                    state['digits'] = digits
                await broadcast({'type': 'state', **state})
            elif message.get('type') == 'log':
                await broadcast({'type': 'log', 'text': str(message.get('text', ''))[:2000]})
            elif message.get('type') == 'status' and job and message.get('job_id') == job['id']:
                status = message.get('status')
                if status in ('running', 'error', 'stopped'):
                    job['status'] = status
                    await broadcast({'type': 'job', 'job': job})
                    if status in ('error', 'stopped'):
                        (UPLOADS / (job['id'] + '.bit')).unlink(missing_ok=True)
                        job = None
                        await broadcast({'type': 'job', 'job': None})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        agent = None
        state.update(connected=False, leds=None, digits=None, switches=None, result=None, uart_live=False, fpga_detected=None, jtag_connected=None)
        if job:
            (UPLOADS / (job['id'] + '.bit')).unlink(missing_ok=True)
            job = None
        await broadcast({'type': 'state', **state})
        await broadcast({'type': 'job', 'job': None})


# Serve the same lab under /rasp/ while preserving local agent URLs.
lab_app = app
app = FastAPI()
@app.get('/rasp')
async def rasp_redirect():
    return RedirectResponse('/rasp/', status_code=307)

app.mount('/rasp', lab_app)
app.mount('/', lab_app)
