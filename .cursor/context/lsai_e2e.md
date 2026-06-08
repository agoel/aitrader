# End-to-end testing notes (generic)

*Vendor-neutral patterns. Your organization’s internal runbooks own commands, paths, and credentials.*

**Last updated:** 2026-05-05

---

## Stages (typical meanings)

Teams often use **three** names for depth of environment—exact definitions vary by org:

| Stage | Typical use |
|--------|-------------|
| **Alpha** | **Local or single-developer** environment: fast iteration, non-production data, safe to break. |
| **Beta** | **Shared staging**: closer to production, integrations and callbacks may point here; coordinate with your team before destructive actions. |
| **Gamma** | **Pre-release or one-box production-like** validation when staging is not enough; use only with approval. |

Match **your** org’s naming—some teams use only two tiers.

---

## Principles (product-agnostic)

### 1. Service readiness

Before calling HTTP APIs against a **locally started** server, confirm the process is **actually listening** (health check, log line, or probe)—not only that the parent process started. Races between “PID exists” and “port open” are common.

**Typical split for debugging:** separate **status** (running / stopped / error), **standard output** (request traces or injection logs), and **standard error** (framework and stack traces). Many frameworks log “listening on …” to **stderr** even when healthy—read both streams before concluding the server is ready.

**Timeouts:** If nothing becomes ready after a reasonable window (often several minutes for large apps), stop and inspect stderr for build or config errors before trying random port or flag changes.

### 2. Debug the test first

When an automated test fails, verify the **test** (expectations, inputs, ordering) before rewriting application code. If behavior changed intentionally, update the test; if not, fix the code.

### 3. Expectation and log gates

Treat **unexpected stderr / server errors** as a hard stop before adding more cases in the same session. Resolve or explain new errors so the next step starts from a known-good baseline.

### 4. Order and dependencies

Run **health / auth / prerequisites** before feature tests. If step B needs output from step A, keep that order in the suite.

### 5. Layered iteration

A practical loop:

1. Start the stack and wait until it is ready.  
2. Run a **small** set of tests for the current slice.  
3. Read application and test logs; fix **tests or code** until this slice is green.  
4. Record evidence for reviewers (what ran, pass/fail, notable log lines).  
5. Only then widen scope or add cases.

### 6. Documentation cadence

During a long automated pass: update **test data, logs, and scratch notes** as often as needed. **Batch-edit** durable “how we work” documents **after** a coherent pass finishes, so you are not thrashing shared prose every attempt.

### 7. Secrets and audit

- Do **not** commit passwords, API keys, session tokens, or cloud credentials.  
- Prefer environment variables or local config files that are **gitignored**.  
- Mask secrets in logs and screenshots used for evidence.

### 8. Object storage (if you use it)

For flows that **write** to object storage, **HTTP 200 alone** may not prove persistence. When your runbook requires it, add an explicit **read-back** check (list/get object) and record the key or id in your evidence.

### 9. Reporting “not applicable”

If a release or merge request has **no** beta or gamma run, state **“Not applicable”** with a one-line reason so reviewers know validation was considered.

---

## Build phases (generic pattern)

Many monorepos use **four** named phases—names vary (`clean`, `init`, `build`, `deploy` is one common set):

| Phase | Typical purpose |
|--------|-------------------|
| **Clean** | Remove artifacts (`dist/`, caches, old bundles) so the next build is reproducible. |
| **Init** | Prepare trees, install dependencies, generate config or code that other phases need. |
| **Build** | Compile, bundle, run tests that belong in CI for this slice. |
| **Deploy** | Often **restricted** to staging/production—may configure services, flip symlinks, or register versions. Some teams **skip** deploy on pure local (alpha) workstations. |

Phases can be run **alone** or **in order**; dependency order between packages should match your build graph. *Your* orchestration tool and flags live in internal docs—this table is only a shared vocabulary.

---

## Three kinds of automated checks (conceptual)

Teams often maintain:

