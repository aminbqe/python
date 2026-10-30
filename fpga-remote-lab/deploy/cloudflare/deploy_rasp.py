"""Deploy the approved /rasp/ route using a short-lived, scoped API token.

Default mode only reads and saves a reviewable plan. --apply performs the plan.
Credentials are loaded from the private workspace directory and never logged.
"""
import argparse
import copy
import datetime
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = os.getenv('CF_ACCOUNT_ID', '')
TUNNEL = os.getenv('CF_TUNNEL_ID', '')
DOMAIN = os.getenv('CF_DOMAIN', 'aminbagheri.com')
ORIGIN = 'rasp-origin.' + DOMAIN
WORKER = 'fpga-rasp-router'
PATTERN = DOMAIN + '/rasp*'


class API:
    def __init__(self):
        self.token = (ROOT / '.deploy-wheels/cloudflare-api-token.txt').read_text().strip()

    def raw(self, method, path, body=None, content_type='application/json'):
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode()
        req = urllib.request.Request('https://api.cloudflare.com/client/v4' + path,
            data=body, method=method, headers={
                'Authorization': 'Bearer ' + self.token,
                'Content-Type': content_type,
                'User-Agent': 'fpga-lab-deployment',
            })
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read(), response.headers.get('Content-Type', '')
        except urllib.error.HTTPError as error:
            # Cloudflare error messages may describe resources, but do not log headers.
            detail = error.read().decode(errors='replace').replace(self.token, '[REDACTED]')
            raise RuntimeError(f'Cloudflare {method} {path}: HTTP {error.code}: {detail[:700]}') from None

    def call(self, method, path, body=None):
        raw, _ = self.raw(method, path, body)
        obj = json.loads(raw)
        if not obj.get('success'):
            raise RuntimeError(f'Cloudflare {method} {path}: {obj.get("errors")}')
        return obj.get('result')


def dns_body(record):
    keys = ['type', 'name', 'content', 'ttl', 'proxied', 'priority', 'data', 'comment', 'tags']
    return {key: copy.deepcopy(record[key]) for key in keys if key in record}


def plan_dns(records):
    """Preserve the current host for non-web protocols before proxying the root."""
    roots = [r for r in records if r['name'].rstrip('.') == DOMAIN and r['type'] == 'A']
    if len(roots) != 1:
        raise ValueError('Expected exactly one apex A record; review DNS manually.')
    address = roots[0]['content']
    changes = []
    for record in records:
        name = record['name'].rstrip('.')
        before = dns_body(record)
        after = copy.deepcopy(before)
        if name == 'mail.' + DOMAIN and record['type'] == 'CNAME' and record['content'].rstrip('.') == DOMAIN:
            after.update(type='A', content=address, proxied=False)
        elif record['type'] == 'MX' and name == DOMAIN and record['content'].rstrip('.') == DOMAIN:
            after['content'] = 'mail.' + DOMAIN
        elif record['type'] == 'SRV':
            data = after.get('data') or {}
            if data.get('target', '').rstrip('.') == DOMAIN:
                if name.startswith(('_caldav.', '_caldavs.')):
                    replacement = 'cpcalendars.' + DOMAIN
                elif name.startswith(('_carddav.', '_carddavs.')):
                    replacement = 'cpcontacts.' + DOMAIN
                else:
                    raise ValueError('Unreviewed SRV record points to the apex: ' + name)
                matching = [r for r in records if r['name'].rstrip('.') == replacement and r['type'] == 'A']
                if len(matching) != 1 or matching[0]['content'] != address or matching[0].get('proxied'):
                    raise ValueError('Required DNS-only service hostname is unavailable: ' + replacement)
                data['target'] = replacement
                after['data'] = data
                # SRV content is generated from data by Cloudflare.
                after.pop('content', None)
        elif record is roots[0]:
            after['proxied'] = True
        elif name == 'www.' + DOMAIN and record['type'] == 'CNAME' and record['content'].rstrip('.') == DOMAIN:
            after['proxied'] = True
        if before != after:
            changes.append({'id': record['id'], 'before': before, 'after': after})
    # The root proxy switch must be last, after mail/service preservation.
    changes.sort(key=lambda c: c['after']['name'].rstrip('.') == DOMAIN and c['after']['type'] == 'A')
    return changes


