"""Loopback DNS relay over the local authenticated upstream VPN connection."""
import concurrent.futures
import socket
import urllib.request


def main():
    proxy = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:10809'})
    opener = urllib.request.build_opener(proxy)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 1053))

    def respond(query, peer):
        if len(query) < 12:
            return
        try:
            req = urllib.request.Request(
                'https://cloudflare-dns.com/dns-query', data=query,
                headers={'Content-Type': 'application/dns-message',
                         'Accept': 'application/dns-message'})
            with opener.open(req, timeout=8) as response:
                answer = response.read(65536)
            if len(answer) >= 12 and answer[:2] == query[:2]:
                sock.sendto(answer, peer)
        except Exception:
            # SERVFAIL, preserving query ID and question; no credentials or queries logged.
            failed = query[:2] + bytes([query[2] | 128, (query[3] & 240) | 2])
            failed += query[4:6] + b'\0' * 6 + query[12:]
            sock.sendto(failed, peer)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            query, peer = sock.recvfrom(4096)
            pool.submit(respond, query, peer)


if __name__ == '__main__':
    main()