1. **Endpoint / API tests** — JSON or tables describing HTTP method, path, body, expected status, and optional substrings or error codes. Suited for REST and RPC-style HTTP.  
2. **Auth / login tests** — valid and invalid credentials; secrets never committed.  
3. **Workflow tests** — multi-step scripts (call A, then B, assert on B’s response).  

All three benefit from the same **readiness** and **log-gating** rules above.

---

## Interstitial loop (one “layer” of work)

Borrowed from layered release practice; works for any stack:

1. **Start + readiness** — bring services up; wait until logs show the app is actually serving; fix startup failures **before** adding tests.  
2. **Execute tests** — run the smallest set that covers the change; add **negative** cases where contracts matter (`expected failure` with explicit messages).  
3. **Log + gate** — read stdout/stderr; if stderr shows new errors, fix or explain before expanding scope.

**When to add more tests:** After the current layer is green—not in the middle of a red build.

**When to commit:** After a full automated pass and evidence captured—not after every failing edit.

---

## Per-run evidence (append-only, generic)

For handoff and audits, an **append-only** log helps. Each block might include:

- **Run id** — stable label for the session (e.g. feature branch + date).  
- **Sequence** — incrementing number within that session.  
- **Started at** — local timestamp when the stack was started for this try.  
- **What changed** — short list of files or areas touched.  
- **Outcome** — pass/fail, which tests ran, link to stderr excerpt if something new appeared.

A separate **error log** can record only **new** stderr lines (dedupe by run id + sequence) so reviewers do not chase the same stack trace twice.

---

## REST-style tests (generic pattern)

Many teams drive integration tests from **declarative data** (JSON or similar):

- Request method and path (or action name)  
- Optional body  
- Expected HTTP status  
- Optional substring in body, or structured field checks  
- For **expected failures:** `expected_status`, optional `expected_code` or message fragment so the runner reports an explicit pass when denial is correct  

Keep cases **small and numbered** by **layer** or **feature slice**; expand the suite only after the current slice is stable.

---

## Alpha harness for local API testing (pattern)

**Purpose:** On **alpha** (localhost or a single-developer machine), many teams use a **short, repeatable loop**: start the HTTP app, wait until it is **actually serving**, run **declarative** tests (often JSON-driven) against that base URL, then read logs before adding more cases. This section restores that **recipe shape** in a vendor-neutral way—you map **your** start/stop scripts and test runner in the **Org template** below.

### What you usually need

1. **Start / stop** — a consistent way to launch and tear down the API process (wrapper script, `make` target, IDE run config, etc.).  
2. **Readiness, not just “process up”** — separate visibility into **status** (running / stopped / error), **stdout**, and **stderr**. Many stacks log **“listening”** lines to **stderr**; treating “PID exists” as ready causes flaky tests.  
3. **A test runner** — reads your case file(s), performs HTTP calls, compares status/body/error expectations, exits non-zero on failure (Python script, `pytest` + `httpx`/`requests`, CLI from your platform, etc.).  
4. **Auth for logged-in routes** — session id, bearer token, or cookie from **your** login flow; document how operators obtain it **without** committing secrets.  
5. **Optional** — dev-only **injection** or seed data if your team relies on it; keep it disabled outside alpha.

### Three common runner families (names vary by repo)

| Family | What it stresses |
|--------|------------------|
| **Endpoint / API** | One-shot requests: method, path, body, expected status, optional body checks. |
| **Auth / login** | Valid and invalid credentials; session or token establishment. |
| **Workflow** | Ordered multi-step flows (A then B then C) with state carried between steps. |

All three use the same **readiness** and **stderr gating** habits as **Interstitial loop** above.

### Example — Flask development server (readiness cue only)

If you run **`flask run`** or `app.run(debug=True)` locally, **Werkzeug** often prints a line like **`Running on http://127.0.0.1:5000`** to **stderr** when the server is accepting connections, along with **`Press CTRL+C to quit`**. A practical gate is: **those lines present** and **no traceback** above them in the same stream. **Ports and frameworks differ**—use whatever **your** app prints; the point is to **wait for a real listen signal**, not only for the parent shell to return.

