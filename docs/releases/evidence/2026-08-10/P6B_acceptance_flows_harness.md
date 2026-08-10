<!-- doc-status: current -->
> **EVIDENCE RECORD — 2026-08-10 (ADIM 30).** Bu belge o gün, bu ağaç üzerinde koşulan
> kabul-akışı kanıtının kaydıdır. Sayılar koşuldukları anın değerleridir ve **hiçbiri
> 2026-08-07 kaydından kopyalanmamıştır**. Güncel sayısal otorite
> `docs/generated/repository_facts.md`.

# ADIM 30 / P6-B — RC Blocker 2: kabul akışı harness kapsamı

**Ölçüm ağacı:** `origin/main` @ `aabb85d` + bu dal (`fix/rc-blocker2-acceptance-harness`).
**Aday SHA ile ilişki:** rapordaki aday `1f4b88b`; `1f4b88b..aabb85d` arasında **docs dışı
yalnız üç dosya** değişti (`CLAUDE.md`, `frontend/package-lock.json`,
`scripts/npm-audit-gate.mjs` — P9-B1 js-yaml düzeltmesi). `backend/src`, `frontend/src` ve
`frontend/e2e` **birebir aynıdır** (`git diff --stat 1f4b88b..aabb85d -- backend/src
frontend/src frontend/e2e` → boş), yani buradaki kabul-akışı kanıtı aday için geçerlidir.

**Verdict: Blocker 2 KISMEN KAPANDI.** Kapsam boşluğu kapandı ve beş akış da koştu; blocker'ı
açık tutan tek kalem aşağıda §6'da adlandırılmıştır (harness bir **CI kapısı değil**).

---

## 1. Raporun iki iddiası yeniden ölçüldü

Rapor §6.2 iki sebebi üst üste koyuyordu. Her ikisi de bugün yeniden ölçüldü.

### 1.1 "Docker/OrbStack takılı (`docker ps` sürekli **124**)" — **YENİDEN ÜRETİLEMEDİ**

| Ölçüm | Rapor (2026-08-07) | Bu koşu (2026-08-10) |
|---|---|---|
| `docker version` | 0 | **0** — client 29.4.0 / server 29.4.0 (orbstack) |
| `docker compose version` | — | **0** — v5.1.2 |
| `timeout 20 docker ps -q` | **124** | **0**, anında döndü |
| `timeout 20 docker images -q` | **124** | **0**, anında döndü |
| Docker VM | 3.89 GiB / 8 CPU | **3.89 GiB / 8 CPU** (değişmedi) |
| Host load (1/5/15) | tepe 14.98 / 23.95 / 27.22 | 7.99 / 8.42 / 10.62 → koşu sırasında tepe 18.08 |

Ham: `p6b_docker_remeasure.txt`.

**Dürüst ayrım:** raporun *kaynak baskısı* teşhisi doğrudur — host 8 GB RAM, VM 3.89 GiB, ölçüm
anında 18–21 konteyner zaten koşuyordu. Yanlış olan **sonuçtur**: daemon takılı değildi ve
izole yığın bu baskının altında **sorunsuz ayağa kalktı**. Yani P5/2-3-4 ve P8-1b'yi bloke
eden "aynı kök neden" bugün mevcut değildir; aşağıda hepsi koşuldu.

### 1.2 "Beş akışın hiçbiri hiçbir katmanda doğrulanmadı" — **(a) ve (b) için YANLIŞ**

Raporun terim taraması **iki shell dosyasıyla sınırlıydı** ve o kapsamda **doğrudur**:
`scripts/acceptance.sh` bir konteyner sağlık kapısıdır, `scripts/e2e-acceptance.sh` bir
auth/kimlik bootstrap harness'ıdır. Fakat oradan çıkarılan "hiçbir katmanda" genellemesi
**tarayıcı katmanını atlamıştır**: `frontend/e2e/specs/*` (a) ve (b) akışlarını **tam olarak**
uygular ve **aday SHA'da CI'da yeşildir**.

GitHub Actions **E2E**, branch `main`, run **31364211010**, conclusion **success**, 5m34s,
2026-08-10T07:01:38Z (head = `aabb85d`):

| Spec | Akış karşılığı | Sonuç |
|---|---|---|
| `05-mainboard-ready-check-run.spec.ts` | **(a)** Strategy → Ready **Ready** → RUN **SUCCEEDED** → inline Result | ✓ 8.2s |
| `20-library-request-validation.spec.ts` | **(b)** Library'den Request Validation → durable worker → PASSED | ✓ 7.2s |
| `06-trash-reauth.spec.ts` | **(e)** soft-delete → re-auth → purge **(restore YOK)** | ✓ 2.3s |
| `04-create-package-lifecycle.spec.ts` | (b) destekleyici | ✓ 10.7s |
| `18-result-artifacts-drilldown.spec.ts` ×2 | (a) Result artifact drill-down | ✓ |
| **suite** | | **39 passed (2.3m)** |

