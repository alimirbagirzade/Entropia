<!-- doc-status: historical -->
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı). Bu belge **bir sonraki slice'ın tohumudur**;
> içindeki sayılar 2026-08-10 ADIM 30 koşusunun değerleridir.

# ADIM 30 landed — sırada ne var

## Nerede duruyoruz

RC readiness raporunun (`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`) **Blocker 2**
kalemi — "uçtan uca kabul akışları koşulmadı" — **kısmen kapandı**:

* Beş kabul akışı harness'a yazıldı ve koştu: **60 passed / 0 failed / 2 skipped**, exit 0;
  tarayıcı katmanı **5 passed**. Kanıt `docs/releases/evidence/2026-08-10/`.
* P5'in üç bloke kalemi de koşuldu (session **27/0**, legacy **15/0**, dev-auth **9/0**,
  `acceptance.sh` / `smoke.sh` / `worker-restart-smoke.sh` **exit 0**).
* Raporun iki iddiası düzeltildi: "docker ps → 124" yeniden üretilemedi; "hiçbir katmanda
  doğrulanmadı" genellemesi tarayıcı katmanını atlıyordu.

**RC verdict'i hâlâ BLOCKED.** Bu slice yalnız blocker 2'ye dokundu; 1 (A-08), 3
(Alertmanager) ve 4 (react-router freeze) **kapsam dışıydı ve açıktır**.

## Bu slice'ın bıraktıkları — reuse anchor'ları (tam sembol adları)

| Sembol | Ne yapar |
|---|---|
| `scripts/e2e-acceptance.sh::flow_acceptance` | izole yığını kaldırır + tohumlar; `E2E_KEEP_UP=1` yığını ayakta bırakır |
| `scripts/lib/acceptance-flows.sh::af_run_all_flows` | beş akışın sürücüsü |
| `..::af_bootstrap_actors` | Admin + **plain USER** token'ı — tavizsiz kural 3'ün dayanağı |
| `..::af_flow_a_strategy_run` · `af_follow_run` | readiness OCC · Run≠Result · durable run takibi |
| `..::af_flow_b_library_validation` | katalog · head-match · USER 403 |
| `..::af_flow_c_esp_lifecycle_export` | ESP create/validate · registry OCC · trust gate · export zarfı |
| `..::af_flow_d_agent_signal_tools` | TS≠Package · K-07 fail-closed · agent yüzeyleri |
| `..::af_flow_e_trash_lifecycle` | O-12 dual-token 409 · **restore** ayağı · O-30 purge gövdesi |
| `..::af_browser_layer` | var olan spec 05/18/20-library/06'yı **koşar** — yeniden yazmaz |
| `..::af_skip` / `AF_SKIP_N` | SKIP kendi sayacında; PASS'e asla katılmaz |

## Sıradaki iş — üç aday, öncelik sırasıyla

### 1. `flows`'u bir CI kapısına bağla (blocker 2'yi TAM kapatan tek adım)

Bugün hiçbir workflow `flows`'u koşmuyor: tarayıcı yarıları `.github/workflows/e2e.yml` ile
kapılı, **sunucu yarıları hiçbir yerde değil**. Maliyet gerçek — CI'da ikinci bir 12
konteynerlik yığın + koşu süresi — bu yüzden **insan kararıdır**. Karar verilirse en ucuz
biçim: `e2e.yml`'e yeni bir job değil, mevcut `e2e` job'ının **sonuna** bir adım
(`scripts/e2e-acceptance.sh flows` yerine, zaten ayakta olan compose yığınına karşı yalnız
sunucu katmanını koşan bir varyant) — böylece ikinci bir yığın kalkmaz.
**Dikkat:** `ci.yml`'in concurrency kusuru (main'de kuyruğa giren koşu bir öncekini iptal
ediyor) `e2e.yml`'de **yok** (`cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`).

### 2. İki SKIP'i kapat

* **Pozitif ESP activate→deprecate.** Probe resolver `validation_state=failed /
  vectors_run=0` veriyor; `esp_cmd.run_resolver_validation`'ın çalıştırılabilir test vektörü
  beklediği şekli çıkar ve `af_flow_c_esp_lifecycle_export`'ta gerçek bir vektör seti kur.
  Pozitif yol bugün yalnız in-process kapsamda: `backend/tests/integration/test_esp_persistence.py`.
* **Tool Gateway çağrı günlüğü.** Taze yığında agent task yok. `POST /agent-directives`
  sonrası coordinator'ın task üretmesini bekleyip `GET /agent-tasks/{id}/tool-calls`'ı
  gerçekten oku (durable yol, senkron kestirme yok).