### Typical 3-step loop (one “layer” of alpha work)

1. **Start + readiness** — start the server; wait for **your** ready signals; if startup fails, fix build/config (often rerun **clean / init / build** per **your** runbook) **before** adding tests.  
2. **Execute** — run the smallest endpoint or workflow batch against `<ALPHA_BASE_URL>`; use a **`--live`** (or equivalent) flag only when you intend to hit the real local server.  
3. **Log + gate** — confirm **no new unexpected stderr**; append **Per-run evidence**; **stop** the server when the automated slice is done if the next slice needs a clean process.

### Starter / watcher script (`run_rest.sh` pattern — not in this bundle)

In larger monorepos the alpha loop is often wrapped by a **small shell script** historically named **`run_rest.sh`**: it **starts** or **stops** the dev API process and **captures** **stdout**, **stderr**, **PID**, and a simple **status** file under **your** `<LOG_OR_STATUS_DIR>` (see org template). Typical responsibilities:

- **CLI** — e.g. `run_rest.sh --app <profile> start|stop` (flags are yours to define).  
- **Start** — launch your real entrypoint (**`rest.py`**, **`flask run`**, **`uvicorn`**, etc.) in the **background**; redirect or tee streams to files such as `*.std_out`, `*.std_err`, `*.pid`, `*.status` (`running` / `stopped` / `error`).  
- **Stop** — read **PID** and signal the process cleanly.  
- **Optional** — a tiny **`wait_until_ready`** helper (shell loop or Python) that polls **stderr** until **`<READY_SIGNAL>`** or a timeout—same readiness rules as the Flask example above.

**This repository’s generic bundle does not ship `run_rest.sh`**—paths and interpreters differ for every customer. It is **straightforward to author** with your coding agent: provide your **venv Python path**, **module that runs the dev server**, **port**, and **directory for logs**; ask for idempotent start/stop and no secret embedding.

---

## Org template — plug in **your** alpha harness

Replace every placeholder with **your** commands, paths, and flags. Keep the filled copy in **your** internal runbook or in **`.cursor/context/`** overlays; this bundle only documents the **pattern**.

| Placeholder | You fill in |
|-------------|-------------|
| `<SERVER_START>` | Command or script that starts the API for alpha (foreground or background per your convention). |
| `<SERVER_STOP>` | Clean shutdown (SIGTERM, wrapper `stop`, etc.). |
| `<READY_SIGNAL>` | Log line(s) or health check that means “accepting HTTP” (see Flask example above). |
| `<LOG_OR_STATUS_DIR>` | Where **stdout/stderr** or status files land, if your wrapper splits streams. |
| `<ALPHA_BASE_URL>` | e.g. `http://127.0.0.1:5000` — must match the listening address. |
| `<TEST_RUNNER>` | e.g. `python -m myapp.tools.api_tester` — **your** entrypoint. |
| `<RUNNER_FLAGS>` | Flags for case file, verbosity, `--live`, user/session, etc. |
| `<CASES_FILE>` | JSON/YAML/CSV path your runner understands. |
| `<SESSION_OR_TOKEN>` | How operators obtain auth material (helper script, env var, doc link). |

**Minimal case row shape** (adapt field names to your runner):

- HTTP method and path (or your routing convention)  
- Optional request body  
- Expected HTTP status  
- Optional substring or JSON path checks on success or error body  
- For **negative** tests: expected status and message fragment so “correct denial” counts as pass  

**Illustrative shell sequence (replace all placeholders):**

```bash
<SERVER_START>
# Block until <READY_SIGNAL> appears in the log stream you use for stderr/stdout.
<TEST_RUNNER> <RUNNER_FLAGS> --base-url <ALPHA_BASE_URL> --cases <CASES_FILE> \
  # plus <SESSION_OR_TOKEN> wiring your runner expects
<SERVER_STOP>
```

