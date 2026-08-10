<!-- doc-status: current -->
# P5 — Docker stack, üç auth modu, servis sağlığı (ADIM 29 / V18 RC verification)

**Tarih:** 2026-08-07 · **Dal:** `claude/entropia-v18-docker-auth-validation-52e446`
**HEAD:** `bc59dae` — *docs(v18-rc): adjudicate the A-08 human gate as BLOCKED (#634)*
**Çalışma ağacı:** temiz (`git status --porcelain` → boş çıktı)
**Kod değişmedi.** Bu slice yalnızca kanıt üretir.

---

## 0. Karar: **PARTIAL — 1/4 PASS, 3/4 BLOCKED**

| # | Adım | Sonuç |
|---|---|---|
| 1 | `docker build` backend + frontend (ci.yml `docker` job pariteli) | **PASS** — ikisi de exit 0 |
| 2 | Stack ayağa kalksın; session / dev-auth / legacy üç auth modu | **BLOCKED** — Docker daemon kilitlendi |
| 3 | Her servisin health endpoint'i tek tek | **BLOCKED** — aynı sebep |
| 4 | `scripts/smoke.sh` + `scripts/worker-restart-smoke.sh` | **BLOCKED** — aynı sebep |

> **Sahte yeşil YOK.** 2–4 için hiçbir servis "healthy" yazılmadı; hiçbiri ayağa
> kalkmadı. Blokaj **ürün kusuru değil, host kaynak tükenmesidir** — kanıtı §3'te.

---

## 1. İmaj build'leri — **PASS**

`.github/workflows/ci.yml:186-194` `docker` job'ının **birebir aynı** iki komutu:

| Komut | Süre | Exit | İmaj | Boyut | Log |
|---|---|---|---|---|---|
| `docker build -t entropia-backend:ci ./backend` | 203.4 s | **0** | `entropia-backend:ci` | 2.09 GB | `p5_logs/01_build_backend.log` |
| `docker build -t entropia-web:ci ./frontend` | 588.9 s (`npm ci` 579.1 s + export 9.3 s) | **0** | `entropia-web:ci` | 84 MB | `p5_logs/02_build_frontend.log` |

İkisi de `naming to docker.io/library/…:ci … done` satırıyla bitti ve
`EXIT_CODE=0` yazdı. **CI'ın `docker` job'ı bu ağaçta yeşildir.**

> Not: frontend build'inin **ilk** denemesi araç zaman aşımına (10 dk) takıldığı
> için arka planda yeniden koşuldu; log dosyası bunu ilk satırında kaydeder.
> Yeniden koşu sıfırdan (`npm ci` dahil) tamamlandı — cache'lenmiş sahte yeşil değil.

---

## 2. Ortam hazırlığı (blokajdan önce yapılanlar)

| İş | Sonuç |
|---|---|
| `scripts/bootstrap.sh` | `.env` `.env.example`'dan üretildi; `ENTROPIA_SERVICE_TOKEN` yerel olarak üretildi (değer **basılmadı**), backend venv + frontend deps kuruldu |
| `.env` `AUTH_MODE` | `session` (base profil varsayılanı) |
| Host portu çakışması | **5432 / 6379 / 9000 / 9001 macOS native servislerince tutulu** (`postgres` pid 929, `redis-server` pid 918, `minio` pid 927) → compose host bindingleri `.env` üzerinden 15482 / 16429 / 19300 / 19301'e alındı. **Container tarafı ve container-içi URL'ler değişmedi.** 8000 (api) ve 8080 (web) boştu. |

---

## 3. BLOCKED'ın kanıtı — Docker host kaynak tükenmesi

### 3.1 Ne oldu

`docker compose up -d --build` başlatıldı (`p5_logs/03_compose_up_session.log`).
Backend katmanları kısmen cache'ten geldi, ancak compose **aynı 2.09 GB backend
imajı için 10 hedefi EŞZAMANLI export etmeye** başladı:

```
#30 [api] exporting to image          #35 [worker-agent] exporting to image
#31 [worker-data] …                   #36 [scheduler] …
#32 [worker-agent-executor] …         #37 [worker-backtest] …
#33 [worker-default] …                #38 [provision] …
#34 [agent-coordinator] …             #39 [migrate] …
```

Bu noktadan sonra buildkit **16+ dakika hiçbir çıktı üretmedi** ve host çöktü.

### 3.2 Ölçülen host durumu

| Ölçüm | Değer |
|---|---|
| Docker VM belleği | **3.89 GiB** / 8 CPU |
| Aynı daemon'da koşan **başka** stack'ler | `entropia-a11y-audit` (15 container, ADIM 28'den beri 2+ saattir ayakta) + `entsec` (9+ container) = **22 container** |
| Paralel oturum build'i | `entropia-backend:scan`, `entropia-web:scan` etiketleri bu oturuma ait DEĞİL — başka bir oturum aynı anda build ediyor |
| Host load average | `14.98 / 23.95 / 27.22` (tepe) |
| `docker stats --no-stream` | **120 s'de dönmedi** |
| Boş disk | 28 GiB → **20 GiB** (buildkit hâlâ yazıyor) |

### 3.3 Kilitlenme kanıtı (API yüzeyi bazında)

Compose CLI durdurulduktan **sonra** ölçüldü — buildkit işi CLI ile birlikte iptal olmuyor:

| Komut | Exit |
|---|---|
| `docker version` | **0** (daemon canlı) |
| `docker buildx ls` | **0** |
| `docker ps -q` | **124** (60 s timeout) |
| `docker images -q` | **124** |
| `docker tag entropia-backend:ci entropia-backend:local` | **124** (240 s timeout) |
| `docker tag entropia-web:ci entropia-web:local` | **124** (240 s timeout) |

→ Daemon'ın **container ve imaj deposu yüzeyi kilitli**. Bu durumda ne stack
kaldırılabilir, ne servis health'i sorulabilir, ne de smoke script'leri koşabilir.
13 dakikalık kurtarma yoklaması boyunca `docker ps` **hiç** yanıt vermedi.

**Bu belge commit edilirken son ölçüm:** `timeout 20 docker ps -q` → **exit 124**.
Kilit hâlâ duruyor; §5'teki BLOCKED kararı commit anında da geçerlidir.

### 3.4 Denenen kurtarma (başarısız)

`docker compose up --build` iptal edildi ve **zaten build edilmiş CI imajlarını
yeniden etiketleyip `--build`'siz `up` etme** planı hazırlandı. Bu plan geçerlidir
— `frontend/Dockerfile:6` `ARG VITE_API_BASE_URL=http://localhost:8000/api/v1`
varsayılanı compose'un geçirdiği değerle **birebir aynıdır**, yani `:ci` imajları
compose'un üreteceğiyle özdeştir. Ancak `docker tag` bile kilitli imaj deposu
yüzünden dönmedi (§3.3), dolayısıyla plan **uygulanamadı**.

---

## 4. Yapılmayanlar — açık ve dürüst sınır

Aşağıdakilerin **hiçbiri** koşturulmadı. Hiçbiri için kısmi/varsayılan sonuç yazılmadı:

- **Üç auth modu.** `scripts/e2e-acceptance.sh all` (§9.4 session-clean, §9.5
  legacy-upgrade, §9.6 dev-auth X-Actor-Id) **koşmadı**. Bu üç akış izole compose
  projeleri (`entropia-e2e-*`, portlar 180xx/154xx/163xx/190xx) kullanır ve doğru
  araçtır; blokaj kalkınca ilk iş budur.
- **Servis bazında health.** `postgres` (pg_isready), `redis` (redis-cli ping),
  `minio` (mc ready), `minio-setup`/`migrate`/`provision` (one-shot exit 0),
  `api` (`/api/v1/health/live` + `/health/ready`), yedi worker/scheduler/coordinator
  plane'i (broker ping healthcheck), `web` (`wget 127.0.0.1:8080`) — **hiçbiri
  ölçülmedi**.
- **`scripts/smoke.sh`** — koşmadı.
- **`scripts/worker-restart-smoke.sh`** — koşmadı.
- **`scripts/acceptance.sh`** (DEP-05 state gate) — koşmadı.

---

## 5. Blokajı kaldırmak — **insan kararı gerektirir**

Kalan tüm çareler bu oturuma ait **olmayan** canlı işi etkiler, bu yüzden agent
tek başına uygulamadı:

| Seçenek | Etkisi |
|---|---|
| **A.** Docker Desktop / engine yeniden başlat | Kilit kalkar; `entropia-a11y-audit` ve `entsec` stack'lerinin container'ları da yeniden başlar (`restart: unless-stopped` geri getirir, ama koşan işleri kesilir) |
| **B.** Diğer iki stack'i `down` et, sonra P5'i koş | Daemon kilitli olduğu için **şu an mümkün değil** — `docker compose down` da `docker ps` gibi bloklanır. Ancak A'dan sonra geçerli bir hazırlık adımıdır |
| **C.** Buildkit'in kendiliğinden bitmesini bekle | Disk 15 dk'da ~1 GiB düşüyor ve 20 GiB kaldı; süresi belirsiz, disk riski var |

**Öneri: A → B → P5'i baştan koş.** B adımı, 3.89 GiB'lik VM'de tek stack bırakır;
P5'in ihtiyacı olan ~13 container ancak o zaman rahatça ayağa kalkar.

---

## 6. Üretilen dosyalar

| Dosya | İçerik |
|---|---|
| `p5_logs/01_build_backend.txt` | backend build tam çıktısı + `EXIT_CODE=0` |
| `p5_logs/02_build_frontend.txt` | frontend build tam çıktısı + `EXIT_CODE=0` |
| `p5_logs/03_compose_up_session.txt` | compose up çıktısı + `EXIT_CODE=ABORTED` ve iptal gerekçesi |

> Uzantı `.txt`: `.gitignore:49`'daki `*.log` deseni kanıtı repodan dışarıda
> bırakırdı; aynı dizindeki `gate1_repository_facts.txt` vb. de bu yüzden `.txt`.
