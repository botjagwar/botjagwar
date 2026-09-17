# Botjagwar

Bot-Jagwar is a side project that automates editing on the Malagasy Wiktionary.


## Build status

| Branch  | Status                                                                                                                                 |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| dev  | [![Unit tests](https://github.com/botjagwar/botjagwar/actions/workflows/unit-tests.yml/badge.svg?branch=dev)](https://github.com/botjagwar/botjagwar/actions/workflows/unit-tests.yml) |

## Prerequisites

- Linux-like environment (Windows users can use WSL).
- Python 3.11 or later with the built-in `venv` module.
- Node.js 22 or later for frontend development. The installation scripts install or upgrade Node.js automatically when needed.
- `uv` is used for Python package management; `install.sh` bootstraps it when missing.
- PostgreSQL 11 or later, configured through `conf/config.ini` in a source checkout or `/etc/botjagwar/config.ini` after installation. SQLite remains supported for tests and small local setups.
- Redis is optional for counters and degraded-mode diagnostics, but is required for persistent Atlas job status and coordinated live Wikimedia access. Counter and error diagnostics fall back locally when Redis is unavailable; tracked jobs and uncached Wikimedia requests fail closed instead of disappearing behind the load balancer or multiplying upstream traffic.

### Optional translation services

- `install-ctranslate.sh` installs standalone NLLB/CTranslate support into `/opt/ctranslate` using `requirements-ctranslate.txt`.
- Place the int8 CTranslate2 model at `~/nllb-200-3.3B-int8` before running the installer; it is copied to `/opt/ctranslate`.
- `ctranslate.py` uses the Transformers model at `/opt/ctranslate/nllb-200-3.3B` by default.
- `ctranslate-lite.py` uses a CTranslate2 model at `/opt/ctranslate/nllb-200-3.3B-int8` and expects `flores200_sacrebleu_tokenizer_spm.model` inside that directory. It is faster and lighter than `ctranslate.py`, so `conf/supervisor-ctranslate.conf` runs it by default.
- Round-trip translation validation uses the `BAAI/bge-small-en` Sentence Transformers model in the standalone CTranslate environment. `gensim` is only needed for offline vector-population scripts or when `CTRANSLATE_EMBEDDING_MODEL` explicitly selects a Gensim model.
- NLLB round-trip validation is enabled by default. Atlas persists its toggle under **Settings > NLLB translation controls** and applies changes to new definition translations without restarting services. Disabling it skips only the back-translation comparison; repeated-output checks remain active. Direct callers that omit the per-request override use `CTRANSLATE_ROUNDTRIP_VALIDATION` as the fallback.
- `install-gemma.sh` installs a standalone OpenAI-compatible chat service into `/opt/gemma`. Download `gemma-4-E2B-it-Q4_K_M.gguf` from `unsloth/gemma-4-E2B-it-GGUF` to `~/gemma-4-E2B-it-GGUF/` first; the installer never downloads model files. A CUDA toolkit and C++ compiler are required because llama.cpp is built for the host CPU with CUDA enabled. The runtime keeps all model layers on the GPU by default. Override the source file with `GEMMA_SOURCE_DIR`, use `GEMMA_DEVICE=cpu` to disable GPU offload, and override the generation limit with `GEMMA_MAX_TOKENS` when needed. The page checker uses this service to generate Simple English fixes before NLLB translation. Atlas can also enable a Basic English gate that sends English definitions longer than six words with less than 75% vocabulary coverage to Gemma before NLLB translation; configure its endpoint under `[gemma]` in `config.ini`. Atlas's Gemma workspace uses the same endpoint for a session-only, multi-turn chat and keeps its URL and optional API key behind the authenticated server gateway. The endpoint can be updated deployment-wide under **Settings > Remote model endpoint**; public URLs must use HTTPS, while private and loopback IP addresses may use HTTP. Gemma listens on all IPv4 interfaces; restrict port `8891` with a firewall or another network access control because the model API does not authenticate requests.

Optional dependencies are listed in `optional_requirements.txt` and include Redis, NLTK, Torch/Transformers/SentencePiece, `gensim`, and `pgvector`. Definition and NLLB embeddings are optional and are not mapped by the service ORM. To enable them, install the pgvector PostgreSQL extension, apply the SQL files in `data/migrations/`, then install `gensim` and the Python `pgvector` package before running the vector-population scripts. Install only the other dependencies required by the features you run.

## Installation

For a first installation, create the ignored source-checkout configuration and protect it before adding credentials:

```bash
install -m 0600 conf/config.example.ini conf/config.ini
```

Configure an active `database_uri`, RabbitMQ credentials, the AMQP broker under `[rabbitmq] host`, and a stable deployment-specific `[wiktionary_review] environment_id`. Run `python scripts/validate_config.py conf/config.ini`, then run `install.sh`. The installer migrates this file to `/etc/botjagwar/config.ini`, builds and validates a versioned release before atomically activating it, and retains the previous release for automatic rollback. Existing protected configuration is never replaced, but its owner and mode `0600` are repaired on reinstall.

The production layout separates immutable application files from machine configuration and writable state:

```text
/opt/botjagwar/releases/<release-id>  versioned backend and frontend artifacts
/opt/botjagwar/current                symlink to the active release
/etc/botjagwar/deployment.ini         declarative service and network policy
/etc/botjagwar/config.ini             protected application and database settings
/etc/botjagwar/pgrest                 active protected PostgREST configuration
/etc/botjagwar/nginx                  Atlas credentials and upstream configuration
/var/lib/botjagwar/user_data          logs, caches, and other writable application data
/var/lib/botjagwar/atlas              Atlas logs and operational state
```

Installation is serialized with `/opt/botjagwar/.install.lock`. Completed releases contain `.release-complete`; interrupted builds cannot be activated. After a successful activation, the installer automatically prunes old releases and their release-specific runtime configuration. Five releases are retained by default, including the active and rollback versions. Set `BOTJAGWAR_KEEP_RELEASES` to a value from 2 through 20 when installing to change retention. Existing explicit deployment retention settings are preserved across reinstalls.

To prune an existing installation to five releases immediately:

```bash
sudo python3 /opt/botjagwar/current/scripts/release_manager.py \
  --root /opt/botjagwar \
  --config-root /etc/botjagwar \
  prune --keep 5
```

On the first versioned installation, existing flat backend and frontend installations are copied into a `legacy-<release-id>` rollback release before compatibility paths are switched. Existing commands under `/opt/botjagwar` and `/opt/botjagwar-front` continue to work through symlinks, but new automation should use `/opt/botjagwar/current`.

For the standalone NLLB translation service, place the converted model directory at `~/nllb-200-3.3B-int8` and run `install-ctranslate.sh`.

For the standalone page-check model service, download `gemma-4-E2B-it-Q4_K_M.gguf` from `unsloth/gemma-4-E2B-it-GGUF` to `~/gemma-4-E2B-it-GGUF/` and run `install-gemma.sh`. It binds to `0.0.0.0:8891`, exposes `/health` and `/v1/chat/completions`, and runs as the single `gemma` Supervisor program. Restrict access to port `8891` at the network layer. Then configure the protected `config.ini`:

```ini
[global]
page_checker_model_api_url = http://127.0.0.1:8891/v1/chat/completions
page_checker_model = gemma-4-e2b-it-q4-k-m
page_checker_model_api_key =
```

The legacy `deepseek_api_key` and `deepseek_model` settings remain the fallback when the `page_checker_model_*` settings are absent. Restart the entry-translator processes after changing this configuration.

If you intend to edit Wiktionary with the bot, set up a Pywikibot instance. See the [Pywikibot installation manual](https://www.mediawiki.org/wiki/Manual:Pywikibot/Installation) for details.

`conf/config.ini` remains relevant only to source-checkout commands, including the project-local OpenCode MCP launcher, and is intentionally ignored by Git. Installed Supervisor programs set `BOTJAGWAR_CONFIG=/etc/botjagwar/config.ini`, making that protected file authoritative and preventing home-directory overrides. Keep both files mode `0600` and never add their machine-specific values to shared changes.

To confirm a working installation, run `test.sh`. All tests should pass. Some tests may fail on a Raspberry Pi because temporary files are not always deleted during teardowns.

## Development guidelines

Common code style and architecture guidance lives in `AGENTS.md` and `pyproject.toml`.

## Running

Start each component from `/opt/botjagwar/current`:

```bash
python3 wiktionary_irc.py        # IRC recent-changes listener
python3 english_wiktionary_cache_irc.py  # English Wiktionary Redis cache listener
python3 dictionary_service.py    # dictionary storage REST API on port 8001
python3 entry_translator_v2.py   # translation/publishing REST API on port 8000
python3 tenymalagasy_mirror.py   # cached tenymalagasy.org mirror on port 8004
```

Alternatively, use the generated `conf/supervisor-botjagwar.conf` to run the components as supervised services. The `english_wiktionary_cache_irc` process subscribes to `#en.wiktionary`, refreshes cached wikitext after edits and creations, removes deleted pages, and renames cached keys after page moves. The mirror is included as the singleton `tenymalagasy_mirror` program and stores its database under the persistent deployment state directory. The Supervisor and HAProxy files are rendered from the templates in `conf/` during installation. The `wiktionary-review` MCP server is not a Supervisor daemon: OpenCode starts the local stdio server from `opencode.json` and owns its lifetime.

## Components and scripts

### Real-time lemma translator

Connects to the recent-changes IRC feeds of the French, English, and Malagasy Wiktionaries on `irc.wikimedia.org`. French and English edits enter a bounded, deduplicated local queue whose single worker submits tracked translation jobs without blocking the IRC callback. On `mg.wiktionary`, the listener watches main-namespace edits from the server-managed user whitelist, excludes configured exact edit summaries, samples matching edits at the configured probability, queues sampled titles for page checking, and uses the configured cooldown to pace submissions. Page checks queue generated fixes for publication to Wiktionary.

#### `wiktionary_irc.py`

IRC client that connects to the entry translator v2 REST API for translations and page-check submissions. Change the IRC page-check settings in Atlas. The defaults are a `Bot-Jagwar` user whitelist, a 10% sampling probability, a 5-second submission cooldown, and ignored edit summaries of `fanitsiana famaritana` and `Dikanteny: es`. Generated page-check fixes are sent to the RabbitMQ queue configured by `[rabbitmq] page_check_queue`, which defaults to `translated`; restart the entry-translator processes after changing it. Queue workers discard a page-check edit if the live target changed after the fix was generated. Page checks that end as `unverifiable` or `error` are sent to the separate durable queue configured by `[rabbitmq] page_check_review_queue`, which defaults to `page-check-review`. Review records are evidence for a human workflow and are never sent directly to the executable edit queue. Review handoffs use a stable event ID, a Redis lease across translator processes, and health-cycle retries so a broker outage or interrupted worker does not strand the terminal job.

#### `rabbitmq_entry_translator.py`

Consumes source recent changes from the `edit2` RabbitMQ queue. Ordinary page edits are submitted for translation without a per-message cooldown. When `localhost:8000/jobs` reports more than 30 active jobs, the consumer waits two seconds before polling again. A true `Special:Log/delete` page-deletion event instead marks the same title on Malagasy Wiktionary with `{{fafao}}`; missing Malagasy pages and pages already carrying a speedy-deletion template are left unchanged.

Page-check lookups for tenymalagasy.org go through `tenymalagasy_mirror.py`. The mirror listens on loopback by default, stores successful and not-found upstream responses in the SQLite database configured by `[tenymalagasy] database_path`, and reuses them without an expiry. Start it before the entry translator; set `[tenymalagasy] mirror_url` if it is not available at `http://127.0.0.1:8004`.

#### Manual page-check review with OpenCode

The project `opencode.json` registers a local `wiktionary-review` MCP server, and `.opencode/skills/review-wiktionary-fixes/SKILL.md` defines the required review workflow. Configure a stable deployment-specific `[wiktionary_review] environment_id` and keep `page_check_review_queue` distinct from the executable `page_check_queue` and generic worker queue. Publishers connect directly to AMQP with the configured RabbitMQ username and password. In a source checkout, install `requirements.txt` in the Python environment inherited by OpenCode, start the configured RabbitMQ services and entry translator, then restart OpenCode so it loads the project configuration.

```bash
ROOT="$(git rev-parse --show-toplevel)"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install uv
"$ROOT/.venv/bin/uv" pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
opencode
```

Switch to the dedicated `wiktionary-review` primary agent, ask it to load `review-wiktionary-fixes`, and review the next failed page check. That agent denies shell, file editing, web access, subagents, and publication queueing so untrusted evidence cannot cross the approval boundary. The MCP launcher and virtual-environment example resolve the Git worktree root, so the project integration also works when OpenCode starts in a subdirectory.

The MCP server acknowledges a `page-check-review` delivery only after storing it in a local SQLite inbox. By default the inbox is below `${XDG_STATE_HOME:-~/.local/state}/botjagwar/<environment-fingerprint>/`; the fingerprint binds the deployment ID, test/production mode, translator endpoint, RabbitMQ destination, and queue names. Override it with an absolute `BOTJAGWAR_WIKTIONARY_REVIEW_DB` path. `BOTJAGWAR_ENTRY_TRANSLATOR_URL` overrides the default `http://127.0.0.1:8000`, and `BOTJAGWAR_PAGE_CHECK_REVIEW_QUEUE` overrides `page-check-review`. Approved edits use `[rabbitmq] page_check_queue`, normally `translated`. Schema migration invalidates legacy unqueued proposals rather than carrying approval across environments.

OpenCode may inspect and prepare a proposal without publishing it. Snapshot content, parsed entries, and proposal diffs are position-addressed chunks. After preparation, the workflow must fetch the stored proposal again from diff offset 0 and carry the returned `diff_review_token` while reading every chunk contiguously within ten minutes. This token records review completeness but is not proof of human approval. A snapshot still returns exact raw content and its hash if parsing fails, with `parsed` set to false and parsed entries omitted. OpenCode must show the complete stored unified diff and approval contract, then provide the proposal ID and approval digest without queueing anything.

Run the approval command yourself in a separate trusted terminal, never through an OpenCode tool. It requires interactive terminal input and output, independently reloads and displays the complete hash-bound contract and safely escaped diff, and accepts only the proposal-specific confirmation phrase it shows. It has no noninteractive approval option and does not retry an uncertain queue outcome.

```bash
ROOT="$(git rev-parse --show-toplevel)"
"$ROOT/.venv/bin/python" -m api.wiktionary_review_cli \
  --proposal-id 'wiktionary-fix:<approval-digest>' \
  --approval-digest '<approval-digest>'
```

The trusted-terminal command uses an owner-token lease, recomputes the complete approval contract and diff, refreshes both English reference and Malagasy target pages, and rejects stale hashes before sending the exact approved Malagasy page to `page_check_queue`. Approval expires after one hour. The queued message uses the same full-page contract as the entry translator, including `expected_content_sha256`, so the normal consumer rejects a write if the Malagasy page changed after queueing. RabbitMQ forwarding uses durable queues, persistent messages, mandatory routing, and publisher confirms. A successful approval-command result means RabbitMQ accepted the edit request; it does not confirm that the Wiktionary consumer published it.

#### `dictionary_service.py`

Word storage engine and REST API used by `wiktionary_irc.py` to store and retrieve translations.

The database backend is configured with `database_uri` in the active configuration file via SQLAlchemy. The service has been tested on PostgreSQL, SQLite, and MySQL. PostgreSQL is recommended for production and for use with the frontend application.

##### Front-end application

The React administration frontend in `frontend/` provides:

- schema-aware CRUD access to all physical tables exposed by PostgREST;
- read-only browsing for ordinary and materialized views;
- a human-readable Wiktionary page explorer backed by `entry_translator_v2`, including definitions, translations, and additional data;
- complete dictionary-entry workflows through `dictionary_service`;
- page previews, translation previews, background jobs, publishing, health data, and recent errors through `entry_translator_v2`.
- live dashboard counts for new entries and the most translated source languages across rolling and calendar periods;
- bounded browser-session tracking for multiple translation jobs, readable processed previews, detailed translator capacity telemetry, and read-only live Wiktionary snapshots with content hashes;
- page-check history filters, explicit publication warnings, a server-managed translation publication prefilter, and manual-review handoff status for failed or unverifiable checks;
- an Atlas-wide job center that keeps translation polling active across navigation and combines tracked translation work with page-check jobs from recently used languages;
- definition-sharing impact details before dictionary edits, relation row inspection and exports, bookmarkable relation browsing state, and searchable/exportable operation records;
- a source-first Malagasy interface with an English translation that can be switched instantly from the global header; the preference is retained in the browser.
- browser-persisted Atlas, Windows 98, Windows XP, and Mac OS interface themes selectable from the Settings page.

For English Wiktionary pages, the explorer preserves source order and scopes
additional data by language and part of speech while following numbered
etymology branches. Branches with the same language and part of speech remain
merged by the entry model. Directly encoded data includes etymologies,
headwords and transcriptions, examples and
quotations, references, alternative forms, descendants, all standard lexical
relation sections, IPA/audio/enPR/hyphenation/rhyme/homophone data, Wikipedia
and Wikidata targets, and explicit literal meanings. Directly encoded
citations retain source titles in their original language. Recognized English
and ISO dates are localized in Malagasy, inline page references use `pejy`,
and `Tsiahy` template page parameters remain compatible with the source
template. Descendant lists are also exposed recursively in processed-page API
and Atlas previews; this tree is neither persisted nor published and is bounded to 32
levels, 2,000 nodes, and 1 MB across each processed-page response. Individual
terms and metadata values are capped at 512 characters, with 16 labels per
node. The existing flat descendant metadata remains available as an unchanged
fallback. Generated inflection tables, expanded language-specific pronunciation
templates, template-generated descendant branches, ruby, and sense-level
Wiktextract metadata are not synthesized because those require template/module
expansion.

When publishing to Malagasy Wiktionary, pronunciation templates named
`{language-code}-pr` are mapped to `{language-code}-IPA`; template parameters
and unrelated pronunciation templates are preserved.

English-to-Malagasy translations also translate fully recognised etymology
origin, comparison, and word-formation clauses with deterministic rules. Terms
and supported wiki links or formatting are preserved; free-form prose or
unsupported templates fail closed and remain in source metadata without being
published as a Malagasy etymology section.

For local development, start PostgREST on port 8100, `dictionary_service` on port 8001, and `entry_translator_v2` on port 8000. Then run:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api/database`, `/api/dictionary`, and `/api/translator` to those services. Override the browser API roots with `VITE_POSTGREST_URL`, `VITE_DICTIONARY_URL`, or `VITE_TRANSLATOR_URL` when needed.

Atlas writes require the authenticated operation gateway so every mutation has a persistent audit record. For local frontend development, create a temporary token and run the gateway in a second shell before starting Vite:

```bash
token=$(openssl rand -hex 32)
printf '%s\n' "$token" > /tmp/atlas-gateway.token
python supervisor_control_service.py \
  --config /tmp/atlas-supervisor.ini \
  --token-file /tmp/atlas-gateway.token \
  --audit-db /tmp/atlas-operations.sqlite3

ATLAS_GATEWAY_TOKEN="$token" ATLAS_USERNAME=developer npm run dev --prefix frontend
```

The Supervisor configuration may be absent when only database, dictionary, and translator auditing is needed. Reads remain available when the operation gateway is stopped, but Atlas deliberately blocks mutations that cannot first be audited.

Text searches in the PostgREST data explorer are debounced until one second after the final keystroke to avoid issuing a request for every character.

Word Atlas definitions link known Malagasy headwords to internal Atlas pages, prefer the longest matching phrase, and link each target only once per definition. Apply `data/migrations/005_add_linkable_lexicon_headwords.sql` to expose the compact PostgREST candidate endpoint used by Atlas and the Wiktionary renderer. Hover or focus a definition link to load a cached definition preview; browser Back and Forward preserve linked-word navigation.

To build and deploy the frontend, run the root `install.sh`. It includes the static build and Nginx configuration in the same versioned release as the backend, validates the production Nginx configuration, obtains a Let's Encrypt certificate when needed, and installs the `botjagwar_atlas` Supervisor program under the current user. Atlas starts automatically and serves HTTPS on port 38000.

Atlas has no default hostname. Set the deployment's DNS hostname and optionally provide a certificate-expiry email when installing:

```bash
ATLAS_DOMAIN=atlas.example.com \
ATLAS_CERTBOT_EMAIL=admin@example.com \
bash install.sh
```

The installed certificate command also accepts an explicit domain argument, which takes precedence over `ATLAS_DOMAIN`:

```bash
/opt/botjagwar/current/frontend/setup-tls.sh --domain atlas.example.com
```

The selected hostname must resolve to the server, and inbound TCP ports 80 and 38000 must be reachable. The system Nginx serves the Certbot HTTP challenge on port 80 and redirects other requests to `https://<hostname>:38000`. Certificate material is retained in `/opt/botjagwar-certs`, outside the replaceable application folders. When that directory already contains readable `fullchain.pem` and `privkey.pem` files, installation skips certificate generation entirely. A renewal hook updates this persistent directory and restarts only `botjagwar_atlas` after the initial Certbot setup.

All Atlas pages and proxied APIs are protected by Nginx HTTP Basic Authentication inside the TLS connection. On first installation, the installer creates the `atlas` user with a cryptographically random password and prints the credential once. Set `ATLAS_USERNAME` and `ATLAS_PASSWORD` when running `install.sh` to supply the initial credential instead.

Use Supervisor to control the production instance:

```bash
sudo supervisorctl status botjagwar_atlas
sudo supervisorctl restart botjagwar_atlas
sudo supervisorctl stop botjagwar_atlas
sudo supervisorctl start botjagwar_atlas
```

Atlas also provides a **Services** workspace for status, start, and stop operations on explicitly allowlisted remote Supervisor programs. The browser talks only to the same-origin `/api/services` endpoint; a loopback-only control gateway keeps remote addresses, credentials, and program allowlists on the Atlas server.

The same authenticated gateway maintains an append-only Operations audit at `/var/lib/botjagwar/atlas_operations.sqlite3`, outside the replaceable application directory. Atlas records database mutations, dictionary changes, queued or synchronous publishing, and Supervisor start/stop attempts without retaining request payloads or credentials. The Operations workspace identifies the HTTP Basic Auth user supplied by the trusted Nginx proxy and shows pending, successful, and failed outcomes. Back up this file with the rest of the persistent deployment data and define an operational retention policy appropriate for the deployment.

Configure a remote Botjagwar host with the installed command. It generates fresh RPC credentials, installs a loopback-only Supervisor listener over SSH, adds a source-restricted `/RPC2` location to the remote Atlas HTTPS server, verifies the endpoint and allowlisted programs, and updates `/etc/botjagwar/supervisor-control.ini` on the local Atlas host:

```bash
/opt/botjagwar/current/bin/configure-atlas-supervisor \
  --host dictionary \
  --label "Dictionary backend" \
  --address 192.0.2.10 \
  --hostname dictionary.example.com \
  --atlas-source 192.0.2.20 \
  --ssh-target deploy@192.0.2.10 \
  --program dictionary_service_1 \
  --program dictionary_service_2
```

The remote account must authenticate with SSH and have non-interactive `sudo` access. The hostname must use a certificate trusted by the Atlas host, and `--atlas-source` must be the source address the remote server sees for Atlas connections. Repeat `--program` for every service Atlas may control. Rerunning the command rotates the generated RPC password and replaces only that host's managed entries. Programs including `botjagwar_atlas`, `supervisor_control_service`, `load_balancer`, and `jenkins` are deliberately forbidden.

For non-Botjagwar remote Nginx layouts, use `--remote-nginx-location`, `--remote-nginx-prefix`, `--remote-nginx-config`, and `--remote-nginx-program`. The selected Nginx server must include the chosen RPC location file inside its TLS `server` block; Botjagwar defaults to persistent `/etc/botjagwar/supervisor-rpc-location.conf`. Manual Atlas host definitions can still be based on `conf/supervisor-control.example.ini`; keep `/etc/botjagwar/supervisor-control.ini` at mode `0600` and restart `supervisor_control_service` after changes.

Remote Supervisor XML-RPC must be authenticated and encrypted. Supervisor's built-in `inet_http_server` is HTTP-only, so bind it to loopback or a private interface, place it behind a verified HTTPS reverse proxy, and firewall that TLS listener so only the Atlas host can connect. The URL stored in Atlas must use `https://`; plaintext HTTP is accepted only for a Supervisor on the Atlas host itself. A minimal remote Supervisor listener is:

```ini
[inet_http_server]
port = 127.0.0.1:9001
username = atlas-control
password = a-long-random-password
```

Terminate TLS in front of `127.0.0.1:9001/RPC2`, use a certificate trusted by the Atlas host, and expose only `/RPC2`. Do not expose the raw Supervisor listener to the network. The Services workspace never accepts arbitrary hosts, commands, groups, or program names from the browser.

Backend HAProxy ports remain loopback-only by default. For an Atlas deployment on a separate trusted host, expose only the four managed frontends to Atlas's source address, validate HAProxy, and restart `load_balancer`:

```bash
/opt/botjagwar/current/pyenv/bin/python /opt/botjagwar/current/scripts/configure_haproxy_network.py \
  --allow-source 192.168.1.30/32
sudo /usr/sbin/haproxy -c -f /etc/botjagwar/haproxy.cfg
sudo supervisorctl restart load_balancer
```

The remote-access command binds managed frontends to all IPv4 interfaces (`0.0.0.0`) by default, while the source ACL rejects clients outside the supplied network even on a private interface. Loopback remains implicitly allowed for local deployment health checks. Pass `--bind-address` only to intentionally restrict HAProxy to one interface. The command updates both `/etc/botjagwar/haproxy.cfg` and the network policy in `/etc/botjagwar/deployment.ini`, so later releases retain it. Set `REGENERATE_HAPROXY=1` during installation only when intentionally returning managed frontends to the loopback-only template.

`/etc/botjagwar/deployment.ini` is the durable source for service counts, pool autostart, release retention, HAProxy bind address, and allowed source networks. Installation environment variables are explicit overrides and are written into the next manifest revision. Existing generated Supervisor counts and managed HAProxy network policy are imported when no manifest exists.

The service pool sizes default to six `dictionary_service` processes, ten `entry_translator` processes, ten PostgREST processes, and three CTranslate `translator` processes. Override them during installation while keeping Supervisor and HAProxy consistent:

```bash
DICTIONARY_SERVICE_INSTANCES=8 \
ENTRY_TRANSLATOR_INSTANCES=12 \
POSTGREST_INSTANCES=6 \
TRANSLATOR_INSTANCES=2 \
bash install.sh
```

PostgREST supports up to 16 generated instances; port 8100 remains reserved for HAProxy. Run `scripts/render_service_configs.py` directly with the same environment variables to regenerate the checked-in configuration examples. Set `NO_AUTOSTART=1` while running either installer or the renderer to set `autostart=false` on every generated service-pool process.

Atlas can be reconfigured without rebuilding it. Open the **Settings** workspace to set ordered PostgREST, `dictionary_service`, and `entry_translator` address lists for the current browser. Use **Reload configuration** to fetch the deployed `config.json` again without reloading the page; browser-local overrides remain in effect. Atlas retries reads against later addresses when an earlier service is unavailable; write operations use only the first address to avoid duplicate mutations.

Use the installed server-side command to change production upstream pools or the protected database URI:

```bash
/opt/botjagwar/current/frontend/configure-atlas.sh --interactive

/opt/botjagwar/current/frontend/configure-atlas.sh \
  --postgrest '127.0.0.1:8100,127.0.0.1:8101' \
  --dictionary-service '127.0.0.1:8001,127.0.0.1:28001' \
  --entry-translator '127.0.0.1:8000,127.0.0.1:18000'
```

Use `--interactive` or pipe a database URI to `--database-uri-stdin` so database credentials do not appear in shell history or the process list.

Rotate the HTTP authentication credential interactively, or pipe the password over standard input so it does not appear in shell history or the process list:

```bash
/opt/botjagwar/current/frontend/configure-atlas.sh --interactive

printf '%s\n' 'new-password' | \
  /opt/botjagwar/current/frontend/configure-atlas.sh --username atlas --password-stdin
```

The command updates authentication and Nginx upstream files, writes `database_uri` to Botjagwar's protected configuration, synchronizes PostgREST database URIs, validates Nginx, and restarts only `botjagwar_atlas`. Restart backend services separately when you are ready to apply a changed database URI. Service addresses must be HTTP host/port values without path components. Database credentials are never written to Atlas's browser-readable `config.json`; only a sanitized host/database label is exposed in Settings.

Runtime configuration and customized upstream pools are retained when `install.sh` is run again.

Root reinstalls retain `/etc/botjagwar/config.ini`, `/var/lib/botjagwar/user_data`, managed HAProxy network policy, Atlas runtime configuration, and existing service-pool sizes. Remote Supervisor listener and Nginx RPC configuration also live under `/etc`, outside release directories. Set the relevant instance-count environment variable to intentionally resize a pool during reinstall.

The production installer also schedules every materialized view in the configured PostgreSQL database to refresh daily at 00:45 and 12:45 in the server's local timezone. The job discovers views dynamically, refreshes dependencies first, and uses a PostgreSQL advisory lock to prevent overlapping runs. Output is written to `/var/lib/botjagwar/user_data/materialized_view_refresh.log`; the cron definition is installed at `/etc/cron.d/botjagwar-materialized-views`. A second cron job regenerates the Atlas dashboard statistics snapshot every five minutes and is installed at `/etc/cron.d/botjagwar-dashboard-statistics`. The dashboard job also attempts a page-check sample every five minutes; the first successful response in each canonical UTC half-hour bucket is retained, so transient failures can retry without creating extra trend points. Sampler output is written to `/var/lib/botjagwar/user_data/page_check_statistics_snapshot.log`. The dashboard job reads the `atlas_dashboard_statistics_mv` materialized view directly through the configured `database_uri` under `[global]` in the protected `conf/config.ini`; a file lock next to the snapshot prevents overlapping runs. It first refreshes that materialized view concurrently every five minutes with `refresh_atlas_dashboard_statistics_mv.py`, with refresh times recorded in `materialized_view_refresh_status`, then writes the JSON snapshot from its rows. Installation generates and validates an initial dashboard snapshot and verifies migrations 010 and 011 before activating a candidate release; a later deployment failure restores the previous dashboard cron definition. When the Atlas frontend serves a remote Botjagwar instance, set `BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE=host:path` during installation. Installation and the dashboard cron then fetch the JSON snapshot that host generates (via `fetch_dashboard_statistics.py`, which validates and atomically replaces the local file) instead of refreshing or validating local dashboard storage. The remote Botjagwar host remains responsible for migrations 010 and 011 and page-check sampling because Atlas reads that history through its remote PostgREST upstream.

To inspect releases and the active target:

```bash
readlink -f /opt/botjagwar/current
ls -1 /opt/botjagwar/releases
```

The installer rolls back application code, generated configuration, and managed services automatically after failed production health checks. Keep manual recovery coordinated through `install.sh`, because changing only the `current` symlink does not also select that release's protected PostgREST, HAProxy, and Supervisor configuration.

Apply `data/migrations/006_add_atlas_dashboard_statistics.sql`, `007_track_entry_and_translation_creation.sql`, `008_add_atlas_dashboard_statistics_mv.sql`, `010_add_page_check_statistics_snapshots.sql`, and `011_score_good_page_check_jobs.sql` before every fresh production installation. Migration 007 adds database-generated immutable `word.created_at` values for new entries and records append-only events when non-Malagasy entries acquire Malagasy definitions. Existing words continue to use `date_changed` as the best available creation-time fallback without a disruptive table rewrite. Translation activity begins when migration 007 is applied; when upgrading an existing database, run `data/migrations/009_backfill_dashboard_translation_events.sql` after migration 008 so periods before migration 007 (previous month, previous year) still report translated languages, then apply migrations 010 and 011. The backfill reconstructs history from Malagasy dictionary links using `word.date_changed` as the timestamp proxy and may take several minutes on large deployments. Dashboard calendar boundaries use UTC: “last week,” “previous month,” and “previous year” are complete calendar periods, while “last day” and “last 7 days” are rolling windows. Atlas precomputes these statistics every five minutes and writes the JSON snapshot to `/var/lib/botjagwar/atlas/logs/dashboard-statistics.json`. The dashboard reads the materialized view and page-check score history through the same-origin `/api/database` Nginx proxy (whose upstream is the configured PostgREST pool), so the browser never talks to a database directly. The browser re-fetches both dashboard statistics and page-check history every five minutes.

The **Settings** workspace can also refresh every materialized view immediately. This protected maintenance request runs the same dependency-aware routine and configured database URI as cron, cannot accept database names or SQL from the browser, and is recorded in the Operations audit. The configured PostgreSQL role must own the materialized views or otherwise have permission to refresh them, as required by the cron job. To avoid elevating the normal application role, set `materialized_view_database_uri` under `[global]` in the protected `/etc/botjagwar/config.ini` to a dedicated materialized-view owner; refresh jobs prefer it over `database_uri`. Keep the page open while the request runs; large deployments may take several minutes.

The database and translation services do not currently authenticate requests. Protect the Nginx listener with authentication or a network allowlist before exposing this administration frontend outside a trusted network.

You may alternatively use the older companion frontend: [botjagwar-frontend](https://github.com/radomd92/botjagwar-frontend).

The frontend uses Vue.js and Nginx. With a PostgreSQL backend, PostgREST is used to offload read operations from `dictionary_service`. Nginx proxies requests to either `dictionary_service` or the PostgREST API.

#### `entry_translator_v2.py`

Wiki page handler that uses translation and page-rendering APIs. Its side effects are page updates and creations on the target wiki. REST service required by `wiktionary_irc.py`.

Canonical endpoints:

- `GET /swagger.json` — returns the generated Swagger 2.0 specification
- `GET /health`
- `GET /jobs`
- `GET /jobs/errors`
- `GET /page-checker/settings` — returns the server-managed page-check and autonomous-agent settings
- `PUT /page-checker/settings` — updates the server-managed IRC monitoring settings
- `PUT /page-checker/settings/autonomous-agent` — enables or disables automatic GitHub fix-agent assignment
- `PUT /page-checker/settings/translation-prefilter` — enables or disables page-check verification of translated candidates before publication
- `PUT /page-checker/settings/job-history` — changes the Atlas page-check history and statistics window from 1 to 100,000 jobs
- `POST /wiktionary-pages/{language}/jobs` — returns HTTP 202 with a durable tracked translation job; source loading happens in the bounded worker, and callers may supply a UUID `request_id` to make retries idempotent
- `GET /wiktionary-pages/{language}/jobs/{job_id}` — returns the pending, running, completed, or failed translation job state
- `POST /wiktionary-pages/{language}/translations` — translates and publishes synchronously
- `POST /wiktionary-pages/{language}/check-jobs` — queues asynchronous page checks
- `GET /wiktionary-pages/{language}/check-jobs` — lists recent page-check jobs
- `GET /wiktionary-pages/{language}/check-jobs/statistics` — aggregates retained jobs over today, 7-day, week, month, 3-month, and 6-month UTC periods
- `GET /wiktionary-pages/{language}/check-jobs/{job_id}` — returns a page-check job and its results
- `GET /wiktionary-pages/{language}/{title}/translations` — previews translations
- `GET /wiktionary-pages/{language}/{title}` — returns processed page data

The service uses a Redis-backed active job counter when Redis is available, with a local fallback for degraded diagnostics. Active workers refresh job heartbeats so another translator process does not mistake slow work for an abandoned job. Translation job status is authoritative in Redis, retained for 24 hours, and polled by Atlas using the returned job ID; Atlas retains an active ID across navigation or reload. A successful asynchronous translation records that publication was queued in RabbitMQ; it does not claim that the later Wiktionary write has completed. Atlas can enable the translation publication prefilter under **Settings > Page-check automation**. When enabled, the checker verifies the exact assembled Malagasy candidate without repairing it; only a `good` result reaches RabbitMQ, while every other result is recorded as `filtered_out` and discarded. Settings or checker failures fail closed without publication. The switch defaults to disabled and affects new translation jobs only. Recent background job errors are exposed through `/health` and `/jobs/errors`. By default, up to 100,000 page-check jobs and their results are stored in the configured Redis server so every translator process serves the same history after a browser refresh or service restart. `--max-check-jobs-kept` changes this physical storage ceiling. Atlas shows and calculates statistics from the newest 2,500 jobs by default; its Settings interface can change that window from 1 to 100,000 without restarting the translator or immediately discarding older stored jobs. Page-check statistics are a retained-job sample rather than a complete historical ledger; the quality percentage is `good / total jobs`, so pending, fixed, unverifiable, and failed jobs remain in the denominator. After migrations 010 and 011 are applied, `snapshot_page_check_statistics.py` stores each of the six scores in a canonical UTC half-hour bucket and Atlas plots that history alongside the live cards. History starts when the sampler first runs; it cannot reconstruct earlier Redis states. The sampler checks `mg` by default. Set `page_check_statistics_languages` to comma-separated language codes and, when the translator is not local, set `page_check_statistics_url` under `[global]` in the protected `config.ini`.

The page checker reviews only `ana`, `mat`, `mpam`, `tamb`, and `ana-pr` entries. Other parts of speech are outside its scope and are assumed correct; in particular, it never rejects `e-ana`, `e-mat`, or `romanizasiona` entries. It does not ask either model to write Malagasy. For each section that the verification model marks bad, the dedicated Gemma service selects one source part of speech and rewrites every associated source sense one-for-one into Simple English. The existing NLLB service translates those controlled definitions from English to Malagasy and applies its normal quality checks. Missing Gemma rewrites, failed NLLB translations, copied source text, or a failed independent verification cause the checker to abstain rather than publish a partial fix. Automatic fixing therefore requires both the Gemma and NLLB services, regardless of which model performs verification.

Live Wikimedia operations made through `RedisSite` and `RedisPage` are globally paced across Botjagwar processes through Redis. Configure `[wikimedia] requests_per_minute`, `max_wait_seconds`, bounded Pywikibot retry/socket settings, and a contact-bearing `user_agent_description` in `/etc/botjagwar/config.ini`. Redis cache hits do not consume this budget. When coordination is unavailable or the wait budget is exceeded, the service fails closed; rate-limited HTTP responses include `Retry-After` when a delay is known. Live writes through this boundary are restricted to Malagasy Wiktionary; source Wiktionaries are read-only.

Asynchronous work is bounded to four running jobs and 21 pending jobs by default. Configure these limits with `--max-async-workers` and `--max-pending-jobs`; requests beyond the configured process capacity receive HTTP 503 and should be retried with backoff. `/health` reports process-local running, queued, available-slot, completion, failure, and rejection metrics in addition to the Redis-backed job count.

### Page-check maintenance agents

`.github/workflows/page-check-issue-agent.yml` polls the newest page-check jobs at minute 17 every six hours. It records the `good`, `fixed`, `unverifiable`, and `error` totals in the workflow summary and creates one deduplicated GitHub issue for each configured problematic outcome. Issues contain a hidden job-ID fingerprint, trusted Wiktionary links, bounded checker evidence marked as untrusted, and outcome labels. Closed issues also count for deduplication. By default, `fixed`, `unverifiable`, and `error` jobs create issues, with at most ten new issues per run. The workflow reads the server-managed autonomous-agent switch before deciding whether new issues receive `agent:queued`.

Approved issues are queued for the repository custom agent in `.github/agents/page-check-fixer.agent.md`. `.github/workflows/page-check-fix-agent.yml` assigns up to three oldest queued issues per run to GitHub Copilot cloud agent. Automatic workflow dispatch rechecks the server setting before every assignment, skips work when disabled, and fails closed without assignments when the setting cannot be read. A maintainer can still apply `agent:queued` or run the fix workflow manually while autonomous assignment is disabled. The custom agent must reproduce a general Botjagwar defect, add an offline regression test, make the smallest safe correction, and open a draft pull request in Malagasy. It must not create a title-specific fix or change code for a content-only report. Pull requests are never merged or deployed automatically and remain subject to the normal CI and human review controls.

Configure the automation in the repository settings:

1. Set the Actions variable `PAGE_CHECKER_URL` to the base URL of `entry_translator_v2.py`, without a trailing API path. Both maintenance workflows use the runner selected by `PAGE_CHECK_RUNNER`. Prefer a dedicated ephemeral or JIT self-hosted runner on the trusted Botjagwar network, restricted to a runner group that does not accept untrusted workflows. Do not reuse a persistent general-purpose runner or expose the unauthenticated translator service solely for these workflows. If a GitHub-hosted runner is required, place an authenticated HTTPS reverse proxy in front of the two read-only `GET .../check-jobs` routes and `GET /page-checker/settings`; deny all page-checker settings `PUT` routes.
2. Enable GitHub Copilot cloud agent and repository custom agents.
3. Add the Actions secret `COPILOT_AGENT_TOKEN` as a user fine-grained personal access token for a licensed Copilot user. GitHub's issue-assignment API currently requires read/write access to Actions, Contents, Issues, and Pull requests, plus Metadata read access; the built-in `GITHUB_TOKEN` cannot start this user-scoped agent assignment.
4. Add `PAGE_CHECKER_TOKEN` only when the reverse proxy protecting the page-check endpoint accepts bearer authentication. `entry_translator_v2.py` does not validate this token itself.
5. Keep the repository default branch protected and retain GitHub's approval requirement for workflow runs from Copilot-authored pull requests. Do not expose Actions secrets to agent changes before a trusted maintainer approves the run.

Optional Actions variables are `PAGE_CHECK_ISSUE_OUTCOMES` (default `fixed,unverifiable,error`), `PAGE_CHECK_JOB_LIMIT` (default `100`), `PAGE_CHECK_MAX_ISSUES` (default `10`), `PAGE_CHECK_FIX_BATCH` (default `3`), `PAGE_CHECK_FIX_AGENT` (default `page-check-fixer`), and `PAGE_CHECK_FIX_MODEL` (Copilot automatic model selection when unset). The fix workflow always uses the protected repository default branch as its base. Autonomous assignment defaults to disabled and is controlled from Atlas under Settings > Page-check automation; enabling takes effect on the next issue-agent run. Disabling prevents later automatic assignments but does not cancel work already accepted by GitHub. Remove any obsolete `PAGE_CHECK_AUTO_FIX` repository variable because it is ignored. Deploy translator support before the Atlas and workflow changes; the autonomous flag uses a separate Redis key so the existing IRC settings document remains readable during rollback.

NLLB cache rows are stored without generating embeddings in the API process. If database vectors are needed, install the optional `gensim` and `pgvector` dependencies and run `python scripts/populate_nllb_translation_vectors.py` separately.

### Other scripts

#### `word_forms.py`

Translates non-lemma entries on the English Wiktionary into Malagasy.

#### `list_wikis.py`

Updates statistics tables for each Wiktionary, Wikipedia, and Wikibooks, and stores them to the user's subpage on the Malagasy Wiktionary.

#### `unknown_language_manager.py`

Maintains language templates and categories:

- fetches words created in the last 30 days;
- checks for missing language templates and translates them into Malagasy with a basic phonetic transcription algorithm;
- creates templates and categories for newly translatable languages;
- stores untranslatable language names in a table on the Malagasy Wiktionary at `Mpikambana:<USERNAME>/Lisitry ny kaodim-piteny tsy voafaritra`.

#### `api/speedy_deletion.py`

Standalone module that synchronizes speedy-deletion candidates from the English Wiktionary to the Malagasy Wiktionary. If an English page is in [Category:Candidates for speedy deletion](https://en.wiktionary.org/wiki/Category:Candidates_for_speedy_deletion) and the deletion banner is older than 14 days, matching language sections are removed from the corresponding Malagasy page.

Usage:

```bash
python -m api.speedy_deletion <page_title>
```

#### `scripts/recheck_pages.py`

Re-checks a newline-delimited list of Malagasy Wiktionary pages against their source wiktionaries through the entry-translator v2 page checker, which fixes and queues any wrong language section for publication. By default one asynchronous page-check job is queued per title while `GET /jobs` stays below `--max-active-jobs`; `--sync` runs each check synchronously instead and `--dry-run` only lists the titles that would be rechecked.

Usage:

```bash
python scripts/recheck_pages.py pages_to_recheck.txt
```

## Copyright

Copyright © 2011-2026 Rado A. (Terakasorotany). Licensed under the MIT License.