If you use **pytest**, **Newman**, or a **CI job** instead of a single script, keep the same **order**: readiness → run → gate logs.

---

## Alpha **Run / Verify** (template)

For each test or layer, document:

- **Run** — which filled values from **Org template** you use (`<TEST_RUNNER>`, `<CASES_FILE>`, `<ALPHA_BASE_URL>`, auth).  
- **Verify** — runner exit code **0**; **no new unexpected stderr** after readiness; if your runner prints explicit expectation lines (e.g. per-case PASS/FAIL), capture those in evidence.

This pairs well with merge-request **evidence** sections.

---

## Video-based UX debugging (expanded)

Assistants often cannot read binary video directly. Options:

1. **Attach** media if your tool supports automatic description.  
2. **Screenshots** of key moments (often enough for layout bugs).  
3. **Narrate** with timestamps if video cannot be processed.  
4. **Extract frames** with `ffmpeg` into a directory **outside the git repo** (e.g. under your user data folder), then analyze PNGs.

**Example — sample frames at roughly 1s intervals (adjust frame indices for your fps):**

```bash
mkdir -p "${HOME}/data/ux_bug_frames/my_session"
ffmpeg -i /path/to/recording.mp4 \
  -vf "select=eq(n\,0)+eq(n\,30)+eq(n\,60)+eq(n\,90)+eq(n\,120)" \
  -vsync vfr -q:v 2 \
  "${HOME}/data/ux_bug_frames/my_session/frame_%03d.png"
```

Install `ffmpeg` if needed (`which ffmpeg`). Prefer short clips; correlate stills with navigation or lifecycle in your app’s docs.

**UI-heavy bugs:** Treat **current** screenshots or frames as part of the “ground truth” for the turn—planning or coding without seeing the failure state often wastes iterations.

---

## Agent vision (UI dimension) — plain language

For bugs shown in **video or screenshots**, gather **visual state** (what is on screen, sequence of transitions) **before** deep code changes. Missing or stale UI context is a common cause of wrong fixes—same idea as needing correct logs for backend bugs.

---

## Remote staging: deployment patterns (template)

Use when your integration tests require a **shared remote** host (often called beta or staging)—for example webhooks, partner callbacks, or mobile clients that cannot target `localhost`.

### Fill in these placeholders first

| Placeholder | Meaning |
|-------------|---------|
| `<DEPLOY_TOOL>` | Your org’s CLI or CI job that runs clean/init/build/deploy (or equivalent). |
| `<APP>` | Environment or product name your build system recognizes. |
| `<STAGE>` | `beta`, `staging`, `gamma`, etc. |
| `<REMOTE_HOST>` | SSH hostname or IP of the staging box. |
| `<DEPLOY_ROOT>` | Directory on the remote where artifacts must exist (your runbook defines it). |
| `<WEB_RESTART_CMD>` | How the web tier reloads (e.g. `sudo systemctl reload apache2`, `nginx -s reload`, Kubernetes rollout). |

### Path A — First-time or full reset on staging

**When:** New environment, new major dependency, or you need a clean tree.

**Template workflow**

1. On the staging host: checkout the intended **branch/tag**; record `git diff --name-only <base>...HEAD` locally for evidence.  
2. Ensure **`<DEPLOY_ROOT>`** already exists and is owned by the right user—if the path is wrong, you may be on the wrong machine.  
3. Run your org’s **full pipeline** for **`<APP>`** / **`<STAGE>`**: typically **clean → init → build → deploy** (or your equivalent). **Deploy** may be disallowed for dev-only stages—follow internal policy.  
4. Append a row to your **deploy log** (see **Per-run evidence** and **Beta evidence** below): timestamp (staging clock), commit or build id, files changed summary.  
5. Run **warm-up** (next section) before hitting callbacks or load generators.  
6. Only then run integration tests, log babysitter, or backfill jobs.

### Path B — Fast iteration (copy changed artifacts only)

**When:** Staging already had a successful Path A; you changed a **small** set of server-side files.

**Template workflow**

