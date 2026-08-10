<!-- doc-status: current -->

# P10-B — Alert notification path (RC blocker 3)

**Dalga:** ADIM 31 · **Tarih:** 2026-08-10 · **Branch:** `ops/rc-blocker3-alertmanager`
**Base:** `origin/main` = `20108af` (`fix(docs): rename video walkthrough folder to a Windows-safe path (#648)`)
**Kapsam:** `docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` **§6.3 blocker'ı** — YALNIZ o.
Blocker 1 (A-08), 2 (kabul akışları) ve 4 (react-router freeze) bu slice'a **girmedi**.

**Host:** darwin 25.5.0 · Docker 29.4.0 · compose v5.1.2

> **Kayda geçirilen kendi hatam:** bu suite'in **ilk** koşusu **1 failed** verdi — `test_repository_facts_guard.py::test_the_repository_itself_passes_the_documentation_truth_gate`. Sebep: slice bir test dosyası eklediği için `docs/generated/repository_facts.*` ve README'nin üretilmiş bloğu bayatladı, ayrıca ikinci bir kickoff `doc-status: current` iddia etti. **Kapı tam olarak bunun için var.** Artefaktlar yeniden üretildi, `docs/ADIM30_LANDED_KICKOFF.md` `historical`'a indirildi, suite yeniden koşuldu. Gizlenmedi: `p10b_backend_suite.txt` §1b.

---

## 1. Kapatılan blocker — tek cümlede

