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

> **Build status:** **Stage 0 (skeleton)** and **Stage 1 (common system
> foundation)** are complete — identity/roles, server-side policy, audit +
> transactional outbox, generic root/revision model, optimistic concurrency,
> soft-delete/trash/restore/purge, idempotency, durable jobs, and the central
> lifecycle enum registry. The staged roadmap lives in
> [`docs/STAGE_BUILD_PLAN.md`](docs/STAGE_BUILD_PLAN.md).

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
`agent-coordinator`, `scheduler`).

Stop it with `docker compose down` (add `-v` to also delete data volumes).

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
uv run python -m entropia.apps.seed   # "user_admin" (yönetici) + "agent_alpha" (agent)
```

Denemek için (API tekrar çalışırken, **yeni** bir terminalde):
```bash
curl     -H "X-Actor-Id: user_admin" http://localhost:8000/api/v1/me   # macOS
curl.exe -H "X-Actor-Id: user_admin" http://localhost:8000/api/v1/me   # Windows
```
Kim olduğunu söyleyen bir JSON dönerse tebrikler — çalışıyor! 🎉 _(Giriş/şifre
sistemi bilinçli olarak sonraya bırakıldı; şimdilik kim olduğunu `X-Actor-Id`
başlığı söyler, **rolü her zaman sunucu veritabanından çözer**.)_

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

**Kendiliğinden (otomatik) güncellensin mi?** Aynı komutu zamanlanmış bir göreve bağla:

- **macOS / Linux (cron):** `crontab -e` → şu satır her gün 09:00'da çalıştırır:
  ```cron
  0 9 * * * cd /ENTROPIA/YOLU && ./scripts/update.sh >> update.log 2>&1
  ```
- **Windows (Görev Zamanlayıcı):** yeni görev oluştur, "Program/script" alanına:
  ```text
  powershell.exe -ExecutionPolicy Bypass -File C:\ENTROPIA\YOLU\scripts\update.ps1
  ```
  ve bir tetikleyici seç (ör. "Günlük 09:00").

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

### Acting as a user (dev-mode auth)

Authentication / IdP selection is a deliberately deferred security decision. Until
then, seed the baseline identities and choose which principal to act as:

```bash
# inside the backend (DB must be migrated):
uv run python -m entropia.apps.seed        # creates admin "user_admin" + agent "agent_alpha"
```

The web app's header has an **act as** field (sends `X-Actor-Id`); set it to
`user_admin` to use Admin-only screens (Panel, Trash). With Docker, run the seed
once: `docker compose run --rm api python -m entropia.apps.seed`. The server always
resolves the **role** from the database — the client never asserts its own role.

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
| Backend tests | `make backend-test` | `.\scripts\tasks.ps1 backend-test` |
| Backend lint | `make backend-lint` | `.\scripts\tasks.ps1 backend-lint` |
| Frontend build | `make frontend-build` | `.\scripts\tasks.ps1 frontend-build` |
| Frontend lint | `make frontend-lint` | `.\scripts\tasks.ps1 frontend-lint` |
| Run `make help` for the full list. | | |

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
with **separate worker processes** for long-running work. The API never runs
heavy work inline — it creates a durable **job** and returns immediately; workers
publish authoritative state in a transaction and emit an **SSE** refresh signal.
**PostgreSQL** is the source of truth for metadata, roots, revisions, audit, and
jobs; large/columnar artifacts live in **object storage** as immutable, content-
addressed Parquet. The **Agent** is a non-login system actor whose research loop
runs continuously in the backend, independent of any browser or UI session. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full model.

---

## License

Proprietary — see [LICENSE](LICENSE).