1. From your machine: list changed paths (`git diff --name-only …`).  
2. Map each path to the **installed location** on staging (Python `site-packages`, static asset dir, etc.—your runbook).  
3. Copy with **`scp`**, **`rsync`**, or your release tool; avoid copying secrets.  
4. Run **`<WEB_RESTART_CMD>`** on **`<REMOTE_HOST>`** so workers pick up code.  
5. Wait **warm-up** (below), then run tests or triggers.  
6. Log the iteration in the same deploy log (increment **sequence**; keep the same **release / run id** until you cut a new release).

**Adapt:** Some teams use Docker/K8s only—replace steps 2–4 with **image build + push + rollout** and keep the same logging discipline.

---

## Beta / staging — remote operations recipe (pattern)

Use when work must run against a **shared remote** host (often called **beta** or **staging**): partner **webhooks**, mobile clients, or anything that cannot target `localhost`. This section **generalizes** an internal “beta ops” playbook: deploy modes, **log babysitting**, **remote vs local clocks**, and **“new error”** semantics—without product-specific hosts, buckets, or integration names.

### How it fits with Path A / Path B

- **Path A** — full reset on staging (checkout, full **clean → init → build → deploy** or your equivalent). Use when the environment is new or dependencies changed a lot.  
- **Path B** — fast loop: copy **only changed** artifacts to the installed paths on staging, restart the web tier, re-run triggers/tests. Use after at least one good Path A.

After either path, follow **Warm-up** before heavy triggers; append a block to **`interstitial_fixes.txt`** (see **Beta / remote evidence files** below).

### Log monitor (“babysitter”) — pattern

Goal: pull **recent error lines** from the staging web tier **without** logging in interactively every time. **Apache** on Debian/Ubuntu is a common layout: **`/var/log/apache2/error.log`** — adjust for **Nginx**, **systemd**, or containers per **Remote log analysis**.

**One-shot snapshot (typical):**

```bash
ssh -i "<SSH_KEY>" <USER>@<STAGING_HOST> \
  "tail -n <N> /var/log/apache2/error.log | grep -E -B <B> -A <A> '<APP_PATTERN>'"
```

- **`<N>`** — often 500–2000 lines for one incident window.  
- **`<APP_PATTERN>`** — stable substring from **your** app (route prefix, integration name, error code)—**not** a vendor-specific name from this template.

**Optional wrapper `<LOG_MONITOR_SCRIPT>`** — many teams wrap the above in a script with flags: `--host`, `--key`, `--tail`, `--pattern`, `--before`, `--after`, `--save ~/data/<stage>/<app>/apache_error_grep.txt`. Stream to stdout or to a **local** file; avoid leaving temp files **on the server**.

### Remote (server) time vs local time — **keep them straight**

This matters for **warm-up**, **throttles**, and **“is this error new?”**.

| Kind of event | Which clock to record | Why |
|---------------|----------------------|-----|
| Lines in **Apache / WSGI** logs | **Server time** embedded in the log line (or staging TZ) | Dedup and ordering must match what the web tier wrote. |
| **`interstitial_fixes.txt` — “Staging deploy at”** | **Staging host** time (or UTC if you standardize) | Aligns with server log timelines. |
| **Operator triggers** (start babysitter, kick job) | **Local laptop** time is fine if labeled **`(local)`** | Easier for the developer; do **not** use this to compare against Apache timestamps. |
| **Throttle (“do not rerun job before …”)** | Often **local** wall clock in a small state file | Document which clock you used. |

**Rule:** When deciding if an error is **new**, compare **server log timestamps** to the **previous** entry’s **server** time for the **same** release id—**not** your laptop clock.

### Parser / comparison habit

Whether you use **grep** or a **small script** (Python `re` over SSH output, etc.), **extract** the **timestamp** from each matching log line the same way every time (Apache common formats include `[Wed Jun 10 …]` or ISO-like prefixes—**your** distro may differ). Store **that parsed value** in `beta_error_log.txt` so humans and automation agree on ordering.