Ham: `p6b_ci_browser_layer.txt`.

**Gerçekten hiçbir katmanın kapsamadığı kalemler** şunlardı — ve blocker'ın asıl içeriği budur:
**(c)** ESP lifecycle + export · **(d)** Agent / Trading Signal tool yüzeyleri ·
**(e)**'nin **restore** ayağı · ve dört tavizsiz kuralın tamamı (aşağıda §4).

---

## 2. Bu dalgada yazılan kapsam

Yeni harness **icat edilmedi**. Mevcut `scripts/e2e-acceptance.sh`'e beşinci bir alt-komut
eklendi ve gövdesi `scripts/lib/acceptance-flows.sh`'e kondu; izolasyon sözleşmesi, hermetik
env dosyası, `dc`, `req` ve PASS/FAIL sayacı **aynen** yeniden kullanıldı.

```
scripts/e2e-acceptance.sh flows     # (a)-(e), izole proje entropia-e2e-flows
scripts/e2e-acceptance.sh all       # session + legacy + dev-auth + flows
```

İki katman, biri diğerinin yerine geçmez:

* **Tarayıcı katmanı** — hâlihazırda var olan yolculuklar **yeniden yazılmadı, koşuldu**
  (05 + 18 = (a), 20-library = (b), 06 = (e)'nin delete→purge ayağı), `E2E_BASE_URL` ve
  `E2E_API_BASE_URL` bu izole yığına yönlendirilerek.
* **Sunucu katmanı** — hiçbir katmanın kapsamadığı her şey: ESP yaşam döngüsü, paket export
  zarfı, Trading Signal / Agent yüzeyleri, (e)'nin **restore** ayağı, ve bir tarayıcının
  kanıtlayamayacağı dört değişmez (bir tarayıcı yalnız UI'nin göstermeyi seçtiğini görür).

Terim taraması, aynı yöntemle: `p6b_term_scan.txt`.

---

## 3. Koşu sonucu (2026-08-10)

```
$ E2E_KEEP_UP=1 ./scripts/e2e-acceptance.sh flows
========== RESULT ==========
  60 passed, 0 failed, 2 skipped
E2E ACCEPTANCE OK — every asserted step passed.        exit 0
```

| Akış | Sunucu katmanı | Tarayıcı katmanı | Sonuç |
|---|---|---|---|
| **(a)** Strategy → Ready-check → Run → Result | readiness projeksiyonu · stale fingerprint → **409** · boş kompozisyonda fingerprint YOK · run reddi Result üretmiyor · USER → **403** | specs 05 ✓ (9.0s) + 18 ✓✓ | **PASS** |
| **(b)** Library validation | katalog + detay · uyuşmayan head → **422** · USER approve/delete → **403** | spec 20-library ✓ (9.3s) | **PASS** |
| **(c)** ESP lifecycle + export | create **201** · validate **200** · USER activate → **403** · stale `X-Registry-Version` → **409** · doğrulaması FAILED resolver **promote edilemiyor** · registry'de `trusted_active` var · export zarfı `export_schema_version` + `manifest_hash` + `registry_observation` | — | **PASS** (1 SKIP, §5) |
| **(d)** Agent / Trading Signal tools | TS ≠ Package (katalogda yok, paket kökü TS yüzeyinde **404**) · `.exe` **422 FILE_TYPE_NOT_ALLOWED** · boş filename **422** (fail-closed) · agent overview/tasks **200** · directive **202** · USER pause → **403** | — | **PASS** (1 SKIP, §5) |
| **(e)** Trash: soft-delete → restore → purge | çelişkili dual token → **409 OCC_TOKEN_CONFLICT** · soft-delete **204** → Trash girdisi · restore-preflight **200** · **restore 200 → RESTORED** · sahte reauth reddedildi · gerçek proof ile purge **202** · **O-30: `deletion_state` = `root_lifecycle_state` = `purge_pending`** · altı USER yüzeyi **403** | spec 06 ✓ (2.2s) | **PASS** |

Tarayıcı katmanı toplam: **5 passed (23.8s)**, sıfır failed.
Ham: `p6b_flows_run.txt` (155 satır, tarayıcı raporu dahil).

---

## 4. Dört tavizsiz kural — varsayılmadı, iddia edildi

| # | Kural | Nerede kanıtlandı |
|---|---|---|
| 1 | Trading Signal / Trade Log **Package DEĞİLDİR** | `[d1]` — Library kataloğunda `trading_signal`/`trade_log` kökü yok; paket kökü `GET /trading-signals/<pkg>` → **404** |
| 2 | **Backtest Run ≠ Backtest Result** | `[a3]` — hazır olmayan kompozisyonda run **409** ile reddedildi ve Results düzlemi **0 → 0** kaldı; yalnız SUCCEEDED run Result üretir (pozitif taraf: spec 05) |
| 3 | UI hidden/disabled **authorization değildir** | 9 ayrı yüzey plain USER token'ı ile yeniden saldırıldı: run admission, library approve, library delete, ESP activate, agent runtime pause, `GET /trash-entries`, trash detay, restore-preflight, restore, purge → hepsi **403** |
| 4 | Uzun işler **durable queue** üzerinden | `[d4]` directive **202** (inline çalıştırma yok) · `[e5]` purge **202** + `purge_job_id` · `af_follow_run` gerçek worker'ı yoklar, senkron kestirme yok · yedi düzlemin tamamı broker-connected |

---

## 5. Bu koşunun İKİ SKIP'i (PASS değildir)

1. **`[c5]` pozitif ESP activate→deprecate koşulmadı.** Probe resolver'ın doğrulaması
   `validation_state=failed / vectors_run=0` ile bitiyor; harness çalıştırılabilir test
   vektörü **sentezlemiyor**. Bunun yerine güvenlik yönü iddia edildi: doğrulanmamış bir
   resolver **trusted-active'e yükseltilemiyor**. Pozitif yol in-process kapsamdadır:
   `backend/tests/integration/test_esp_persistence.py`.
2. **`[d3]` Tool Gateway çağrı günlüğü egzersiz edilmedi.** Yeni tohumlanmış bir yığında
   agent task yok; `GET /agent-tasks` **200** ile boş döner. Tool-call günlüğü okunmadı.

---

## 6. Blocker 2 neden **AÇIK** kalıyor

Kapsam boşluğu kapandı, beş akış da koştu, ortam iddiası düzeltildi. Kalan **tek** kalem:

> **`flows` bir CI kapısı DEĞİLDİR.** Yerel bir komuttur; hiçbir workflow onu koşmaz.
> Kapıya dönüşene kadar bir regresyon sessizce geri gelebilir. Bunu bağlamak ayrı bir
> karardır (CI'da 12 konteynerlik bir yığın daha + koşu süresi) ve bu slice'ta **yapılmadı**.

Ayrıca §5'teki iki SKIP açık iştir. Verdict bu yüzden **"kapandı" değil, "kısmen kapandı"**.

---

## 7. P5'in bloke kalemleri — Docker çalıştığı için koşuldu

| # | Kalem | Komut | Exit | Sonuç |
|---|---|---|---:|---|
| 3 | Servis bazında health | `COMPOSE_PROJECT_NAME=entropia-e2e-flows ./scripts/acceptance.sh` | **0** | **PASS** — 15 servis, hiçbiri exited/restarted/unhealthy |
| 4a | `scripts/smoke.sh` | `BASE_URL=…:18030/api/v1 FRONTEND_URL=…:18110 ./scripts/smoke.sh` | **0** | **PASS** — postgres/redis/object storage ok, `/metrics` servis ediliyor, session modunda `X-Actor-Id` yok sayılıyor |
| 4b | `scripts/worker-restart-smoke.sh` | `COMPOSE_PROJECT_NAME=entropia-e2e-flows ./scripts/worker-restart-smoke.sh` | **0** | **PASS** — yedi düzlem SIGKILL + restart, `package_root` 15→15, `audit_events` 69→69, `outbox_events` 40→40 → **mükerrer artefakt yok** |
| 2a | §9.4 session-clean | `./scripts/e2e-acceptance.sh session` | **0** | **PASS** — 27 passed / 0 failed / 0 skipped |
| 2b | §9.5 legacy-upgrade | `./scripts/e2e-acceptance.sh legacy` | **0** | **PASS** — 15 passed / 0 failed / 0 skipped |
| 2c | §9.6 dev-auth | `./scripts/e2e-acceptance.sh dev-auth` | **0** | **PASS** — 9 passed / 0 failed / 0 skipped |

Ham: `p5b_acceptance_gate.txt` · `p5b_smoke.txt` · `p5b_worker_restart.txt` · `p5b_three_auth_modes.txt`.

**P5 böylece "1 PASS / 3 BLOCKED" yerine 4/4 ölçülmüş durumdadır** — ve bunu mümkün kılan tek
şey, aynı hostta daemon'ın takılı olmamasıdır (§1.1). Üç auth akışı bu dalgada
**değiştirilmedi**; 08-07'de de aynı kodla oradaydılar.

---

## 8. Bu dalgada değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `scripts/lib/acceptance-flows.sh` | **YENİ** — beş akış, iki katman, dört tavizsiz kural |
| `scripts/e2e-acceptance.sh` | `flows` alt-komutu + `all`'a dahil; `API_CORS_ORIGINS` (ölçülen tuzak: web origin allowlist'te değilken **her** tarayıcı yolculuğu düşüyor, curl ise aynı API'yi sağlıklı raporluyor); SKIP sayacı sonuç satırında |
| `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts` | sabit-kodlu `http://localhost:8000/api/v1` yedeği `utils/api.ts::API_BASE` ile değiştirildi — `E2E_API_BASE_URL` set değilken **aynı literal**, yani CI davranışı birebir korunur |

**Ürün kodu değişmedi.** `backend/src` ve `frontend/src` bu dalgada hiç düzenlenmedi.
