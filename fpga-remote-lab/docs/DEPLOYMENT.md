# Deployment and troubleshooting

## Current public URLs

The physical laboratory panel is at `https://aminbagheri.com/rasp/`; the standalone converter is at `https://aminbagheri.com/fpga/`. The converter can run on ordinary web hosting. The JTAG/UART agent must run on the device physically connected to the FPGA.

## Public request path

```text
Browser -> HTTPS /rasp/ -> Cloudflare Worker
        -> tunnel origin hostname -> cloudflared on Raspberry Pi
        -> http://127.0.0.1:8000/rasp/
```

`deploy/cloudflare/rasp-worker.mjs` forwards uploads and WebSocket upgrades, validates the browser Origin before rewriting it, and blocks public agent access. Set `RASP_ORIGIN` to your tunnel's origin hostname. `wrangler.jsonc` describes the current route; adjust it for another domain.

For a named tunnel, connect the public origin hostname to `http://127.0.0.1:8000` with path `^/rasp(/.*)?$`. DNS and the Worker route must belong to the intended zone. Verify both ordinary web requests and WebSockets. Loading the Cloudflare dashboard does not establish that cloudflared can reach the edge network.

## Python deployment utility

`deploy/cloudflare/deploy_rasp.py` is a maintenance tool and is not required to run the server. The published version reads account ID, tunnel ID, and domain from environment variables. Create `.deploy-wheels/cloudflare-api-token.txt` locally and restrict its permissions. Keep this file and generated backups out of Git.

```sh
export CF_ACCOUNT_ID='your-account-id'
export CF_TUNNEL_ID='your-tunnel-id'
export CF_DOMAIN='your-domain.example'
python deploy/cloudflare/deploy_rasp.py
```

By default, the utility reads state and creates a backup and deployment plan. It expects an existing tunnel and Worker. `--apply` makes actual DNS, ingress, Worker, and route changes. Review the plan and backup first. Its DNS rules were designed to preserve the original domain's mail services and records; review those rules when using a different zone. The deployment API token is separate from the cloudflared runtime token.

## cPanel converter

`deploy/cpanel/fpga` contains the standalone HTML/JS/PHP converter. Place its contents in your hosting account's public `/fpga/` directory. PHP handles temporary ZIP storage and downloads and needs write access to the configured temporary location. Project generation runs in the browser; ISE does not run on the web host.

`deploy/build_cpanel.py` is the initial package builder. The final `core.js`, PHP handler, and download fixes are maintained in the prepared cPanel directory. Running the builder can overwrite final-package changes, so review its output before replacing deployed files. Use the prepared directory for the current deployment.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Upload returns 401 | Administrator: check your private password and hash configuration; the form clears its password after 401. Users should deliver files to the administrator rather than request the password. |
| Upload returns 503 | Password hash configuration or agent connectivity; inspect the response message |
| Upload returns 409 | A previous session still exists |
| JTAG works but UART is disconnected | Bitstream template, pin assignments, logic levels, serial console, and baud rate |
| FPGA is not detected | Board power, cable, FTDI serial number, USB permissions, and `openFPGALoader` output |
| Panel loads without live updates | WebSocket, Origin validation, route, and local agent connection |
| ZIP download fails in Chrome | File existence and retention, PHP endpoint, HTTP headers, and download-extension interference |
| Tunnel times out | cloudflared logs, edge reachability, and network routing; check TCP/UDP and HTTP/2 as appropriate |
| systemd reports a unit name containing `\x0d` | A script has CRLF line endings; convert them to LF |

Some networks require a dedicated proxy path. `tunnel_dns.py` provides a loopback DNS relay using DoH through a local proxy on port 10809. It does not create a VPN or TUN interface. VPN configurations, passwords, tunnel tokens, and private routing settings are excluded from this repository.

## Maintenance

Back up DNS and service settings before changing them. Keep `.env` at mode 0600 and preserve credentials during application updates. Remove the Worker route to disable public access. Stop the `fpga-lab` and `fpga-agent` user services to stop the application. Stopping the agent may leave the design held in reset.