### Async jobs after deploy (generic)

If your product runs **date-window backfills**, **reindexes**, or **webhook-heavy** jobs:

- **Warm-up** — wait after **`<WEB_RESTART_CMD>`** before triggering (see table in **Warm-up**).  
- **Throttle** — do not rerun the same expensive job more often than your platform allows; track **last run** in a **local** file with **`(local)`** timestamp.  
- **Idempotency** — if the API returns **“already processed”** for a duplicate window, adjust the requested window per **your** API docs instead of hammering the same range.

**Org placeholders (beta)**

| Placeholder | You fill in |
|-------------|-------------|
| `<STAGING_HOST>` | SSH hostname or IP for staging. |
| `<SSH_KEY>` | Path to private key (mode `600`). |
| `<ERROR_LOG_PATH>` | e.g. `/var/log/apache2/error.log` or your unit’s log. |
| `<LOG_MONITOR_SCRIPT>` | Optional wrapper around SSH + tail + grep + save. |
| `<ASYNC_JOB_CMD>` | CLI or curl that triggers your backfill/reindex (if any). |

---

## Warm-up, throttle, and post-trigger waits (template)

Remote and async systems often need **deliberate delays** so you do not mis-triage race conditions.

| Rule | Typical starting point | How to adapt |
|------|------------------------|--------------|
| **Warm-up after deploy/restart** | Wait **60 seconds** after the web tier reports healthy before firing webhooks, backfills, or heavy tests. | Increase for slow cold starts; decrease only with metrics. |
| **Throttle between similar jobs** | Do not run the same **expensive** job (backfill, reindex, bulk export) more often than **5 minutes** unless your platform docs say otherwise. | Encode “last run at” in your log file (local timestamp). |
| **Post-trigger verification** | After triggering async work, wait **several minutes** before scraping logs or object storage for side effects—partners and queues are rarely synchronous. | Tune from observed p95 latency. |

**Template log lines** (append to your session log):

```text
Deploy finished at (staging): <YYYY-MM-DD HH:MM:SS TZ>
Warm-up complete at (local):   <YYYY-MM-DD HH:MM:SS>
Backfill/trigger started at:     <YYYY-MM-DD HH:MM:SS>
Next deploy/trigger allowed after: <timestamp per throttle rule>
```

---

## Remote log analysis (template)

Use when the bug **only reproduces on staging/production** or when you need **server** error lines (reverse proxy, WSGI, application stderr).

### 1. Identify the canonical error log path

Common locations (adapt to your distro and product):

- **Apache:** `/var/log/apache2/error.log`  
- **Nginx + PHP-FPM:** `/var/log/nginx/error.log` plus pool logs  
- **systemd unit:** `journalctl -u <unit> -n 200 --no-pager`  
- **Container:** `kubectl logs <pod>` or `docker logs <container>`

Your **internal** runbook should name the path for each **`<STAGE>`**.

### 2. One-shot snapshot (preferred for automation)

Pull the **last N lines**, filter by pattern, include **context** lines so stack traces stay readable.

**Template (SSH):**

```bash
ssh -i "<PATH_TO_SSH_PRIVATE_KEY>" <REMOTE_USER>@<REMOTE_HOST> \
  "tail -n <N> <ERROR_LOG_PATH> | grep -E -B <BEFORE_LINES> -A <AFTER_LINES> '<REGEX_PATTERN>'"
```

**You choose:**

- **`<N>`** — often 500–2000 for a single incident window.  
- **`<REGEX_PATTERN>`** — stable substrings from your app (request path, error code, integration name). Avoid overly broad patterns.  
- **`<BEFORE_LINES>` / `<AFTER_LINES>`** — often 5 and 10.

**Save locally** for MR evidence:

```bash
ssh ... "tail -n <N> <ERROR_LOG_PATH> | grep ..." > ./staging_error_snippet.txt
```

### 3. Interactive follow (when the issue is intermittent)