Ateşleyen 11 alarm kuralının (7'si `severity: page`) hiçbiri bir insana ulaşmıyordu.
**Artık ulaşıyor**, ve bildirim yolu **fail-closed**'dur: hedef adres verilmezse
Alertmanager **başlamaz**.

---

## 2. ÖNCE DOĞRULAMA — raporun iddiaları yeniden ölçüldü

Slice'ın talimatı açıktı: *"Rapordaki sayıları KOPYALAMA — bu koşunun kanıtını yaz."*
Ham çıktı: **`p10b_preexisting_state.txt`**.

| # | §6.3 iddiası | `origin/main` (`20108af`) üzerinde ölçülen | Doğru mu? |
|---|---|---|---|
| 1 | `ops/prometheus/prometheus.yml` içinde `alerting:` bloğu yok | `grep -n '^alerting:'` → **eşleşme yok** | ✅ |
| 2 | `docker-compose.yml`'de Prometheus servisi yok | `grep -nE '^  (prometheus\|alertmanager):'` → **ikisi de yok** | ✅ |
| 3 | Repo genelinde receiver / routing / silence / on-call yok | `ops/ scripts/ .github/ backend/src/` içinde **3 dosya eşleşiyor, hepsi yokluğu anlatan YORUM** — tek satır yapılandırma yok | ✅ |
| 4 | 11 kural | `grep -c '^      - alert:'` → **11** | ✅ |
| 4b | 7'si page seviyeli | `severity: page` **7** · `severity: ticket` **4** | ✅ |
| 5 | promtool kapısı | CI job `alerts` (`Alert rules — promtool`) → `scripts/alert-rules-gate.sh` · bu koşuda **exit 0**, 11 kural | ✅ |

**Beş iddianın beşi de doğrulandı.** Madde 3'te dosya listesi ilk bakışta iddiayı
çürütür gibi görünüyor; ham çıktı hit'leri satır satır basar ve **hepsinin yokluğu
anlatan yorum satırları** olduğunu gösterir.

---

## 3. Karar: (A) sevk — (B) imzalı sapma SEÇİLMEDİ

**Gerekçe (slice'ın kendi gerekçesi, kayıt için):** eksik olan bir on-call
*organizasyonu* değil, bildirim *yolunun kendisiydi*; o yol repo içi yapılandırmadır.
Yedi page seviyeli alarm "ürün kullanılamaz", "Postgres erişilemez", "async düzlem hiç
kurulmamış" diyor — bu sessizliği imzalamak D-10'dan (WCAG 1.4.3 kontrast, ölçülmüş ve
sınırlı) **kategorik olarak farklı** olurdu.

**Ek olarak: agent zaten imzalayamaz.** İmzalayan verilmedi, ve bu repo (D-10 ve
`security-allowlist.json` disiplini) imzayı **adı verilmiş bir insana** bağlar.

---

## 4. Sevk edilen — dört kalem

### 4.1 Alertmanager servisi + yapılandırma

| Kalem | Dosya | Ölçülen davranış |
|---|---|---|
| Routing ağacı | `ops/alertmanager/alertmanager.yml` | `severity: page` → **`entropia-page`** (group_wait 30s, repeat **1h**) · `severity: ticket` → **`entropia-ticket`** (group_wait 5m, repeat **12h**). İki AYRI receiver, iki AYRI zamanlama. |
| Kök route | aynı | **Gerçek bir receiver** (`entropia-page`). Eşleşmeyen alarm düşürülmez — **page eder**. `receiver: null` catch-all'ı bilerek reddedildi. |
| Inhibit | aynı | 3 kural, **hepsi aşağı yönlü**: `EntropiaApiDown` → 5xx + latency · `…NeverRecorded` → `…Stale` · `OutboxLagSevere` → `OutboxLagGrowing`. Üçünde de **kaynak alarm teslim edilir**. |
| Silence | `docs/runbooks/alert-notification.md` §4 | Runtime state, config değil → `amtool silence add` + published :9093. Birkaç kuralın `false_positives` notu bunu açıkça istiyor. |

### 4.2 Prometheus `alerting:` bloğu

`ops/prometheus/prometheus.yml` → `alerting.alertmanagers[0].static_configs[0].targets =
["alertmanager:9093"]`. `test_prometheus_sends_its_alerts_to_the_shipped_alertmanager`
hedefin **compose'da gerçek bir servis** olduğunu da doğrular.

### 4.3 Provenance kapısı — §6.3'ün İKİNCİ doğrulanmamış noktası

**Statik yarı** (her PR'da): `test_the_prometheus_service_is_configured_from_this_tree` —
servisin **tüm `ops/` ağacını** mount ettiğini (yalnız `prometheus/` mount edilse
`rule_files: ../alerts/…` **başarıyla hiçbir şeye** çözülürdü) ve launcher'ın config'i
**şablonlamadan, `cp -R` ile birebir** stage ettiğini pinler.

**Canlı yarı** (proof faz 3): üç bağlı halka —

| Halka | Ölçülen |
|---|---|
| (a) hash | çalışma ağacı / mount / staged **üçü de `f1c1949c6d3382fa5450138604759509ac57262f93fbb219c3356b34e5be0e19`** |
| (b) flag | `--config.file` = `/tmp/ops/prometheus/prometheus.yml` — yani (a)'daki dosya |
| (c) parse | yürürlükteki config `entropia-api`, `api:8000`, `alertmanager:9093`, `entropia.rules.yml`, `deployment: entropia` taşıyor (hepsi **tracked dosyadan okunarak** üretildi) |
| (d) kurallar | yüklenen alarm adları **11 = 11**, `diff` boş |

> **Neden basit diff DEĞİL — ölçüldü, varsayılmadı.** İlk yazılan kapı
> `GET /api/v1/status/config` çıktısını çalışma ağacındaki dosyayla diff'liyordu ve
> **KIRMIZI verdi**: Prometheus config'i **marshalled** döndürüyor — `scrape_protocols`
> ve `runtime.gogc` gibi varsayılanlar enjekte ediliyor, tüm yorumlar siliniyor.
> Bu, kapının yanlış tasarımıydı, ürünün hatası değil. Byte-özdeşlik bu uçtan **asla**
> elde edilemez; yukarıdaki zincir onun yerini alır.

### 4.4 Uçtan uca kanıt

`scripts/alert-notification-proof.sh` — dört faz, **sentetik seri YOK**.

---

## 5. Ölçülen kanıt

### 5.1 Kapılar (CI'da koşacak)

| Kapı | Komut | Exit | Ölçülen | Ham dosya |
|---|---|---:|---|---|
| promtool (mevcut, yeni `alerting:` bloğuyla) | `scripts/alert-rules-gate.sh` | **0** | `check config` SUCCESS · `check rules` **11 rules** · `test rules` SUCCESS | `p10b_promtool_gate.txt` |
| amtool (**YENİ**) | `scripts/alert-notification-gate.sh` | **0** | `check-config` SUCCESS (3 inhibit, 2 receiver) · `severity=page` → **`entropia-page`** · `severity=ticket` → **`entropia-ticket`** · etiketsiz alarm → **`entropia-page`** (düşmüyor) | `p10b_amtool_gate.txt` |
| contract (**YENİ**) | `pytest tests/contract/test_alert_notification_contract.py` | **0** | **21 passed** | `p10b_contract_tests.txt` |
| contract (regresyon) | `pytest test_alert_notification_contract + test_alert_rules_contract` | **0** | **79 passed** (21 yeni + **58 mevcut, regresyonsuz**) | `p10b_contract_tests.txt` |
| backend tam suite | `uv run pytest` (izole DB, tek çağrı) | — | **3987 passed / 1 xfailed / 0 failed**, coverage **%93.53** (kapı ≥90) | `p10b_backend_suite.txt` |

### 5.2 Uçtan uca proof — `p10b_notification_proof.txt`, **exit 0**

| Faz | Ne kanıtlandı | Ölçülen |
|---|---|---|
| **1 — FAIL-CLOSED** | Hedef yoksa Alertmanager **başlamaz** | `ALERTMANAGER_NOTIFY_URL=""` → **exit 78** + `FATAL: ALERTMANAGER_NOTIFY_URL is unset or empty` · `="not-a-url"` → **exit 78** + `not an http:// or https:// URL` |
| **2 — UP** | Sevk edilen çift, sevk edilen config'lerle kalkar | `prometheus` + `alertmanager` **ready** |
| **3 — PROVENANCE** | Yürürlükteki config bu ağacınki | §4.3'teki dört halka, hepsi ✅ |
| **4 — DELIVERY** | Gerçek bir alarm alıcıya ulaşır | `EntropiaApiDown` ateşledi ve alıcı şunu aldı: `"receiver": "entropia-page"` · `"alertname": "EntropiaApiDown"` · `"severity": "page"` · `"status": "firing"` |

**Faz 4'te alarm neden gerçek:** `api` servisi hiç koşmuyor, dolayısıyla
`up{job="entropia-api"} == 0` **basitçe doğru**. Seri enjekte edilmedi, eşik gevşetilmedi,
sevk edilen hiçbir dosya düzenlenmedi. Kural `for: 2m` taşıyor ve kök route `group_wait:
30s` — teslimat o süreden sonra gerçekleşti.

---

## 6. FAIL-CLOSED tasarımı — nasıl garanti edildi

| Yasak (slice'ın sözleriyle) | Nasıl engellendi |
|---|---|
| Placeholder receiver YOK | `test_no_receiver_is_a_silent_black_hole` — **`amtool check-config` notifier config'i OLMAYAN bir receiver'a SUCCESS döndürüyor** (v0.28.1'de ölçüldü, varsayılmadı). Tam olarak bu şekli reddeder. |
| `/dev/null` route YOK | `test_the_root_receiver_is_a_real_one` — kök receiver gerçek olmalı ve adında `null` geçemez |
| Sessiz düşürme YOK | `test_every_severity_the_rules_emit_has_a_route` + `test_every_routed_receiver_is_declared` |
| `default receiver: null` YOK | aynı |
| Hedef adres uydurulmaz | `test_the_alertmanager_service_has_no_default_destination` — compose'daki değer **tam olarak** `${ALERTMANAGER_NOTIFY_URL:-}` olmalı; herhangi bir varsayılan reddedilir |
| Kapı kırmızı olur | `test_the_entrypoint_actually_refuses_a_missing_destination` (kaynak okur: `require_url` + `exit 78` + `:-` varsayılanı yok) + proof faz 1 (davranışı ölçer) |

**Neden `${VAR:?...}` kullanılmadı — kayda değer bir tasarım kararı:** compose'un
zorunlu-değişken işareti **tüm dosyanın** interpolation'ını iptal eder, yani
`prometheus`/`alertmanager` profil kapalı olsa bile repo'daki **her** `docker compose up`
kırılırdı (`acceptance.sh`, `e2e-acceptance.sh`, `a11y-audit-stack.sh`). Ret bu yüzden
**konteynerin içinde** yaşıyor.

---

## 7. Mevcut yığına etkisi — YOK (ölçüldü)

| Kontrol | Sonuç |
|---|---|
| `prometheus` / `alertmanager` profili | `profiles: ["observability"]` — düz `docker compose up` **ikisini de başlatmaz** (`test_the_observability_plane_is_profiled_off_by_default`) |
| `test_worker_plane_deployment.py` | Yeni servislerin `--queues` komutu yok ve `image` alanları `entropia-backend:local` değil → **etkilenmez**, geçiyor |
| `test_default_credential_gate.py` | `.env.example`'a yalnız **ekleme** yapıldı; okuduğu üç anahtar el değmedi → geçiyor |
| `backend/src` · `frontend/` | **hiç düzenlenmedi** |
| migration · lockfile · imza · tag · release · issue | **hiçbiri yok** |
| Üretilmiş artefakt deltası | **yalnız test collection sayısı** (3415→3432, 329→330 dosya). Alembic head, `ENGINE_VERSION`, route/tablo **hareket etmedi** — bir ops/CI slice'ının üretmesi gereken delta budur |

---

## 8. KAPANMAYAN ARTIK — dürüst kayıt

§6.3'ün **iki** doğrulanmamış noktası vardı. **İkincisi (provenance) kapandı.**

> **BİRİNCİSİ KAPANMADI: kurallar gerçek production serilerine karşı hiç
> değerlendirilmedi.** `promtool test rules` sentetik seri kullanır; bu slice'ın uçtan
> uca kanıtı **tek bir yapısal kuralı** (`up == 0`) ateşler. Gerçek trafiğe göre yanlış
> ayarlanmış bir eşik hâlâ *doğru* görünür.

**Bu slice'ta kapanamaz** — yalnız gerçek trafik biriktikçe kapanır, ve repo içindeki
hiçbir kapı onu kapatamaz. **Kalıcı imzalı sapma DEĞİLDİR** ve öyle kaydedilmemiştir;
süreli (`expires`'lı) bir kayda dönüştürülmesi istenirse **imzayı agent atayamaz**.

Blocker olmayan ama kapanmamış diğer kalemler (raporun §6.7'sine işlendi):

| # | Kalem |
|---|---|
| **P10-B3** | Delivery proof'u **bir CI kapısı değil** — config yarısı kapılı, teslimat yarısı değil. Kapıya bağlamak bir maliyet kararı, insan işi. |
| **P10-B4** | **Monitörü izleyen yok** — `prometheus_notifications_errors_total` Prometheus'un kendi `/metrics`'inde ve onu hiçbir şey scrape etmiyor. Döngüsel olmayan çözüm ikinci bir Prometheus ister. |
| **P10-B5** | **On-call rotasyonu / escalation / acknowledgement yok** — Alertmanager'ın ack kavramı yoktur; repo dışı organizasyonel karar. |

Tam liste (5 madde): `docs/runbooks/alert-notification.md` §5.

---

## 9. Verdict'e etkisi

**Blocker sayısı 4 → 3. Verdict BLOCKED KALIR.**

| # | Blocker | Durum |
|---|---|---|
| 1 | A-08 insan kabul denetimi | **AÇIK** — bu slice'a girmedi |
| 2 | Kabul akışları (`flows` CI kapısı değil) | **AÇIK** — bu slice'a girmedi |
| ~~3~~ | ~~Alertmanager~~ | **KAPANDI** (bu belge) |
| 4 | react-router imzasız freeze | **AÇIK** — bu slice'a girmedi |

Numaralandırma **bilerek korunmuştur**: kalanlar (1), (2), (4) olarak anılmaya devam
eder. Yeniden numaralandırmak, bu belgeye atıf yapan merge edilmiş PR gövdelerini ve
commit mesajlarını geçmişten koparırdı — repo'nun ADIM 16 / ADIM 21 çakışmasında verdiği
kararın aynısı.

**"READY" YAZILMADI ve yazılamaz.**
