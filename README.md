# Entropia V18

A quantitative trading **strategy & backtest platform**: build strategies and
data packages, pin exact revisions, run deterministic backtests on a worker
plane, and let a continuously-running research Agent propose candidates — all on
an auditable, replayable, revision-controlled core.

This repository is built **stage by stage** from a canonical specification (see
[`docs/spec/`](docs/spec/)). The authoritative tech contract is the
[Master Technical Reference](docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md).

| Area | Stack |
| --- | --- |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic |
| Data | PostgreSQL 16 · Redis 7 + Dramatiq · MinIO / S3 · Polars · PyArrow · Parquet |
| Frontend | React 18 · TypeScript · Vite · TanStack Query · React Hook Form |
| Realtime | Server-Sent Events (SSE) |
| Runtime | Docker Compose — modular monolith with separate worker planes |

> **Build status:** the staged build
> ([`docs/STAGE_BUILD_PLAN.md`](docs/STAGE_BUILD_PLAN.md), Stages 0–8) and the
> post-V1 wave have landed — real local authentication (argon2id credentials +
> opaque Bearer sessions + first-Admin bootstrap), a real bar-replay backtest
> engine with built-in indicator compute (SMA/EMA/RMA/WMA/RSI/VWAP, condition
> blocks, multi-timeframe resampling, risk-based & Kelly sizing, position-size
> limits), all **24 screens routed and bound to live server projections**, the
> Future Dev capability system, and audit-log query indexes.
>
> **"Landed" is not one binary state (F-09).** Completion is reported on six
> independent axes, each with its own evidence — never collapsed into a single
> "everything is done" sentence: (1) **route exists**; (2) **UI bound** to live
> server data (no client-computed domain state); (3) **functional completion**
> end-to-end — Future-Dev stubs are NEVER counted here (e.g. Create Package's
> in-transaction candidate stub, the test-only breakout fixture); (4) **visual
> fidelity** vs the v18 prototype (10 pages are still observed-only, not deep
> item-by-item compared); (5) **accessibility** (axe AA with recorded contrast
> deviations A11Y-01/02; NVDA/VoiceOver manual audit not yet done); (6)
> **product-owner acceptance** (signed in
> [`docs/implementation/v18_final_acceptance.md`](docs/implementation/v18_final_acceptance.md) §4 —
> D-1/D-9 accepted, D-2…D-6/D-8 are FIX items still open). All 24 routes are green
> on axes 1–2; several remain **In Progress** on axes 3–6 under the **R2 re-opening**
> (see the status doc's banner) and the **R3 deep-audit backlog** (F-01 worker
> lifecycle, F-04 breakout-proxy fence, F-05 capability matrix, F-07 raw-id
> residuals, F-09 doc honesty). Per-requirement, per-axis status lives in
> [`entropia_v18_remediation_status.md`](docs/implementation/entropia_v18_remediation_status.md).
>
> **Test/schema figures are recomputable, not a frozen claim (F-09).** They are no
> longer typed here by hand: the table below is **generated** from the working tree by
> `scripts/generate_repository_facts.py`, and CI fails when it is stale — so a number
> in this README cannot quietly outlive the code it describes. Pass counts are still
> **not** claimed anywhere: the generator collects test *nodes* statically, and only a
> full CI run reports green. Recompute locally with `make test` (backend **and**
> frontend suites, no swallowed exit codes).
> *(Historical, kept auditable: the R2 close (PR #364, 2026-07-22) cited ≈1841 backend /
> ≈577 frontend tests and alembic `0035_portfolio_rules`; a full re-measurement on
> `origin/main` @ `0dcce69` (2026-08-03), including the gaps this repo still carries,
> lives in [`docs/audit/current_main_ground_truth_2026-08-03.md`](docs/audit/current_main_ground_truth_2026-08-03.md).)*
> This is not "everything is possible" software — the engine and architecture have
> deliberate, fail-closed boundaries and out-of-scope non-goals, listed under
> [Known limitations](#known-limitations) and in
> [`docs/POST_V1_KICKOFF.md`](docs/POST_V1_KICKOFF.md). The running handoff lives
> in [`docs/STAGE2_HANDOFF.md`](docs/STAGE2_HANDOFF.md).

## Repository facts

<!-- BEGIN GENERATED: repository-facts -->
<!-- Written by scripts/generate_repository_facts.py; `--check` gates it in CI. -->

| Fact | Value |
|---|---|
| Alembic head | `0043_i08_registry_strategy_fks` |
| Alembic revisions | 43 (single head) |
| Postgres tables | 104 |
| Foreign keys | 140 |
| HTTP paths | 177 |
| HTTP operations | 196 |
| Frontend router paths | 29 |
| Frontend nav items | 25 |
| Application modules (`domain/` packages) | 32 `commands` · 38 `queries` · 16 `jobs` (26 packages) |
| `ENGINE_VERSION` | `backtest-engine-v18-percent-sizing-per-fill-commission` |
| `SHARED_ALLOCATION_STATUS` | `future_dev` |
| Capability matrix | 62 rows (40 `active_v1`, 22 `future_dev`) |
| Backend tests **collected** (static, not a pass count) | 3628 in 346 files |
| Backend `xfail` markers | 0 (0 strict) |
| Frontend unit test **call sites** (static; `.each` expands at run time) | 718 in 72 files |
| E2E test **call sites** (static) | 84 in 22 specs |
| Acceptance criteria mapped | 383 |
| Acceptance clauses mapped | 1175 |

*Generated from the working tree — no commit sha, no GitHub state, no pass counts.*
*Full detail: [`docs/generated/repository_facts.md`](docs/generated/repository_facts.md).*

<!-- END GENERATED: repository-facts -->

Contributing? See [`CONTRIBUTING.md`](CONTRIBUTING.md) for local setup and the
development workflow. Found a security issue? See [`SECURITY.md`](SECURITY.md)
— please do not open a public issue.

---

## Quick start — Docker (recommended, identical on macOS / Windows / Linux)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(includes Docker Compose v2).

### macOS / Linux

```bash
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
cp .env.example .env
docker compose up -d --build
```

### Windows (PowerShell)

```powershell
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
Copy-Item .env.example .env
docker compose up -d --build
```

Then open:

| URL | What |
| --- | --- |
| http://localhost:8080 | Web app (Mainboard shows live backend status) |
| http://localhost:8000/docs | API — interactive OpenAPI docs |
| http://localhost:8000/api/v1/health/ready | Dependency health (postgres/redis/object storage) |
| http://localhost:9001 | MinIO console (user/pass from `.env`) |

The stack runs migrations automatically (the `migrate` service), creates the
MinIO bucket, and starts the API plus every worker plane
(`worker-default`, `worker-data`, `worker-backtest`, `worker-agent`,
`worker-agent-executor`, `agent-coordinator`, `scheduler`).

Stop it with `docker compose down` (add `-v` to also delete data volumes).

### Authentication profiles (pick one)

`docker compose up` (above) is the **normal session** profile: real Sign Up /
Log In. For **developer / test impersonation** (no login — identity from the
`X-Actor-Id` header, `AUTH_MODE=dev`, local-only) layer the explicit override:

| | Normal session (default) | Dev-auth impersonation |
| --- | --- | --- |
| macOS / Linux | `make up` | `make up-dev-auth` |
| Windows | `.\scripts\tasks.ps1 up` | `.\scripts\tasks.ps1 up-dev-auth` |
| Raw Compose | `docker compose up -d --build` | `docker compose -f docker-compose.yml -f docker-compose.dev-auth.yml up -d --build` |

Both profiles share the same Compose project and named volumes, so switching
between them **preserves your data** — only `make nuke` deletes volumes.

### Verifying a running stack

- `make smoke` (`./scripts/smoke.sh`) — read-only health/deps/identity checks.
- `make accept` (`./scripts/acceptance.sh`; `make accept-dev-auth` /
  `COMPOSE_DEV_AUTH=1 ./scripts/acceptance.sh` for the dev-auth stack) — fails if
  **any** service exited, restarted, or is unhealthy. Every long-running plane
  carries a healthcheck; the one-shots (`migrate`, `minio-setup`) must exit 0.
- `make e2e` (`./scripts/e2e-acceptance.sh`) — real Docker E2E of the three
  authentication acceptance flows (session-clean, legacy-upgrade, dev-auth)
  **plus the five product acceptance flows** (`make e2e-flows`: Strategy →
  Ready-check → Run → Result · Library validation · ESP lifecycle + export ·
  Agent / Trading Signal tools · Trash soft-delete → restore → purge), each in an
  **isolated** Compose project + volumes that never touch your normal stack.
  See [docs/E2E_ACCEPTANCE.md](docs/E2E_ACCEPTANCE.md).

### Authoritative test command

`make test` (Windows: `.\scripts\tasks.ps1 test`) runs the **backend and
frontend** suites and fails if **either** fails — no swallowed exit codes.

---

## What's inside — the 24-screen map

Every screen renders **server projections only** (the client never computes
domain state) and every mutation is a typed, audited command.

| Group | Screen | Purpose |
| --- | --- | --- |
| Workspace | **Mainboard** (`/`) | Composition plane: attach work objects, pin exact revisions, enable/order/label items, freeze snapshots — the fingerprint that feeds Ready Check. |
| Workspace | **Strategy Details** (`/strategy`) | Strategy editor: draft → validate (pure compiler pass) → save immutable revisions; revision history and deep links. |
| Workspace | **Add Outsource Signal** (`/outsource-signal`) | Type chooser routing external work into the Trading Signal / Trade Log workbenches. |
| Workspace | **Trading Signal** (`/trading-signal`) | Upload a signal file → durable import job → report → save as a native work object with OCC-guarded revisions. |
| Workspace | **Trade Log** (`/trade-log`) | The same import chain for historical trade records (twin surface of Trading Signal). |
| Packages & Data | **Create Package** (`/packages/create`) | Package request lifecycle: compose a request, run dependency scans, generate a deterministic **in-transaction candidate stub** (the real generation worker pipeline is Future-Dev — F-01), draft, approve. |
| Packages & Data | **Pre-Check** (`/packages/pre-check`) | Dependency scan viewer: resolved vs missing canonical keys against the resolver registry. |
| Packages & Data | **Package Library** (`/packages/library`) | Read-only catalog of every package: permissions, provenance, scan summary, revision history. |
| Packages & Data | **Embedded System Packages** (`/packages/embedded`) | Resolver registry: propose candidates, Admin activate/deprecate, Pre-Check-parity resolve probe. |
| Packages & Data | **Rationale Families** (`/rationale-families`) | Shared strategy-taxonomy CRUD plus the package-assignment batch editor. |
| Packages & Data | **Market Data** (`/market-data`) | Market dataset registry + owner ingest chain (upload → analyze → schema-map → approve) with revision lifecycle. |
| Packages & Data | **Research Data** (`/research-data`) | Research dataset registry: time policies, field/feature definitions, agent/evidence bundles. |
| Backtest | **Portfolio / Equity Allocation** (`/portfolio`) | Allocation plan draft editor with immutable validation reports, plus portfolio-level rules: a composition-wide **Max Total Exposure** cap and a **cross-item conflict policy** for opposing same-instrument signals. |
| Backtest | **Backtest Ready Check** (`/backtest/ready-check`) | Server preflight over the composition fingerprint; immutable readiness reports. |
| Backtest | **RUN & Backtest Results** (`/backtest/run`) | Run admission (202 + durable tracking) and immutable result deep links with retry. Composite results carry a **per-item breakdown** (each strategy/trade-log's own metrics) and a **contribution** section — correlation, diversification, and each item's marginal delta to the portfolio. |
| Backtest | **Results History** (`/backtest/history`) | Keyset-sorted result index with two-result compare and soft delete. |
| Backtest | **Arrange Metrics** (`/backtest/metrics`) | Metric profile editor (apply / lock / unlock) shaping how results are displayed — never what was computed. |
| Analysis & Ops | **Analysis Lab** (`/analysis-lab`) | Alpha Agent workspace: runtime pause/resume/stop, directives, tasks, checkpoints, tool-call history, hypotheses. |
| Analysis & Ops | **Panel / Management / Logs** (`/panel`) | Admin: users & roles, system actors, role matrix, audit-log explorer, operator recovery. |
| Analysis & Ops | **Admin Provisioning** (`/panel/provisioning`) | First-Admin bootstrap window status and flow documentation. |
| Analysis & Ops | **System Metrics** (`/panel/metrics`) | Golden-signals ops dashboard over the Prometheus `/metrics` exposition. |
| Analysis & Ops | **Trash** (`/trash`) | Admin recycle bin: restore, or permanently purge with confirmation + re-auth proof. |
| Docs | **User Manual** (`/user-manual`) | Versioned in-app manual: sections, uploads, revisions, search. |
| Docs | **Future Dev** (`/future-dev`) | Capability registry: lifecycle transitions with activation gates, operational POSTs, output & transition histories. |

Plus `/login` (sign up / log in when `AUTH_MODE=session`).

---

## Using it — the strategy-universe workflow

Entropia's core is a **strategy universe**: you gather many strategies (and
external Trade Logs) on one Mainboard and analyse how they behave *together* and
*on their own*. The end-to-end path, screen by screen:

1. **Bring data in.** On **Market Data** (`/market-data`), `+ Add Market Dataset`
   → upload a raw OHLCV file → *Analyze & map fields* → *Create version* →
   *Verify / approve*. Only an **approved** revision feeds a backtest.
2. **Make an indicator usable.** On **Create Package** (`/packages/create`) request
   an Indicator Package → run **Pre-Check** → generate a candidate → draft →
   Admin **approve**. It then shows as *usable* in **Package Library** and becomes
   pinnable in the Strategy editor.
3. **Add a strategy.** On the **Mainboard** (`/`), `+ Add → Add Strategy`. A thin
   horizontal box appears at once as an **unsaved draft**; its ▼ expands the full
   3-column Strategy Details editor (Setup & Data · Decision Logic · Risk
   Management). Configure it — market, approved data source, backtest range, entry
   indicator block (*Choose indicator* → your approved package), stops, sizing.
4. **Save.** *Save Strategy Revision* writes an immutable revision and the row
   automatically **joins the composition** (an unsaved draft is never part of
   Ready Check or RUN). Repeat steps 3–4 to stack **many strategies** on the one
   board — the strategy universe. `+ Add → Add Outsource Signal` adds a Trade Log
   the same way.
5. **Set portfolio rules (optional).** On **Portfolio / Equity Allocation**
   (`/portfolio`), turn on *Use Equity Allocation* to share one capital pool by
   per-item **share**, and set the composition-wide **Max Total Exposure** cap and
   the **cross-item conflict policy** (`KEEP_SEPARATE` = each item replays
   independently · `BLOCK_OPPOSITE` = a later item's opposing same-instrument entry
   is blocked while an earlier item holds the other side · `NET` is validated but
   the V1 sequential engine executes it conservatively as `BLOCK_OPPOSITE` and
   discloses the downgrade — never a silent net-fill).
6. **Ready Check → RUN.** **Backtest Ready Check** (`/backtest/ready-check`)
   preflights the composition; a blocker is shown verbatim, never faked green.
   When it passes, **RUN** admits the backtest (202 + durable tracking).
7. **Read the result.** The immutable Result shows portfolio metrics **plus** a
   **Per-item breakdown** (each strategy/trade-log's own PnL, drawdown, trades)
   **and** a **Contribution** section — the correlation matrix, a diversification
   summary, and each item's **marginal** delta (portfolio *with* vs *without* that
   item) — i.e. "what does this item add to the universe?".

> Strategy configs are related through this shared plane, not in isolation: they
> share one capital pool + exposure cap, obey the cross-item conflict policy on the
> same instrument, run as one composition, and are compared by correlation and
> marginal contribution in the Result.

---

## Yerel kurulum — Docker'sız, sıfırdan (Mac & Windows) 🧑‍💻

Bu bölüm Entropia'yı bilgisayarına **hiç Docker kurmadan** çalıştırmayı adım adım
anlatır. Hiç programlama bilmesen de takip edebilesin diye her şeyi tek tek
yazdım — komutları **kopyala → yapıştır** yapabilirsin.

> 🧩 **Entropia neyden oluşuyor?** Üç parça düşün:
> 1. **Beyin (API)** — bir Python programı. Asıl iş burada döner.
> 2. **Hafıza (PostgreSQL)** — bir veritabanı; her şeyi burada saklarız. **Zorunlu.**
> 3. **Yardımcılar (Redis + MinIO + worker'lar)** — backtest gibi ağır işleri arka
>    planda yapan parçalar. **Başlangıçta gerekmez** — bunları Bölüm B'de açacağız.
>
> Yani **en kısa yolda sadece Python + veritabanı** kurup API'yi çalıştıracağız.

### 🅰️ Bölüm A — En kısa yol (sadece API'yi ayağa kaldır)

Bunu bitirince tarayıcında çalışan bir API'n olacak. 🎉

#### Adım 1 — Kodu indir

```bash
# macOS (Terminal)
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
```

```powershell
# Windows (PowerShell)
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
```

> `git` yoksa: macOS'ta `xcode-select --install`, Windows'ta https://git-scm.com/download/win

#### Adım 2 — `uv`'yi kur (Python'u senin yerine kurar)

`uv`, Python'un doğru sürümünü (3.12) ve tüm kütüphaneleri senin yerine indiren
akıllı bir yardımcı. **Python'u elle kurmana gerek yok.**

```bash
# macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
# Kurulumdan sonra terminali KAPAT ve yeniden aç.
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Sonra PowerShell'i KAPAT ve yeniden aç.
```

Kontrol: `uv --version` bir sürüm numarası yazıyorsa 👍

#### Adım 3 — PostgreSQL'i kur, başlat ve veritabanını oluştur

**macOS — en kolayı [Postgres.app](https://postgresapp.com):**
1. İndir, `Applications`'a sürükle, aç ve **Initialize / Start**'a bas (yeşil = çalışıyor).
2. `psql` komutunu kullanabilmek için (tek seferlik):
   ```bash
   sudo mkdir -p /etc/paths.d && echo /Applications/Postgres.app/Contents/Versions/latest/bin | sudo tee /etc/paths.d/postgresapp
   ```
   Terminali yeniden aç. _(Homebrew seversen alternatif: `brew install postgresql@16 && brew services start postgresql@16`.)_

**Windows — resmi kurulum sihirbazı:**
1. https://www.postgresql.org/download/windows/ → **Download the installer** (PostgreSQL 16).
2. Sihirbazı çalıştır. `postgres` kullanıcısı için bir **şifre** ister — bir şifre yaz ve **not al**. Port `5432` kalsın.
3. Bitince Başlat menüsünde **"SQL Shell (psql)"** kısayolu oluşur; onu kullanacağız.

Şimdi Entropia'nın beklediği hesabı ve veritabanını yarat (kullanıcı `entropia`,
şifre `entropia`, veritabanı `entropia`):

```bash
# macOS
psql -d postgres -c "CREATE USER entropia WITH PASSWORD 'entropia';"
psql -d postgres -c "CREATE DATABASE entropia OWNER entropia;"
```

```text
# Windows: "SQL Shell (psql)"'i aç. Server/Database/Port/Username sorularını
# Enter'la geç, postgres şifreni gir, sonra şu iki satırı yapıştır:
CREATE USER entropia WITH PASSWORD 'entropia';
CREATE DATABASE entropia OWNER entropia;
```

Test et (`?column? | 1` görürsen tamam):
```bash
psql "postgresql://entropia:entropia@localhost:5432/entropia" -c "SELECT 1;"
```

#### Adım 4 — Ayar dosyasını (`.env`) oluştur ve düzelt ⚠️ (EN ÖNEMLİ ADIM)

```bash
cp .env.example .env          # macOS
```
```powershell
Copy-Item .env.example .env   # Windows
```

`.env` dosyasını bir metin düzenleyiciyle aç. İçindeki adresler Docker'a göre
yazılmış (`postgres`, `redis`, `minio`). **Docker'sız** çalışacağımız için bunları
`localhost` yapmalıyız. Şu **üç satırı** değiştir:

```diff
- DATABASE_URL=postgresql+asyncpg://entropia:entropia@postgres:5432/entropia
+ DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia

- REDIS_URL=redis://redis:6379/0
+ REDIS_URL=redis://localhost:6379/0

- OBJECT_STORAGE_ENDPOINT=http://minio:9000
+ OBJECT_STORAGE_ENDPOINT=http://localhost:9000
```

> 🚨 Bu adımı atlarsan API `could not translate host name "postgres"` hatası verir.
> **En sık yapılan hata budur.**

#### Adım 5 — Kütüphaneleri kur ve veritabanı tablolarını oluştur

```bash
cd backend
uv sync --all-extras          # Python 3.12 + tüm kütüphaneler (ilk seferde biraz sürer)
uv run alembic upgrade head   # boş veritabanına tabloları yazar
```

Birkaç `Running upgrade ...` satırı görürsen tablolar hazır 👍

#### Adım 6 — API'yi başlat 🚀

```bash
uv run uvicorn entropia.apps.api.main:app --reload --port 8000
```

`Application startup complete` yazınca hazır. Tarayıcıda aç:

| Adres | Ne görürsün |
| --- | --- |
| http://localhost:8000/docs | Tıklanabilir API arayüzü (Swagger) |
| http://localhost:8000/api/v1/health/live | `{"status":"ok"}` — API ayakta! |

> `…/health/ready` şu an `redis` ve `object_storage` için `down` gösterebilir — bu
> **normaldir**. Onları Bölüm B'de açacağız; API'nin temel çalışması için gerekmez.

Durdurmak için terminalde **Ctrl + C**.

#### Adım 7 — Bir "kullanıcı" oluştur (dev-mod giriş)

Bir yönetici ve bir agent hesabı ekleyelim (API'yi durdurup, `backend` klasöründe):

```bash
uv run python -m entropia.apps.seed   # "agent_alpha" (agent) + temel kayıtlar
```

Varsayılan `AUTH_MODE=session` modunda **kendi hesabını sen açarsın**. İlk
yöneticiyi almak için `.env` dosyasına e-postanı yaz:

```bash
ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=sen@example.com
```

Sonra API'yi yeniden başlat ve web arayüzündeki `/login` sayfasından **aynı
e-postayla** kayıt ol — bu ilk kayıt yönetici olarak açılır (sadece ortada aktif
yönetici yokken; sonrası kapanır).

Denemek için (API çalışırken, **yeni** bir terminalde):
```bash
curl http://localhost:8000/api/v1/meta      # macOS
curl.exe http://localhost:8000/api/v1/meta  # Windows
```
İçinde `"auth_mode":"session"` yazan bir JSON dönerse tebrikler — çalışıyor! 🎉
_(Arayüz bu değeri okur ve giriş ekranını ona göre gösterir; **rolü her zaman
sunucu veritabanından çözer**, istemci kendi rolünü asla iddia edemez. Girişsiz
yerel geliştirme profili için `.env`'e `AUTH_MODE=dev` yaz — o modda kim olduğunu
`X-Actor-Id` başlığı söyler ve giriş ekranı kapanır; ayrıntı:
[Authentication — two local profiles](#authentication--two-local-profiles).)_

### 🅱️ Bölüm B — Tam deneyim (isteğe bağlı: backtest + arayüz)

Backtest çalıştırmak, dosya üretmek ve web arayüzünü görmek istersen üç şey daha
lazım: **Redis**, **MinIO** ve **worker**'lar (bir de istersen **frontend**).

**Redis (iş kuyruğu)**
```bash
# macOS
brew install redis && brew services start redis
redis-cli ping   # -> PONG
```
Windows'ta Docker istemediğimiz için **[Memurai](https://www.memurai.com)**'yi kur
(ücretsiz *Developer* sürümü — Redis'in Windows kardeşi; otomatik olarak `6379`
portunda servis gibi çalışır). Test: `memurai-cli ping` → `PONG`.
_(Alternatif: https://github.com/tporadowski/redis/releases → `redis-server.exe`.)_

**MinIO (dosya deposu)**
```bash
# macOS
brew install minio/stable/minio
export MINIO_ROOT_USER=entropia
export MINIO_ROOT_PASSWORD=entropia-secret
minio server ~/entropia-minio --console-address :9001
```
```powershell
# Windows: minio.exe'yi indir -> https://dl.min.io/server/minio/release/windows-amd64/minio.exe
$env:MINIO_ROOT_USER="entropia"
$env:MINIO_ROOT_PASSWORD="entropia-secret"
.\minio.exe server C:\entropia-minio --console-address :9001
```
Sonra tarayıcıda **http://localhost:9001** → `entropia` / `entropia-secret` ile gir
ve **`entropia-artifacts`** adında bir *bucket* (klasör) oluştur.

**Worker'lar (ağır işleri yapan parçalar)** — Redis çalışırken, **her satırı ayrı
terminalde** (`backend` klasöründe):
```bash
uv run python -m entropia.apps.worker --queues default,maintenance
uv run python -m entropia.apps.worker --queues data
uv run python -m entropia.apps.worker --queues backtest
uv run python -m entropia.apps.worker --queues agent,agent-high
uv run python -m entropia.apps.agent_coordinator   # sürekli çalışan araştırma Agent'ı
uv run python -m entropia.apps.scheduler           # bakım / takılan iş kurtarma
```

**Frontend (web arayüzü)** — Node.js 20+ ister (https://nodejs.org):
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```
Sayfanın üstündeki **"act as"** kutusuna `user_admin` yazarsan yönetici ekranlarını
(Panel, Trash) görürsün.

### 🔄 Güncelleme (başka bilgisayarda en son sürümü al)

Projeyi kurduktan sonra, ileride en son sürümü almak için **tek komut** yeter — kodu
çeker, kütüphaneleri günceller ve veritabanı tablolarını en yeni haline getirir:

```bash
make update                 # macOS / Linux   (ya da: ./scripts/update.sh)
```
```powershell
.\scripts\tasks.ps1 update  # Windows          (ya da: .\scripts\update.ps1)
```

Sırasıyla şunları yapar: `git pull` → `uv sync` (backend) → `alembic upgrade head`
(veritabanı) → `npm install` (frontend). **`.env` dosyana dokunmaz.**

**Her gün otomatik güncellensin (kurduğun yere).** Yolu elle yazmana gerek yok —
tek komut, bulunduğu klasör için **günlük** bir görev kurar (varsayılan 09:00):

```bash
./scripts/schedule-update.sh          # macOS / Linux
```
```powershell
.\scripts\schedule-update.ps1         # Windows
```

macOS/Linux'ta bir **cron** işi, Windows'ta bir **Görev Zamanlayıcı** görevi kurulur;
her gün `git pull` + bağımlılıklar + migration çalışır (loglar macOS/Linux'ta `update.log`'a yazılır).
Saati değiştir: `./scripts/schedule-update.sh 21:30` · Kaldır: `--remove` (Windows: `-Remove`).

> 💡 **Cursor kullanıyorsan (uçtan uca):** Cursor'da GitHub linkiyle depoyu **Clone**'la →
> yerleşik terminalde bir kez **Bölüm A** kurulumunu yap → sonra `./scripts/schedule-update.sh`
> (Windows: `.\scripts\schedule-update.ps1`) komutunu **bir kez** çalıştır. Artık kurduğun
> yerde her gün kendini günceller — Cursor açık olmasa bile.

> Otomatik güncelleme yalnızca kodu/bağımlılıkları tazeler; değişiklikleri görmek için
> çalışan API/worker'ları yeniden başlatman gerekir (`--reload` ile çalışan API kendini yeniler).

### 🧪 Her şey doğru mu? (hızlı test)

```bash
cd backend
uv run pytest --no-cov -q
```
Birim/contract testleri altyapı istemez. `integration` testleri Postgres (bazıları
Redis/MinIO) ister; onlar kapalıysa kendiliğinden atlanır.

### 🆘 Takıldın mı? (sık sorunlar)

| Belirti | Sebep & çözüm |
| --- | --- |
| `could not translate host name "postgres"` | `.env`'de `postgres`/`redis`/`minio` → `localhost` yapmayı unuttun (Adım 4). |
| `connection refused ... 5432` | Postgres çalışmıyor. macOS: Postgres.app yeşil mi? Windows: "postgresql" servisi açık mı? |
| `password authentication failed` | `entropia` kullanıcısı/şifresi Adım 3'teki gibi yok ya da `DATABASE_URL` yanlış. |
| `uv: command not found` | Terminali kapatıp yeniden aç; olmazsa `uv`'yi PATH'e ekle. |
| Windows'ta `psql` bulunamıyor | Başlat menüsünden **"SQL Shell (psql)"** kullan ya da `C:\Program Files\PostgreSQL\16\bin`'i PATH'e ekle. |
| `address already in use ... 8000` | Port dolu. `--port 8001` ile başlat. |
| `/health/ready` → `redis`/`object_storage`: `down` | Bölüm B'yi yapmadıysan **normal** — API yine de çalışır. |

---

## Local development — app on host, infra via Docker

> Prefer a **fully Docker-free** setup? See the Turkish step-by-step guide above
> (“Yerel kurulum — Docker'sız, sıfırdan”). The section below runs the app code
> natively but starts Postgres/Redis/MinIO with Docker for convenience.

**Prerequisites**

| Tool | Version | Install |
| --- | --- | --- |
| Python | 3.12 | via [`uv`](https://docs.astral.sh/uv/) (recommended) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (macOS/Linux) · `irm https://astral.sh/uv/install.ps1 \| iex` (Windows) |
| Node.js | 20+ | https://nodejs.org |
| Docker | latest | for Postgres/Redis/MinIO |

### 1. One-time bootstrap

**macOS / Linux**

```bash
make bootstrap          # copies .env, runs `uv sync`, runs `npm install`
```

**Windows (PowerShell)**

```powershell
.\scripts\bootstrap.ps1
```

### 2. Start infrastructure (Postgres + Redis + MinIO)

```bash
docker compose up -d postgres redis minio minio-setup
```

### 3. Run the backend (API) and apply migrations

**macOS / Linux**

```bash
make migrate            # or: cd backend && uv run alembic upgrade head
make backend-dev        # uvicorn with reload on :8000
```

**Windows (PowerShell)**

```powershell
.\scripts\tasks.ps1 migrate
.\scripts\tasks.ps1 backend-dev
```

### 4. Run the frontend

**macOS / Linux**

```bash
make frontend-dev       # Vite dev server on :5173
```

**Windows (PowerShell)**

```powershell
.\scripts\tasks.ps1 frontend-dev
```

The dev frontend talks to `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`).

### Authentication — two local profiles

`AUTH_MODE` selects the authentication line. There are exactly **two** supported
local profiles, and they are not interchangeable — the API trusts one mechanism
and ignores the other. The web app follows whichever the server reports through
`GET /api/v1/meta` (`auth_mode`), so the UI can never offer a credential the
backend will discard.

| | 1. Normal local browser use | 2. Developer / test impersonation |
|---|---|---|
| `AUTH_MODE` | **`session`** (default) | `dev` (explicit opt-in) |
| Credential | opaque Bearer session token | `X-Actor-Id` header |
| UI | Sign Up / Log In / Log out | **act as** field; `/login` is inactive |
| Login page | the real form | a local-development notice |
| Environments | any (**required** for staging/production) | `ENTROPIA_ENV=local` only |

In **both** modes the server resolves the **role** from the database on every
request — the client never asserts its own role. Switching profiles means editing
`AUTH_MODE` in `.env` and restarting the API; the UI follows on reload.

#### 1. Normal local browser use (`AUTH_MODE=session`)

Real login: argon2id password credentials + opaque Bearer session tokens, created
on the web app's `/login` page (sign up / log in).

To provision the **first Admin**, set `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=you@example.com`
before signing up — the matching sign-up is promoted to Admin, and only while no
active Admin exists (fail-closed).

Non-human runtimes (agent, scheduler, coordinator, workers) authenticate with
`ENTROPIA_SERVICE_TOKEN` plus their own non-human `X-Actor-Id`. Session mode needs
a non-empty value; `scripts/bootstrap.sh` and `scripts/update.sh` (and the `.ps1`
twins) generate one into your git-ignored `.env` and never rotate an existing one.
Never reuse a human session token as the service token.

The seed does **not** create the credentialless `user_admin` in this mode — an
ACTIVE Admin with no password can never log in, yet would permanently block the
first-Admin bootstrap:

```bash
cd backend
uv run python -m entropia.apps.seed        # agent "agent_alpha" + baseline registries
```

> **Upgrading a database created before this change?** If your local database
> already has the credentialless `user_admin`, you do **not** need to touch it.
> In session mode the first-Admin bootstrap counts only **login-capable**
> (credentialed) Admins, so a legacy Admin that nobody can log in as never blocks
> provisioning. Just sign up with `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` — the matching
> sign-up becomes your first real Admin **over** the legacy row, which is left
> completely untouched (its principal, ownership, audit history and domain data
> are preserved), and the upgrade is recorded as a `user.admin_bootstrapped`
> audit event with a PII-free legacy-upgrade note. The Admin Provisioning page
> shows the window as open ("a legacy Admin exists but cannot log in") until you
> do. No database edit or row retirement is required.

#### 2. Developer / test impersonation (`AUTH_MODE=dev`)

The transport supplies the principal via `X-Actor-Id`; session tokens are ignored
outright. Set `AUTH_MODE=dev` in `.env`, then seed the fixture identities:

```bash
cd backend
uv run python -m entropia.apps.seed        # creates admin "user_admin" + agent "agent_alpha"
```

The web app's header has an **act as** field (sends `X-Actor-Id`); set it to
`user_admin` to use Admin-only screens (Panel, Trash). Sign Up / Log In are
deliberately not offered here. With Docker, run the seed once:
`docker compose run --rm api python -m entropia.apps.seed`.

`SEED_DEV_ADMIN=1` / `=0` forces the `user_admin` fixture on or off regardless of
the mode.

### 5. (Optional) Run worker planes natively

```bash
cd backend
uv run python -m entropia.apps.worker --queues default,maintenance
uv run python -m entropia.apps.worker --queues data
uv run python -m entropia.apps.worker --queues backtest
uv run python -m entropia.apps.agent_coordinator
uv run python -m entropia.apps.scheduler
```

---

## Common tasks

macOS/Linux use `make <target>`; Windows use `.\scripts\tasks.ps1 <task>`.

| Task | `make` | `tasks.ps1` |
| --- | --- | --- |
| Full stack up | `make up` | `.\scripts\tasks.ps1 up` |
| Stack down | `make down` | `.\scripts\tasks.ps1 down` |
| Tail logs | `make logs` | `.\scripts\tasks.ps1 logs` |
| DB migrate | `make migrate` | `.\scripts\tasks.ps1 migrate` |
| Smoke-test a running stack | `make smoke` | `bash scripts/smoke.sh` (Git Bash) |
| Back up Postgres + artifacts | `make backup` | `bash scripts/backup.sh` (Git Bash) |
| Verify a backup restores | `make backup-verify` | `bash scripts/backup-verify.sh` (Git Bash) |
| Backend tests | `make backend-test` | `.\scripts\tasks.ps1 backend-test` |
| Backend lint | `make backend-lint` | `.\scripts\tasks.ps1 backend-lint` |
| Frontend build | `make frontend-build` | `.\scripts\tasks.ps1 frontend-build` |
| Frontend lint | `make frontend-lint` | `.\scripts\tasks.ps1 frontend-lint` |
| Run `make help` for the full list. | | |

---

## Verifying changes

Everything below is what CI runs (`.github/workflows/ci.yml`: **Backend — lint,
type, test** with a PostgreSQL 16 service · **Frontend — lint, typecheck,
build, test** · **Docker — build images**) — run it locally before pushing.

Several of those steps are **gates that fail the build**, not reports: the
backend suite enforces `--cov-fail-under=90` (the measured percentage is
reported by a CI run, not pinned here — `docs/audit/coverage_baseline.md`
records the historical calibration baseline), `npm run coverage`
enforces the thresholds in `frontend/vite.config.ts`, and dependency advisories
are checked by `pip-audit` (backend) and `scripts/npm-audit-gate.mjs` (npm). The
npm gate fails on any high/critical advisory that is not a **recorded exception**
— `.github/dependabot.yml` deliberately suppresses frontend majors, so an
advisory only a major upgrade would clear cannot simply be merged away.

There is exactly **one** place such an exception may be recorded:
`.github/security-allowlist.json`. Every entry requires an `owner` (a named human,
not a team alias) and an `expires` date, and **the build fails once that date
passes** — whether or not the finding still appears, because an exception nobody
re-examines is not an exception. Both gates read it through
`scripts/lib/security-allowlist.mjs` and both expire the whole list, so an
exception's calendar never depends on which workflow ran. The list is currently
empty: nothing is waived. The E2E workflow adds an **A11Y** job that runs the
axe-core scan against the seeded stack.

**Backend** (from `backend/`):

```bash
uv run ruff check . && uv run ruff format --check .   # lint + formatting
uv run mypy src                                       # strict typing
uv run alembic upgrade head                           # migrations apply cleanly
uv run pytest --no-cov -q                             # unit + contract + integration
```

Integration tests **rebuild the schema on every test** — never point them at a
database you care about. Give each concurrent session its own database:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_test \
  uv run pytest --no-cov -q
```

Without a reachable PostgreSQL, integration tests skip themselves (unit and
contract tests always run). Migration changes additionally require an
up/down/up proof and migration↔model column parity — both are now automated:

```bash
make migration-accept   # single head · empty->head · LEGACY->head · down/up/up · column parity · provisioning idempotency
```

It works inside a scratch database (never your live one), needs no Docker, takes
about half a minute, and gates every PR via
[`.github/workflows/install-acceptance.yml`](.github/workflows/install-acceptance.yml).
See [`docs/INSTALL_ACCEPTANCE.md`](docs/INSTALL_ACCEPTANCE.md).

**Frontend** (from `frontend/`):

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

**Running stack** (outside-in): `make smoke` — health endpoints, per-dependency
readiness, metrics exposition, identity resolution, frontend reachability. The
full end-to-end product path (ingest → package → strategy → mainboard → ready
check → RUN → result → history → trash/restore) is executable as one test:

```bash
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_smoke \
  uv run pytest tests/integration/test_e2e_pipeline.py --no-cov -q
```

---

## Backup & recovery

Two authoritative stores are backed up — **PostgreSQL** (metadata) and **MinIO**
(artifacts); Redis is derivable and intentionally excluded. Backups are
operator-initiated and local:

```bash
make backup          # snapshot -> ./backups/<UTC-stamp>/  (Postgres required, MinIO optional)
make backup-verify   # quick: prove the latest backup LOADS into a throwaway DB
make dr-accept       # full: restore to scratch and prove rows, hashes and object bytes survived
make restore         # recover from the latest backup (DESTRUCTIVE, guarded)
```

`make dr-accept` also runs nightly in CI (`install-acceptance.yml`, job
**disaster-recovery**) and uploads its transcript as the `dr-evidence` artifact.

The full runbook — retention, disaster scenarios, RPO/RTO, and what V1 defers to
the infra module (PITR, off-site replication) — is in
[`docs/BACKUP_DR.md`](docs/BACKUP_DR.md).

---

## Configuration

All configuration is environment-driven. Copy `.env.example` to `.env` and edit.
Secrets are never logged, never written to audit payloads, and never baked into
the frontend build. Each environment (`local`/`staging`/`production`) uses its
own database, bucket, and queue namespace. See
[`.env.example`](.env.example) for every variable and its default.

---

## Repository layout

```
Entropia/
├── backend/              FastAPI app + worker planes (Python, uv)
│   ├── src/entropia/      apps · application · domain · infrastructure · config · shared
│   ├── alembic/           async database migrations
│   └── tests/             unit · integration · contract · deterministic · acceptance
├── frontend/             React + TypeScript + Vite app shell
├── scripts/              cross-platform bootstrap / task runners (sh + ps1)
├── docs/
│   ├── ARCHITECTURE.md        system architecture (synthesized from the spec)
│   ├── DOMAIN_MODEL.md        canonical roots/revisions, roles, invariants
│   ├── STAGE_BUILD_PLAN.md    the Stage 0..8 roadmap
│   └── spec/                  source specification (canonical authority)
├── docker-compose.yml    full local/first-production stack
├── Makefile              macOS/Linux developer tasks
└── .github/workflows/    CI (lint, test, build)
```

---

## Architecture in one paragraph

The backend is a **modular monolith** (one codebase, domain-oriented modules)
with **separate worker processes** for long-running work. Backtest and data-ingest
work runs on dedicated worker planes: the API creates a durable **job** and returns
immediately; workers publish authoritative state in a transaction and emit an
**SSE** refresh signal. Honest boundary (F-09/F-01): Create Package's
pre-check / candidate / publish jobs are V1 **synchronous in-transaction stubs**
(the generation worker pipeline is Future-Dev) — durable job rows exist but do not
yet dispatch to a worker plane.
**PostgreSQL** is the source of truth for metadata, roots, revisions, audit, and
jobs; large/columnar artifacts live in **object storage** as immutable, content-
addressed Parquet. The **Agent** is a non-login system actor whose research loop
runs continuously in the backend, independent of any browser or UI session. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full model.

---

## Known limitations

These are deliberate, fail-closed engine and architecture boundaries — not open
bugs. Each is surfaced honestly (via engine diagnostics or a Ready Check
blocker), never silently faked. Full per-requirement detail is in
[`docs/implementation/entropia_v18_remediation_status.md`](docs/implementation/entropia_v18_remediation_status.md).

- **Composite portfolio equity curve (F-04)** concatenates each strategy's
  realized-PnL progression in deterministic pin order; a unified-clock,
  simultaneous cross-margin co-simulation across heterogeneous bar sources is
  deferred (surfaced as the L4 `portfolio_curve_sequential_not_unified_clock`
  diagnostic, never hidden). For the same reason the **`NET` cross-item conflict
  policy** cannot be honestly co-simulated on the V1 sequential engine, so it is
  executed as **`BLOCK_OPPOSITE`** with an explicit validation + engine warning
  (`CONFLICT_POLICY_NET_V1`), never a silent net-fill. The **per-item breakdown**
  and **contribution** analytics (correlation, diversification, marginal deltas)
  build on this same per-item replay.
- **Multi-instrument filtering (F-05)** is implemented but not exercised
  end-to-end: the current ingestion schema is single-instrument-per-revision
  (`MarketDatasetRevision.instrument_id` is dataset-level and the canonical
  OHLCV Parquet schema carries no per-row instrument column), so there is
  nothing to filter per row today. The dataset-level instrument mismatch check
  is enforced.
- **Research-feature → strategy-condition binding (F-11)** covers the documented
  funding-cost rule plus the reusable anti-lookahead as-of join; a general
  "arbitrary Research feature → condition" binding stays gated on the
  feature-definition compiler (raw binding prohibited, doc 12 §9.2).
- **Breakout proxy (spec F-06 / R3 deep-audit F-04)** survives in
  `domain/backtest/engine.py` ONLY as an explicit test-only fixture
  (`run_engine(..., builtin_breakout_fixture=True)`). Every production path fails
  closed on an unresolved/empty indicator plan — Ready Check blocks admission, the
  worker returns `RUN_FAILED_UNRESOLVED_DEPENDENCY`, and `run_engine` itself now
  raises `UnresolvedStrategyError` (defence-in-depth) rather than fabricate a
  Result from a strategy the user never defined. R3 tracks deleting the fixture
  from the shipped module. (Spec requirement **F-06** "remove unresolved-indicator
  breakout fallback" and deep-audit finding **F-04** "breakout-proxy fail-closed"
  refer to the same code — cross-referenced here so the two governance docs agree.)
- **Intrabar / limit / stop-limit fills (F-07)** require tick data. F-07(i)
  wires the tick-data requirement into Ready Check; without tick data these
  settings fail closed (a Ready Check blocker), never a silently imitated fill
  over plain OHLCV. A partial *fill* is likewise unmodellable over OHLCV (no
  volume-at-price) and stays a blocker rather than a silent full fill.
- **F-23 end-to-end gate** runs in a dedicated CI workflow
  (`.github/workflows/e2e.yml`) that stands up the Docker Compose stack and runs
  Playwright against it; it is CI-executable but requires Docker, so it cannot
  be exercised on a Docker-less machine.
- **Deliberate non-goals (out of scope for V1):** live trading, LLM-based code
  generation (Future-Dev), retention auto-purge (doc 20 §16 — purge is always
  explicit Admin confirm + re-auth), and the Graphic View renderer (a static
  placeholder). See [`docs/POST_V1_KICKOFF.md`](docs/POST_V1_KICKOFF.md).

---

## License

Proprietary — see [LICENSE](LICENSE).