```bash
ssh -i "<PATH_TO_SSH_PRIVATE_KEY>" <REMOTE_USER>@<REMOTE_HOST>
# then on the server:
sudo tail -f <ERROR_LOG_PATH> | grep -E '<REGEX_PATTERN>'
```

Stop when you have a reproducible snippet; paste **only** non-secret lines into tickets.

### 4. Wrapper script pattern (optional)

Many teams wrap the SSH + `tail` + `grep` + optional save in a small script:

- **Inputs:** host, key path, log path, pattern, tail size, before/after, `--save <local_path>`.  
- **Output:** stdout, or file under e.g. `${HOME}/data/<stage>/<app>/remote_grep_<timestamp>.txt`.  
- **Security:** never embed credentials in the script; use SSH agent or `-i` with chmod `600` keys.

### 5. When logs are not enough

Correlate with **request ids**, **trace ids**, or **upstream partner dashboards** if your app emits them. For **object-backed** flows, pair log lines with **object storage verification** (next major section).

---

## Beta / remote evidence files (local machine template)

Keep **append-only** artifacts on the **developer laptop** (or CI workspace) so MR reviewers can see what happened without SSH access. **All paths here are on the operator machine** unless you explicitly SSH to staging.

**Suggested layout** (adapt names):

```text
${HOME}/data/<stage>/<app>/
  interstitial_fixes.txt      # deploy + test sequence blocks
  beta_error_log.txt          # or staging_error_log.txt — deduped errors
  backfilled_dates.txt        # optional — one ISO date per line if you run date-window jobs
  branch_changed_files_list.txt
  apache_error_grep.txt       # optional — saved output from <LOG_MONITOR_SCRIPT>
```

### Block format for `interstitial_fixes.txt` (example)

Use **staging/server** time for deploy lines when possible; label **local** actions explicitly.

```text
Release id: <branch_or_tag_or_MR_id>
Sequence: <n>
Staging deploy at: <timestamp> (staging — from staging host clock or log)
Backfill/trigger run at: <timestamp> (local)   # optional
Files changed: <short list or git range>
Notes: <what you tested>
---
```

### When is an error “new”? (deduplication template)

Treat an error as **new** if **either**:

- **Release id** changed since the last logged error, **or**  
- **Release id** is the same **and** the **parsed server timestamp** from the error log line is **strictly after** the previous entry’s **server** time for that release.

**Do not** compare Apache timestamps to laptop **local** time unless you have a defined offset and automation applies it—prefer **raw log timestamps** copied into the evidence file.

**Multi-line template for `beta_error_log.txt`** (easy for humans and scripts):

```text
Release id: <id>
Sequence: <n>
Server time (staging): <yyyy-mm-dd HH:MM:SS>   # parsed from error.log line
Summary: <one line in your words>
error clip:
  <paste 5–20 log lines, redact secrets>
---
```

A **one-line** variant is also fine if your tooling prefers it:

```text
Release id: <id> | Seq: <n> | Server time (staging): <timestamp> | Summary: <one line>
```

### Optional: small parser script

A **short Python or awk** program can: read the last `beta_error_log.txt` entry, SSH + tail the log, **regex-parse** timestamps from new matches, and print **NEW** vs **SEEN**—keeping **server time** in one column throughout. This reduces mistakes when logs are busy.

---

## Object storage (S3-compatible): retrieval, verification, cleanup (template)

Applies to AWS S3, MinIO, GCS with S3 API, etc. Replace **vendor CLI** names if your org uses another tool.

### Placeholders

| Placeholder | Example role |
|-------------|----------------|
| `<CREDENTIAL_SETUP>` | `aws configure`, `aws sso login`, `. ./env.sh` — **your** approved method. |
| `<BUCKET>` | Per-stage bucket name. |
| `<PREFIX>` | Key prefix for the feature (`users/...`, `superagent/...`, `indexed/...`). |

### A. Fail-closed credential rule

- Credentials must exist **before** any `ls`/`cp`/`rm`.  
- If they are missing: **stop**—do not paste secrets from chat into CI logs.  
- Prefer **short-lived** roles or SSO over long-lived keys where possible.