def multipart_worker():
    boundary = 'fpga_' + secrets.token_hex(16)
    metadata = {'main_module': 'rasp-worker.mjs', 'compatibility_date': '2026-10-30',
                'bindings': [{'type': 'plain_text', 'name': 'RASP_ORIGIN', 'text': 'https://' + ORIGIN}]}
    parts = []
    for name, filename, kind, data in [
        ('metadata', None, 'application/json', json.dumps(metadata).encode()),
        ('rasp-worker.mjs', 'rasp-worker.mjs', 'application/javascript+module',
         (Path(__file__).parent / 'rasp-worker.mjs').read_bytes()),
    ]:
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        parts.append(f'--{boundary}\r\n{disposition}\r\nContent-Type: {kind}\r\n\r\n'.encode()
                     + data + b'\r\n')
    return b''.join(parts) + f'--{boundary}--\r\n'.encode(), 'multipart/form-data; boundary=' + boundary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not ACCOUNT or not TUNNEL or not DOMAIN:
        parser.error('Set CF_ACCOUNT_ID, CF_TUNNEL_ID and CF_DOMAIN for your deployment')
    api = API()
    zones = api.call('GET', '/zones?name=' + DOMAIN)
    if len(zones) != 1 or zones[0]['account']['id'] != ACCOUNT or zones[0]['status'] != 'active':
        raise RuntimeError('Unexpected domain account or status.')
    zid = zones[0]['id']
    zone_path = '/zones/' + zid
    account_path = '/accounts/' + ACCOUNT
    tunnel_path = account_path + '/cfd_tunnel/' + TUNNEL + '/configurations'
    worker_path = account_path + '/workers/scripts/' + WORKER
    records = api.call('GET', zone_path + '/dns_records?per_page=1000')
    tunnel = api.call('GET', tunnel_path)
    routes = api.call('GET', zone_path + '/workers/routes')
    config = copy.deepcopy(tunnel.get('config') or {})
    ingress = config.setdefault('ingress', [{'service': 'http_status:404'}])
    existing_origin = [r for r in ingress if r.get('hostname') == ORIGIN]
    rule = {'hostname': ORIGIN, 'path': '^/rasp(/.*)?$', 'service': 'http://127.0.0.1:8000'}
    if existing_origin and existing_origin != [rule]:
        raise RuntimeError('Origin hostname already has different ingress settings.')
    if not existing_origin:
        ingress.insert(0, rule)
    existing_dns = [r for r in records if r['name'].rstrip('.') == ORIGIN]
    origin_record = {'type': 'CNAME', 'name': ORIGIN, 'content': TUNNEL + '.cfargotunnel.com',
                     'proxied': True, 'ttl': 1, 'comment': 'FPGA lab tunnel origin'}
    if existing_dns and not (len(existing_dns) == 1 and existing_dns[0]['type'] == 'CNAME'
                            and existing_dns[0]['content'].rstrip('.') == origin_record['content']
                            and existing_dns[0].get('proxied')):
        raise RuntimeError('Origin DNS already exists with different settings.')
    matches = [r for r in routes if r['pattern'] == PATTERN]
    if matches and any(r.get('script') != WORKER for r in matches):
        raise RuntimeError('An existing route belongs to another Worker.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%SZ')
    backup = ROOT / 'backups' / ('cloudflare-rasp-' + stamp)
    backup.mkdir(parents=True)
    for name, value in [('zone', zones[0]), ('dns', records), ('tunnel', tunnel), ('routes', routes)]:
        (backup / (name + '.json')).write_text(json.dumps(value, indent=2))
    worker_before, worker_type = api.raw('GET', worker_path)
    (backup / 'worker-before.bin').write_bytes(worker_before)
    (backup / 'worker-before-content-type.txt').write_text(worker_type)
    subdomain = api.call('GET', worker_path + '/subdomain')
    (backup / 'worker-subdomain.json').write_text(json.dumps(subdomain, indent=2))
    changes = plan_dns(records)
    plan = {'dns_updates': changes, 'origin_record': origin_record, 'tunnel_config': config,
            'worker_route': {'pattern': PATTERN, 'script': WORKER}}
    (backup / 'plan.json').write_text(json.dumps(plan, indent=2))
    print('Backup:', backup, flush=True)
    for change in changes:
        print('Planned:', change['before']['type'], change['before']['name'], '->',
              change['after']['type'], change['after'].get('content', change['after'].get('data')), flush=True)
    if not args.apply:
        print('Read-only plan complete. No external changes made.', flush=True)
        return
    journal = []
    def record(step, rollback):
        journal.append({'step': step, 'rollback': rollback})
        (backup / 'journal.json').write_text(json.dumps(journal, indent=2))
        print('Applied:', step, flush=True)
    body, content_type = multipart_worker()
    raw, _ = api.raw('PUT', worker_path, body, content_type)
    if not json.loads(raw).get('success'):
        raise RuntimeError('Worker upload failed; inspect saved backup before continuing.')
    record('Worker code', {'method': 'PUT', 'path': worker_path,
                           'body_file': 'worker-before.bin', 'content_type': worker_type})
    api.call('PUT', tunnel_path, {'config': config})
    record('Tunnel ingress', {'method': 'PUT', 'path': tunnel_path,
                             'body': {'config': tunnel.get('config')}})
    if not existing_dns:
        result = api.call('POST', zone_path + '/dns_records', origin_record)
        record('Origin DNS', {'method': 'DELETE', 'path': zone_path + '/dns_records/' + result['id']})
    for change in changes:
        path = zone_path + '/dns_records/' + change['id']
        api.call('PUT', path, change['after'])
        record('DNS ' + change['after']['name'], {'method': 'PUT', 'path': path, 'body': change['before']})
    if not matches:
        result = api.call('POST', zone_path + '/workers/routes', plan['worker_route'])
        record('Public /rasp route', {'method': 'DELETE', 'path': zone_path + '/workers/routes/' + result['id']})
    api.call('POST', worker_path + '/subdomain', {'enabled': False, 'previews_enabled': False})
    record('Disable unused workers.dev endpoint', {'method': 'POST', 'path': worker_path + '/subdomain',
                                                  'body': subdomain})
    (ROOT / '.deploy-wheels/rasp-deployment-backup.txt').write_text(str(backup))
    print('Deployment submitted. Public HTTP and WebSocket verification still required.', flush=True)


if __name__ == '__main__':
    main()
