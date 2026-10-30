// Route aminbagheri.com/rasp* to the named Cloudflare Tunnel's origin hostname.
// RASP_ORIGIN is an HTTPS URL such as https://rasp-origin.aminbagheri.com.
export default {
  async fetch(request, env) {
    const original = new URL(request.url);
    if (original.pathname === '/rasp') {
      original.pathname = '/rasp/';
      return Response.redirect(original.href, 307);
    }
    if (!original.pathname.startsWith('/rasp/')) return fetch(request);

    let origin;
    try {
      origin = new URL(env.RASP_ORIGIN);
      if (origin.protocol !== 'https:' || origin.hostname === original.hostname
          || origin.username || origin.password || origin.port) throw new Error();
    } catch {
      return new Response('سرویس موقتاً در دسترس نیست.', { status: 503 });
    }

    // The hardware agent connects locally and must not use this public route.
    let path;
    try { path = decodeURIComponent(original.pathname).replace(/\/+/g, '/'); }
    catch { return new Response('Bad request', { status: 400 }); }
    if (path === '/rasp/agent' || path.startsWith('/rasp/agent/')) {
      return new Response('Not found', { status: 404 });
    }

    // Validate at the public boundary before translating Origin for the backend's
    // same-origin check. Never blindly rewrite an arbitrary browser Origin.
    const browserOrigin = request.headers.get('Origin');
    if (browserOrigin) {
      try {
        if (new URL(browserOrigin).origin !== original.origin) throw new Error();
      } catch {
        return new Response('Forbidden', { status: 403 });
      }
    }

    const destination = new URL(original.href);
    destination.hostname = origin.hostname;
    destination.port = '';
    const headers = new Headers(request.headers);
    headers.set('X-Forwarded-Host', original.host);
    headers.set('X-Forwarded-Proto', 'https');
    if (browserOrigin) headers.set('Origin', origin.origin);
    const upstreamRequest = new Request(destination, request);
    const forwarded = new Request(upstreamRequest, { headers, redirect: 'manual' });
    try {
      const upstream = await fetch(forwarded);
      // Preserve Cloudflare's WebSocket response object and stream unchanged.
      if (upstream.status === 101) return upstream;
      const response = new Response(upstream.body, upstream);
      response.headers.set('Cache-Control', 'no-store');
      const location = response.headers.get('Location');
      if (location) {
        const target = new URL(location, destination);
        if (target.hostname === origin.hostname) {
          target.hostname = original.hostname;
          target.port = original.port;
          response.headers.set('Location', target.href);
        }
      }
      return response;
    } catch {
      return new Response('ارتباط با آزمایشگاه موقتاً برقرار نیست.', {
        status: 502, headers: { 'Cache-Control': 'no-store' },
      });
    }
  },
};
