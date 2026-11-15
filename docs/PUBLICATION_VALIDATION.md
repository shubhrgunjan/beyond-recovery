# Public publication verification

Public origins:

- Research site: https://beyond-recovery.vercel.app/
- Report: https://beyond-recovery.vercel.app/report/
- Downloads: https://beyond-recovery.vercel.app/downloads/
- Live entry point: https://beyond-recovery.vercel.app/lab
- Source: https://github.com/shubhrgunjan/beyond-recovery
- Data release: https://github.com/shubhrgunjan/beyond-recovery/releases/tag/research-2026-11-15

## Checks completed on 2026-11-15

- Anonymous HTTP 200 from the home, report, downloads page, a scientific figure and a CSV table.
- HTTP 206 for an unauthenticated byte-range request to a published video.
- `/lab` returns an HTTP 307 to the current Thor tunnel origin.
- Anonymous GitHub API access confirms the source repository is public.
- The static build passes 54 internal asset/link/anchor checks with `npm run test:publication`.
- The offline report ZIP passes its integrity check; its navigation uses public URLs and its figures, videos and data are included.
- A real public HTTPS/WebSocket integration test connected to the simulator, started a named verification trial, paused/resumed, advanced exactly one 20 ms step, finalized the recording and verified all nine saved artifact URLs. Run: `20261115-122042-b5cd2a`. The service was returned to its ready scene.
- The original Python project suite contains sixteen passing tests. Publication changes did not retrain policies or alter the recorded research outcomes.

No connected browser surface was available for automated visual interaction. HTTP, protocol, asset and build checks are verified; this document does not claim browser screenshot/layout testing.

The live lab uses a shared native MuJoCo instance on Thor and a Cloudflare Quick Tunnel. Its availability depends on both processes remaining online, and the tunnel address changes after restart. The Vercel report and GitHub data release remain independent of that live transport.

The research release consists of ten checksummed raw archives totaling 4,598,179,255 bytes, plus the archive index, checksum list and compact offline report bundle. Release publication includes a final comparison against GitHub's server-side asset digests. Raw data is outside Git history and the Vercel build.