### B. Download an object (read path)

```bash
# After <CREDENTIAL_SETUP>:
aws s3 cp "s3://<BUCKET>/<KEY>" "/tmp/<LOCAL_NAME>"
# Verify file exists and matches expected magic bytes / headers
```

**Adapt:** Add `--profile`, `--endpoint-url` for MinIO or non-AWS endpoints.

### C. Positive verification after a write (read-after-write)

**Rule:** Do **not** trust HTTP 200 alone for persistence-critical flows.

**Template after an API call that should create `s3://<BUCKET>/<KEY>`:**

```bash
aws s3 ls "s3://<BUCKET>/<PREFIX_CONTAINING_KEY>/"
aws s3 cp "s3://<BUCKET>/<KEY>" -
```

Record in evidence: **full key**, **size**, and a **redacted** payload snippet (ids only—no PII).

**Negative test template:** For “must not write” cases, `ls` the forbidden prefix and assert **zero** new objects matching the pattern.

### D. List prefix and sample keys

```bash
aws s3 ls "s3://<BUCKET>/<PREFIX>/" --recursive | head -n 50
```

Use to discover actual key shapes before writing grep-heavy shell.

### E. Cleanup / reset (destructive — gated)

**When:** Isolated test account, explicit approval, or disposable prefix only.

```bash
aws s3 rm "s3://<BUCKET>/<PREFIX>/" --recursive
```

**Never** run recursive delete against **production** shared prefixes without a **written** blast-radius review. Prefer **per-test prefixes** or **lifecycle rules** for junk data.

### F. SuperAgent-style layout (generic)

If your product stores **routers and agents** under a prefix, a common shape is:

```text
s3://<BUCKET>/superagent/<provider_id>/router.md
s3://<BUCKET>/superagent/<provider_id>/l345_router.md
s3://<BUCKET>/superagent/<provider_id>/router_catalog.md
s3://<BUCKET>/superagent/<provider_id>/agents/<name>.md
```

**Normal:** publish via **API** after session/auth. **Emergency:** some teams allow `aws s3 cp` from a trusted machine—treat as **break-glass** and document in MR. **Cleanup:** `rm` the test `provider_id` prefix only.

---

## Structured remote data: ledgers and NDJSON (template)

Many products store **append-only or line-oriented** artifacts in object storage:

- **NDJSON** — one JSON object per line; good for crawlers, indexers, audit trails.  
- **Fields** often include: resource id, status, last attempt time, retry count, opaque metadata.

**Template analysis on a downloaded file:**

```bash
wc -l downloaded.ndjson
head -n 5 downloaded.ndjson
grep '"status":"failed"' downloaded.ndjson | head
```

**Adapt:** For large files, stream with `jq`/`python` instead of loading entirely into memory.

---

## Change-request / MR reporting: remote stages (template)

When your process has **Alpha / Beta / Gamma** sections:

- **Alpha** — point to local or CI logs + test JSON.  
- **Beta / remote** — point to **staging deploy log**, **SSH grep snippets** (saved files), and **object-storage verification** keys (redacted).  
- **Gamma** — same as beta but stricter about prod-like data; often “Not applicable” for pure docs MRs.

**Interstitial subsection title (example):**  
`Release <N>: Layer <K> — Remote staging interstitial runs`

Under it, numbered **Run 1, Run 2, …** with: command, host, outcome, link to artifact file.

Use **Not applicable (reason)** when no remote run occurred—see **Principles (product-agnostic)** — **9. Reporting “not applicable”** in this file.

---

## What we stripped from the internal version

The long **organization-specific** `lsai_e2e.md` in internal repos named concrete products, buckets, host IPs, SSH key paths, Garmin/Offer flows, and proprietary script filenames. **Those literals are not copied here.** The sections above are **templates**: substitute your runbook’s paths, credentials, and policies. Keep using your **internal** document when you need exact, audited commands.