### 3. Raporun kalan blocker'ları — hepsi **insan işi**, agent kapatamaz

1 (A-08: #514 yeniden açılsın **veya** D-10 biçimi imzalı sapma) · 3 (Alertmanager veya
imzalı sapma) · 4 (react-router freeze'ine `owner` + `expires`).

## Çalışma yöntemi — bu slice'ta işe yarayanlar

* **Önce ölç, sonra yaz.** Rapordaki iki iddianın ikisi de yeniden ölçüldüğünde değişti.
  Şema tahmin etme: `docs/openapi.json`'dan çıkar (`python3 -c` ile `components.schemas`),
  ya da ayakta bir yığına GET at.
* **İzole yığın tuzakları (ikisi de bu slice'ta yaşandı):**
  `API_CORS_ORIGINS` olmadan web origin bloklanır ve **her** tarayıcı yolculuğu düşer — oysa
  curl (Origin göndermez) aynı API'yi sağlıklı raporlar. `E2E_API_BASE_URL`,
  `E2E_BASE_URL` kadar yük taşır: sunucu gerçeğini assert eden spec'ler API'ye doğrudan gider.
* **İterasyon ucuzlatma:** `E2E_KEEP_UP=1` yığını ayakta bırakır; ama davranış ölçümü için
  **temiz DB** şart (`docker compose -p entropia-e2e-flows down -v`), yoksa ikinci koşu
  "username taken" / "canonical_key exists" gibi ilk koşunun kalıntılarına çarpar.
* **Yeşile zorlama yok.** Koşmayan adım `af_skip` ile kaydedilir, PASS sayısına katılmaz.

---

## Paste-ready resume prompt

```
ENTROPIA — ADIM 31: `flows` harness'ını CI kapısına bağla (RC blocker 2'nin kalanı)

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — git fetch && git log --oneline origin/main -6)
Branch: feat/ci-acceptance-flows-gate

OTURUM BAŞLANGICI
1. docs/ADIM30_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §ADIM 30 →
   docs/PROJECT_HISTORY.md §ADIM 30 → docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.2
2. Harness: scripts/e2e-acceptance.sh (`flows` alt-komutu) + scripts/lib/acceptance-flows.sh

AMAÇ
RC §6.2'yi TAM kapatmak: beş kabul akışı yazıldı ve koştu ama `flows` bir CI kapısı DEĞİL.
Sunucu katmanındaki bir regresyon bugün sessizce main'e inebilir.

İŞ
1. En ucuz bağlama biçimini seç ve gerekçesini yaz: `.github/workflows/e2e.yml`'in MEVCUT
   `e2e` job'ı zaten bir compose yığını kaldırıyor ve tohumluyor — sunucu katmanını O yığına
   karşı koşan bir varyant, ikinci bir 12 konteynerlik yığından ÇOK daha ucuzdur.
   `af_run_all_flows`'u yığın kaldırmadan çağırabilecek şekilde ayır (flow_acceptance yalnız
   yığın yönetimi yapsın).
2. Kapı gerçekten kapı olsun: job kırmızıya düşebilmeli. Yeşil bir rozetin ölçmediği bir şeyi
   ölçtüğü sanılmasın — README/docs/E2E_ACCEPTANCE.md'de neyin kapılı olduğunu AÇIKÇA yaz.
3. Mümkünse iki SKIP'ten birini kapat (ESP test vektörleri VEYA Tool Gateway çağrı günlüğü).

TAVİZ VERİLEMEZ
· Ürün kodu değiştirme; bu bir harness/CI slice'ı.
· Yeşile zorlama YOK — koşmayan adım SKIP, PASS değil.
· UI hidden/disabled AUTHORIZATION DEĞİLDİR · Run ≠ Result · TS/TL Package DEĞİLDİR ·
  uzun işler durable queue üzerinden.
· Bir kapı eklerken maliyetini ölç ve yaz (CI dakikası + konteyner sayısı).

KAPSAM DIŞI
· Blocker 1 (A-08) · 3 (Alertmanager) · 4 (react-router freeze) — hepsi insan işi.
· PR B / ItemParticipant (post-V1, SHARED_ALLOCATION_STATUS=future_dev).

ÖLÇÜM TUZAKLARI
· pytest'i | tail'e BORULAMA; alt küme koşarken --no-cov EKLE.
· vitest: --no-file-parallelism ZORUNLU.
· İzole yığın: API_CORS_ORIGINS + E2E_API_BASE_URL olmadan tarayıcı katmanı düşer.
· Temiz DB olmadan ikinci koşu ilk koşunun kalıntısına çarpar.
· docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ
· CLAUDE.md §Session CLOSING ritüelinin 6 maddesi.
· cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
