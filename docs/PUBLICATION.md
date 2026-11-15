# Publication operations

The public repository is `shubhrgunjan/beyond-recovery`. The root Vercel configuration builds the public research home, report and downloads from committed source. Public settings are in `deployment/public.json`; credentials are held by the local GitHub/Vercel tools and never committed.

## Static publication

Run `npm ci`, `npm run build` and `npm run test:publication`. The builder writes ignored `public/`. It copies the report and supporting assets without running physics. Production Git pushes deploy through the connected Vercel project. For an explicit deployment with existing CLI authentication, use `npx vercel --prod`.

The research report and compact videos/tables stay available on Vercel independently of the live lab. The raw archives are GitHub Release assets. `deployment/dataset-index.json` records names, sizes, original relative directories and SHA-256 digests; `deployment/SHA256SUMS` verifies the initial raw release. Each `.tar.zst` file is below GitHub's per-asset size limit.

## Live Thor transport

The simulation server binds to Thor loopback at port 8080. A dedicated `br-public-tunnel` tmux session runs `cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8080`. Only this project service is exposed. No existing Tailscale routes are replaced.

The current transport is a Cloudflare Quick Tunnel. Its hostname changes when the tunnel process restarts, and it has no production uptime guarantee. The initial attempt to use Tailscale Funnel was unavailable under the current machine/tailnet permissions. A persistent named tunnel or an administrator-enabled dedicated Funnel would provide a more durable live origin.

After a tunnel restart, obtain the new public URL from that session's log, update `live` in `deployment/public.json` and `/lab` in `vercel.json`, rebuild/check, then push. The public site explains that the live robot is shared: visitors operate the same physics instance. Starting another trial saves and restarts the current trial. Static reports do not require Thor or a tunnel.

## Research-data release

On Thor, `scripts/export_public_dataset.py` freezes research study directories and baseline/live/training outputs into checksummed archives under ignored `artifacts/publication/`. Export when studies are idle so records are finalized. The script leaves original records in place. Inspect the release inputs before making them public.

Upload the resulting archives, `dataset-index.json` and `SHA256SUMS` to the research GitHub Release. Large data stays out of Git history and the Vercel build. The release also includes the compact report bundle. Preserve the original study source snapshots and launch plans when adding later experiments; do not overwrite an earlier study's raw evidence with corrected-controller runs.

A release uploader can receive a GitHub credential through stdin for one process; it never writes the credential to disk or includes it in a command argument. Source publishing excludes `.aws`, `.env*`, `.vercel`, caches, installed dependencies and raw archives. Verify public HTTP responses without authentication before handing out links.
