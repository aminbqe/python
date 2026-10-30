"""Conservative Verilog adapter generator. Never executes submitted code."""
import io
import json
import re
import zipfile
from pathlib import Path

TEMPLATE = Path(__file__).parent / 'hardware' / 'template'
IDENT = r'[A-Za-z_][A-Za-z0-9_$]*'
BUSES = {'switches': 4, 'buttons': 4, 'input_a': 32, 'input_b': 32}


def inspect(source):
    if not isinstance(source, str) or not source.strip() or len(source.encode()) > 128000:
        raise ValueError('سورس باید غیرخالی و حداکثر ۱۲۸ کیلوبایت باشد')
    clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    if '`' in clean or '\\' in clean:
        raise ValueError('این نسخه ماکرو، include و نام escape‌شده را پشتیبانی نمی‌کند')
    modules = []
    for match in re.finditer(r'\bmodule\s+(' + IDENT + r')\s*(.*?)\bendmodule\b', clean, re.S):
        name, text = match.groups()
        if text.lstrip().startswith('#'):
            raise ValueError('پارامترهای ماژول فعلاً پشتیبانی نمی‌شوند؛ مقدارها را ثابت کنید')
        header = re.match(r'\s*\((.*?)\)\s*;(.*)', text, re.S)
        if not header:
            raise ValueError('سرآیند ماژول پشتیبانی نمی‌شود: ' + name)
        ports_text, body = header.groups()
        if re.search(r'\binout\b', ports_text + body):
            raise ValueError('پورت دوطرفه inout در این قالب پشتیبانی نمی‌شود')
        ports = []

        def declarations(items, inherited=None):
            direction, msb, lsb = inherited or (None, 0, 0)
            for item in items:
                item = item.strip()
                declaration = re.match(r'^(input|output)\b\s*(.*)$', item, re.S)
                if declaration:
                    direction, item = declaration.groups()
                    msb = lsb = 0
                item = re.sub(r'\b(wire|reg|signed|unsigned)\b', '', item).strip()
                width = re.match(r'^\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*(.*)$', item, re.S)
                if width:
                    a, b, item = width.groups()
                    msb, lsb = int(a), int(b)
                    if msb < lsb:
                        raise ValueError('بازهٔ صعودی پشتیبانی نمی‌شود')
                if not direction or not re.fullmatch(IDENT, item) or msb-lsb+1 > 32:
                    raise ValueError('پورت نامعتبر یا پشتیبانی‌نشده: ' + item[:80])
                ports.append({'name': item, 'direction': direction, 'width': msb-lsb+1, 'lsb': lsb})

        if re.search(r'\b(input|output)\b', ports_text):
            declarations(ports_text.split(','))
        else:
            names = [s.strip() for s in ports_text.split(',') if s.strip()]
            for declaration in re.finditer(r'\b(input|output)\s+([^;]+);', body):
                declarations([declaration[1] + ' ' + declaration[2].split(',')[0]] + declaration[2].split(',')[1:])
            by_name = {p['name']: p for p in ports}
            if set(names) != set(by_name) or len(names) != len(ports):
                raise ValueError('تعریف پورت‌های ماژول کامل نیست')
            ports = [by_name[n] for n in names]
        if not ports or len({p['name'] for p in ports}) != len(ports):
            raise ValueError('پورت تکراری یا خالی است')
        modules.append({'name': name, 'ports': ports})
    if not modules or len({m['name'] for m in modules}) != len(modules):
        raise ValueError('ماژول معتبر با نام یکتا پیدا نشد')
    reserved = {'lab_top', 'user_logic', 'lab_uart_tx', 'lab_uart_rx', 'lab_bridge'}
    if any(m['name'] in reserved for m in modules):
        raise ValueError('نام ماژول با بخش ثابت قالب تداخل دارد؛ نام دیگری انتخاب کنید')
    return modules


def generate(source, top, mapping):
    modules = inspect(source)
    module = next((m for m in modules if m['name'] == top), None)
    if not module or not isinstance(mapping, dict):
        raise ValueError('ماژول اصلی و نگاشت معتبر انتخاب کنید')
    if set(mapping) != {p['name'] for p in module['ports']}:
        raise ValueError('برای همهٔ پورت‌ها نگاشت انتخاب کنید')
    lines = ['// Generated adapter. Edit mapping in the website, not this file.',
             'module user_logic(input wire clk, reset, input wire [3:0] switches, buttons,',
             ' input wire [31:0] input_a, input_b, output wire [3:0] leds, output wire [31:0] result);']
    outputs = {'leds': ["1'b0"]*4, 'result': ["1'b0"]*32}
    used = set()
    connections = []
    for index, p in enumerate(module['ports']):
        choice, width = mapping[p['name']], p['width']
        if not isinstance(choice, str):
            raise ValueError('نگاشت نامعتبر است')
        if p['direction'] == 'input':
            if choice == 'zero':
                expr = f"{width}'d0"
            elif choice in ('clk', 'reset') and width == 1:
                expr = choice
            else:
                found = re.fullmatch(r'(switches|buttons|input_a|input_b):(\d+)', choice)
                if not found:
                    raise ValueError('نگاشت ورودی نامعتبر: ' + p['name'])
                bus, start = found[1], int(found[2])
                if start + width > BUSES[bus]:
                    raise ValueError('عرض ورودی از ظرفیت قالب بیشتر است')
                expr = f'{bus}[{start+width-1}:{start}]'
        else:
            expr = f'port_{index}'
            lines.append(f'wire [{width-1}:0] {expr};')
            if choice != 'unused':
                found = re.fullmatch(r'(leds|result):(\d+)', choice)
                if not found:
                    raise ValueError('نگاشت خروجی نامعتبر: ' + p['name'])
                bus, start = found[1], int(found[2])
                if start + width > len(outputs[bus]):
                    raise ValueError('عرض خروجی از ظرفیت قالب بیشتر است')
                for bit in range(width):
                    if (bus, start+bit) in used:
                        raise ValueError('دو خروجی روی بیت مشترک نگاشت شده‌اند')
                    used.add((bus, start+bit))
                    outputs[bus][start+bit] = f'{expr}[{bit}]'
        connections.append(f'.{p["name"]}({expr})')
    lines.append(top + ' design_instance (' + ', '.join(connections) + ');')
    for bus, bits in outputs.items():
        lines.append('assign ' + bus + ' = {' + ', '.join(reversed(bits)) + '};')
    lines.append('endmodule\n')
    files = {p.name: p.read_bytes() for p in TEMPLATE.iterdir() if p.is_file()}
    files['design.v'] = source.encode()
    files['user_logic.v'] = '\n'.join(lines).encode()
    files['mapping.json'] = json.dumps({'top': top, 'ports': module['ports'], 'mapping': mapping}, indent=2).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return result.getvalue()
