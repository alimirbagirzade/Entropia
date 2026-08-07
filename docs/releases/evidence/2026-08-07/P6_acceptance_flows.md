<!-- doc-status: historical -->
> **EVIDENCE RECORD — 2026-08-07.** Bu belge o gün, o ağaç üzerinde koşulan kabul-akışı
> kanıtının kaydıdır. Sayılar koşuldukları anın değerleridir; güncel sayısal otorite
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 29 / P6 — Uçtan uca kabul akışları

**Verdict: BLOCKED.** Altı akıştan **yalnız (f)** istendiği gibi koşturulabildi ve geçti.
**(a)–(e) BLOCKED'dır** — ve blocker'ın sebebi ortam arızası *değil*: görevin adlandırdığı
iki script, `scripts/e2e-acceptance.sh` ve `scripts/acceptance.sh`, o beş akışı **hiç
uygulamıyor**. Docker ayağa kalksaydı da bu beş akış koşmayacaktı. Bu, ikinci ve
**bağımsız** bir blocker'ın (uygulama stack'i ayakta değil, OrbStack VM takılmış) üstünde
duran, ondan daha temel bir bulgudur.

## Özet — altı akış

| # | Akış | Komut | Exit | Sonuç |
|---|---|---|---|---|
| a | Strategy → Ready-check → Run → Result | — (adlandırılan harness'ta yok) | — | **BLOCKED** — kapsam boşluğu |
| b | Library validation | — (adlandırılan harness'ta yok) | — | **BLOCKED** — kapsam boşluğu |
| c | ESP lifecycle + export | — (adlandırılan harness'ta yok) | — | **BLOCKED** — kapsam boşluğu |
| d | Agent Strategy / Trading Signal tools | — (adlandırılan harness'ta yok) | — | **BLOCKED** — kapsam boşluğu |
| e | Trash: soft-delete → restore → purge | — (adlandırılan harness'ta yok) | — | **BLOCKED** — kapsam boşluğu |
| — | *harness denemesi* | `timeout 90 ./scripts/acceptance.sh` | **124** | **BLOCKED** — banner'dan sonra asılı kaldı |
| — | *harness denemesi* | `timeout 90 ./scripts/e2e-acceptance.sh all` | **124** | **BLOCKED** — hiç çıktı vermeden asılı kaldı |
| f1 | `scripts/backup.sh` | `./scripts/backup.sh` | **0** | **PASS** |
| f2 | `scripts/restore.sh` | `RESTORE_DB=… OBJECT_STORAGE_BUCKET=… ./scripts/restore.sh <dir> --yes` | **0** | **PASS** |
| f3 | `scripts/backup-verify.sh` | `./scripts/backup-verify.sh <dir>` | **0** | **PASS** |
| f4 | `scripts/dr-acceptance.sh` (1. koşu) | `./scripts/dr-acceptance.sh` | **1** | **FAIL** → eşzamanlılık artefaktı olarak karara bağlandı |
| f4b | `scripts/dr-acceptance.sh` (2. koşu) | `./scripts/dr-acceptance.sh` | **0** | **PASS** — 8 passed / 0 failed |

## Ağaç ve ortam

| | |
|---|---|
| HEAD | `6c239e4` |
| Branch | `claude/entropia-v18-acceptance-flows-1b0a64` (worktree) |
| Working tree | temiz (yalnız bu dalganın ürettiği kanıt dosyaları untracked) |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` |
| `pg_dump` / `pg_restore` | 16.14 (Homebrew) |
| `mc` (MinIO client) | RELEASE.2025-08-13T08-35-41Z |
| Canlı DB `entropia` alembic head | `0039_backtest_run_cancellation` |
| Repo alembic head | `0043_i08_registry_strategy_fks` |

> **Dürüst not — dev DB sürüm geridedir.** DR kanıtı `0039` başındaki canlı geliştirme
> veritabanı üzerinde alınmıştır; repo başı `0043`'tür, yani dev DB **dört migration
> geridedir**. `0040`–`0043` ile gelen tablo/kolonlar bu DR turunda hiç round-trip
> edilmemiştir. Bu bir DR kusuru değil, kanıtın **kapsam sınırı**dır.

### Stack durumu — "ayakta duran stack" varsayımı tutmadı

Görev "ayakta duran stack üzerinde" koşmayı istiyordu. Ölçüm:

| Port | Servis | Durum |
|---|---|---|
| 8000 | API | **KAPALI** |
| 5173 | web | **KAPALI** |
| 5432 | PostgreSQL | AÇIK (Homebrew native) |
| 9000 | MinIO | AÇIK (HTTP 403 = canlı) |
| 6379 | Redis | AÇIK |

Yani **altyapı düzlemi ayakta, uygulama düzlemi değil.** Docker kontrol düzlemi de
kullanılamaz durumda: OrbStack VM takılmış — `orb status` 10 s'de dönmedi (`rc=124`),
`docker ps` / `docker version` / `docker compose` çağrılarının hepsi süresiz asılı kalıyor,
`OrbStack Helper vmgr` süreci %128 CPU'da ve 403 dakika CPU zamanı biriktirmiş.

**Karar (insan):** OrbStack **yeniden başlatılmadı.** Restart, aynı makinede koşan paralel
worktree oturumlarının container'larını öldürürdü; ayrıca (a)–(e)'yi de kurtarmazdı
(§Kapsam boşluğu). Bu yüzden "stack ayakta değil" raporda **ikinci** blocker olarak
kayıtlıdır, birinci değil.

### İki harness gerçekten denendi — gözlenen davranış

Bu iki script "koşturulamaz" diye varsayılmadı; **çağrıldı** ve davranışları kaydedildi.

```bash
timeout 90 ./scripts/acceptance.sh
```

**Exit 124** (90 s'de SIGTERM). Gözlenen: yalnız `== Acceptance gate (session stack) ==`
banner'ı basıldı, sonra `docker compose config --services` üzerinde süresiz asılı kaldı.

```bash
timeout 90 ./scripts/e2e-acceptance.sh all
```

**Exit 124** (90 s'de SIGTERM). Gözlenen: **tek satır çıktı bile yok.**

> **Bulgu — preflight koruması takılmış daemon'a karşı işlemiyor.**
> `e2e-acceptance.sh` bir erişilebilirlik kapısı taşıyor:
> `if ! docker version >/dev/null 2>&1; then echo "FATAL: the Docker daemon is not
> reachable…"; exit 2; fi`. Ama bu satıra **hiç ulaşılmıyor**: bir önceki
> `docker compose version` çağrısı sonsuza dek asılı kalıyor. Yani koruma **yok** bir
> daemon'a karşı tasarlanmış; **takılmış** bir daemon'da script net bir `exit 2` yerine
> sessizce sonsuza kadar asılı kalıyor. CI'da bu, iş bir job timeout'una çarpana kadar
> teşhissiz bekleme demektir. Kayda geçti, düzeltilmedi (P6 kapsamı dışı).

## Neden (a)–(e) BLOCKED — harness kapsam boşluğu

Bu bölüm bulgunun denetlenebilir kanıtıdır. `scripts/acceptance.sh` bir **container sağlık
kapısıdır**: Compose servislerini gezer, one-shot'ların `exit 0` olduğunu, diğerlerinin
`running` + `healthy` + `RestartCount 0` olduğunu doğrular. Tek bir alan (domain) iddiası
içermez. `scripts/e2e-acceptance.sh` ise bir **auth/kimlik bootstrap harness'ıdır** —
audit §9.4 / §9.5 / §9.6, yani `session` / `legacy` / `dev-auth` üç akışı.

`e2e-acceptance.sh`'in çağırdığı **HTTP uçlarının tamamı**:

```
GET  /meta                      POST /auth/signup
GET  /me                        POST /auth/login
GET  /admin/users               POST /auth/logout
GET  /mainboards/default        POST /users/<id>/role
GET  /auth/bootstrap-status
GET  /strategy-drafts
```

Terim taraması (her iki script, büyük/küçük harf duyarsız):

| Terim | `e2e-acceptance.sh` | `acceptance.sh` |
|---|---|---|
| `ready-check` / `readiness` | 0 | 0 |
| `backtest-run` / `backtest_run` / `/runs` | 0 | 0 |
| `backtest-result` | 0 | 0 |
| `library` | 0 | 0 |
| `trading-signal` / `agent-task` | 0 | 0 |
| `trash` / `soft-delete` / `purge` | 0 | 0 |
| `Idempotency-Key` / `If-Match` | 0 | 0 |
| `esp` | 1 → **yanlış pozitif** (`despite` kelimesi) | 0 |
| `validation` | 1 → **yanlış pozitif** (yorum satırı) | 0 |
| `export` | 7 → **yanlış pozitif** (shell `export` deyimleri) | 0 |

Üç isabetin üçü de yanlış pozitiftir; gerçek kapsam **sıfır**dır.

Harness'ın kendisi bu sınırı zaten yazıyor — `scripts/e2e-acceptance.sh:265`:

> `[13] per-plane JOB execution (data/backtest/agent pipelines) is exercised by backend
> integration — tests/integration/test_e2e_pipeline.py (honest boundary: not re-driven
> from this shell harness)`

Ve `scripts/smoke.sh:14-18` bunu bir **mimari karar** olarak kayda geçiriyor: tam uçtan uca
yol (ingest → package → strategy → mainboard → ready check → RUN → result → history →
trash/restore) kabuk harness'ında değil, **ayrılmış bir veritabanına karşı tek bir
entegrasyon testi** olarak koşulur.

**Sonuç:** (a)–(e) için "beklenen ≠ gözlenen" değil, **beklenen mekanizma mevcut değil**.
Görev bu beş akışı adlandırılan iki scriptten talep ettiği için sonuç BLOCKED'dır. Bu bir
regresyon değildir; boşluk repoda bilinçli ve belgelidir.

## Akış (f) — kanıt

> Aşağıdaki kod blokları script çıktısından **kısaltılmıştır** (mutlak yollar sadeleşti,
> bölüm başlıkları atlandı); satırların kendisi birebirdir. Kesilmemiş tam çıktı ve exit
> code'lar §Üretilen kanıt dosyaları'ndaki `.txt` dosyalarındadır.

### f1 · `scripts/backup.sh`

```bash
./scripts/backup.sh
```

**Exit 0 — PASS.** Gözlenen:

```
== Entropia backup -> backups/20260807T181213Z ==
  PASS  postgres.dump written (394464 bytes)
  PASS  alembic head: 0039_backtest_run_cancellation · public tables: 103
  PASS  mirrored bucket 'entropia-artifacts' via host mc
  PASS  MANIFEST.json written
BACKUP OK
```

`.env` bu ağaçta yok; script belgelenmiş Compose varsayılanlarına düştü
(`entropia`/`entropia`@`localhost:5432`) ve bunlar canlı Homebrew Postgres ile eşleşti.
Nesne depolama yarısı **WARN-skip etmedi**, gerçekten mirror etti.

### f2 · `scripts/restore.sh`

```bash
RESTORE_DB=entropia_p6_restore_scratch \
OBJECT_STORAGE_BUCKET=entropia-p6-restore-scratch \
  ./scripts/restore.sh backups/20260807T181213Z --yes
```

**Exit 0 — PASS.** Gözlenen: `PostgreSQL restored — alembic head now:
0039_backtest_run_cancellation`, `object storage restored via host mc`.

> **Neden iki override.** `restore.sh` yıkıcıdır: Postgres yarısı hedef veritabanındaki her
> nesneyi `--clean --if-exists` ile DROP eder. `RESTORE_DB` olmadan canlı `entropia`
> veritabanı silinip yedekten yazılırdı. Ayrıca **nesne yarısının kendi kapsam override'ı
> yoktur**: `RESTORE_DB` yalnız Postgres tarafını daraltır, bucket tarafı `--overwrite` ile
> **canlı** `entropia-artifacts` bucket'ına mirror eder. `dr-acceptance.sh` başlığı bu tuzağı
> açıkça uyarıyor. Bu yüzden `OBJECT_STORAGE_BUCKET` de scratch'e çevrildi; canlı bucket
> yalnız **okundu**.

### f3 · `scripts/backup-verify.sh`

```bash
./scripts/backup-verify.sh backups/20260807T181213Z
```

**Exit 0 — PASS.** Gözlenen:

```
  PASS  alembic_version present: 0039_backtest_run_cancellation
  PASS  public tables restored: 103
VERIFY OK
```

> **Gözlem — `dropdb` bu makinede takılıyor, script kusuru DEĞİL.** İlk koşuda `VERIFY OK`
> basıldıktan sonra `EXIT` trap'indeki `dropdb` 2 dakikayı aşarak SIGTERM aldı (exit 143);
> scratch DB önceden düşürülünce ikinci koşu temiz `exit 0` verdi. Bunun script'e özgü
> olmadığı **ayrıca doğrulandı**: dalga sonunda elle çalıştırılan
> `dropdb --if-exists entropia_p6_e2e` ve `… entropia_p6_restore_scratch` komutları da,
> hiçbir açık bağlantı ve hiçbir `pytest` süreci kalmamışken 30 s'de dönmedi. Yani sorun
> host düzeyindeki `dropdb`/Postgres'tedir. Yine de sonucu şudur: `backup-verify.sh`
> CI/cron'da sağlam bir yedeği **başarısız** raporlayabilir. Kayda geçirildi, düzeltilmedi
> (P6 kapsamı dışı).

### f4 · `scripts/dr-acceptance.sh` — 1. koşu FAIL, 2. koşu PASS

**1. koşu: exit 1 — FAILED.** 8 adımdan 6'sı geçti, ikisi düştü:

```
  FAIL  [5] row counts diverged:
      < audit_events=1032          (source)
      > audit_events=1030          (restored)
  FAIL  [7] audit_events diverged: source=2ee73868a0cce7492683872b599ef041
                                 restored=4a52995899a6de01d4498d844f113d22
  PASS  [3] alembic head identical: 0039_backtest_run_cancellation
  PASS  [4] 103 public tables, same set
  PASS  [6] all 10 immutable-evidence projections identical (1 carried rows)
  WARN  [6] only 1 evidence table(s) actually held rows — this run proves little
            about hash preservation.
  PASS  [8] 56 objects: path, size and md5 identical between the backup and the
            RESTORED bucket
  6 passed, 2 failed, 1 warned
DR ACCEPTANCE FAILED — see the FAIL lines above.
```

**2. koşu (aynı script, aynı ortam, değiştirilmiş hiçbir şey yok): exit 0 — PASS.**

```
  PASS  [5] row counts identical across all tables (1093 rows, 12 non-empty tables)
  PASS  [7] audit_events / outbox_events / agent_checkpoint identical (1 carried rows)
  8 passed, 0 failed, 1 warned
DR ACCEPTANCE OK — the backup restores the installation, not just a loadable schema.
```

#### Adjudication — bu bir DR kusuru değil, eşzamanlı-yazıcı artefaktıdır

CLAUDE.md kuralı gereği bulgu **ampirik olarak** doğrulandı, kabul edilmedi:

1. **Sapma monotonik büyüyor.** Aynı canlı `entropia` DB'sinde `audit_events`:
   dump anında **1030** → dr karşılaştırma anında **1032** → sonraki ölçümde **1036**.
   Sabit bir bozulma büyümez.
2. **Sapan tek tablo `audit_events`.** Diğer **102** public tablo hem sayı hem küme olarak
   eşleşti ([4]/[5]), 10 immutable-evidence projeksiyonu ([6]) ve 56 nesnenin
   path/size/md5'i ([8]) birebir aynı çıktı. Bozuk bir dump seçici davranmaz.
3. **Fazla satırlar yedekten SONRA yazılmış.** dr yedeği 18:18:20Z'de alındı; sonrasında
   yazılan altı satırın hepsi `backtest.run_admission_rejected`, aktör `user_1`,
   zaman damgaları 18:19:22Z – 18:23:00Z.
4. **Belirleyici test.** Yazıcı 18:23:00Z'de sustu; 19:04:46Z'de alınan yedekle koşulan
   ikinci tur **8 passed / 0 failed** verdi.

Yazıcı, paylaşılan `entropia` veritabanına yazan **paralel bir worktree/test oturumudur** —
CLAUDE.md'nin adıyla uyardığı ortam tuzağı (*"paralel worktree oturumları aynı anda
koşuyor — `TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan"*).

> **Bu bir harness kusuru mu?** Hayır — `dr-acceptance.sh` doğru davrandı: donmuş bir
> anlık görüntüyü hareket eden bir kaynakla karşılaştırdı ve farkı bildirdi. Ama kayda
> değer bir **operasyonel sınır**: harness canlı, yazılmaya devam eden bir veritabanına
> karşı koşturulduğunda yanlış-kırmızı verebilir. CI'da izole bir kaynak DB'ye karşı
> koşturulmalıdır.

#### Kapsam uyarısı — [6] ve [7] az şey kanıtladı

Her iki koşuda da `WARN [6] only 1 evidence table(s) actually held rows`. On immutable
projeksiyondan dokuzu **her iki tarafta da boştu** (`EMPTY == EMPTY`), yani hash korunumu
hakkında neredeyse hiçbir şey kanıtlanmadı. `outbox_events` ve `agent_checkpoint` de sıfır
satırdı. Kapsam tabanları (`DR_MIN_EVIDENCE_TABLES`, `DR_REQUIRE_APPEND_ONLY`,
`DR_REQUIRE_OBJECTS`, `DR_MIN_OBJECTS`) bu koşularda **varsayılan OFF**'tur; bu turlar
CI'nın taban kapılarını değil, yalnız geliştirici modunu temsil eder.

Gerçekten kanıtlanan tek şey nesne düzlemidir: **56 nesne**, dört anahtar öneki
(`create-package/baseline` 4, `market/processed` 10, `market/raw` 7, `signals/source` 35),
md5 düzeyinde birebir.

## (a)–(e) semantiği nerede kanıtlanıyor — işaretçiler, bu dalgada KOŞULMADI

Adlandırılan harness bu akışları içermiyor; boşluğun "kanıt hiç yok" mu yoksa "kanıt başka
katmanda" mı olduğunu ayırt etmek için aşağıdaki işaretçiler çıkarıldı. **Bunlar bu kanıt
dalgasında koşturulmamıştır** — statik kaynak taramasıyla bulunmuş, sonuçları
doğrulanmamış işaretçilerdir. Hiçbiri P6 için `PASS` sayılamaz.

| P6 iddiası | Kapsayan görünen test / kaynak |
|---|---|
| (a) yalnız SUCCEEDED Run Result üretir | `tests/integration/test_e2e_pipeline.py::test_failed_run_yields_no_result_and_no_history` · `test_portfolio_simulation_mode.py::test_a_failed_run_produces_no_result_to_label` · `test_backtest_run_cancellation.py::test_cancelling_a_queued_run_is_terminal_and_produces_no_result` |
| (b) Library validation | `tests/integration/test_library_validation_run.py`, `test_library_validation_run_route.py`, `test_library_approval.py` |
| (c) ESP lifecycle + export | `tests/integration/test_esp_lifecycle_resolution.py`, `test_esp_export_contract_v2.py`, `test_library_export.py` |
| (d) Agent ≠ human account/session | `tests/integration/test_provision_concurrency.py::test_the_agent_principal_is_not_the_agent_runtime` · `test_mainboard_authz.py::test_agent_cannot_{attach,revise,soft_delete}_human_work_object` · `test_e2e_agent_loop.py::test_agent_cannot_run_backtest_on_human_composition` |
| (d) Lab Assistant ≠ Alpha Agent | `src/entropia/application/commands/lab_message.py` (Lab Assistant tartışma yüzeyi) vs `domain/agent_lab/enums.py::ALPHA_AGENT_ID` + `agent_runtime` singleton'ı |
| (e) Trash soft-delete → restore → purge | `tests/integration/test_trash_page.py`, `test_trash_restore_conflict.py`, `test_trash_agent_artifact.py` |
| (e) purge 202 gövdesi İKİ anahtar | `tests/contract/test_openapi_contract.py::test_purge_202_publishes_both_state_field_names` |

> **Dürüst kayıt.** Bu tabloyu doğrulamak için `entropia_p6_e2e` izole veritabanında bir
> destekleyici pytest dalgası **başlatıldı** ama maliyet sınırı nedeniyle **tamamlanmadan
> sonlandırıldı** (kesildiği anda 44 passed / 0 failed). Yarım bir koşu kanıt değildir; bu
> yüzden çıktısı bu kayda dahil EDİLMEMİŞTİR ve yukarıdaki tablo bir iddia değil, bir sonraki
> dalga için **koşulacaklar listesi** olarak okunmalıdır.

## Üretilen kanıt dosyaları

| Dosya | İçerik |
|---|---|
| `p6_f1_backup.txt` | `backup.sh` tam çıktısı + exit code |
| `p6_f2_restore.txt` | `restore.sh` tam çıktısı + exit code |
| `p6_f3_backup_verify.txt` | `backup-verify.sh` tam çıktısı + exit code |
| `p6_f4_dr_acceptance.txt` | `dr-acceptance.sh` 1. koşu (FAILED, exit 1) |
| `p6_f4b_dr_acceptance_rerun.txt` | `dr-acceptance.sh` 2. koşu (OK, exit 0) |
| `p6_concurrency_adjudication.txt` | `audit_events` monotonik büyüme + yedek-sonrası satırların dökümü |
| `p6_acceptance_sh_attempt.txt` | `acceptance.sh` denemesi — asılı kaldı, exit 124 |
| `p6_e2e_acceptance_sh_attempt.txt` | `e2e-acceptance.sh all` denemesi — asılı kaldı, exit 124 |

## Dürüst sınırlar

1. **(a)–(e) koşulmadı.** Adlandırılan iki script bu akışları uygulamıyor. Hiçbir belge
   bu beş akışı P6 kapsamında `PASS` gösteremez.
2. **Uygulama stack'i hiç ayağa kalkmadı.** API:8000 ve web:5173 kapalıydı; OrbStack VM
   takılıydı ve insan kararıyla yeniden başlatılmadı. `scripts/acceptance.sh` çağrıldı ve
   **exit 124** ile asılı kaldı — kapı hiç değerlendirilmedi.
3. **`e2e-acceptance.sh` de çağrıldı ve exit 124 ile asılı kaldı** (tek satır çıktı yok).
   Yani §9.4/§9.5/§9.6 auth akışları için de bu dalgada kanıt YOKTUR.
4. **DR kanıtı `0039` başında alındı**, repo başı `0043`. `0040`–`0043` şeması round-trip
   edilmedi.
5. **[6]/[7] kapsamı zayıftır** (bkz. §Kapsam uyarısı) — 10 projeksiyondan 9'u boş, iki
   append-only düzlem sıfır satır. DR turu "hash korunur" iddiasını taşımaz.
6. **`dropdb` bu host'ta takılıyor** — `backup-verify.sh`'in temizlik adımını ve dalga
   sonu temizliğini kilitledi. `entropia_p6_e2e` ve `entropia_p6_restore_scratch` scratch
   veritabanları bu yüzden **düşürülemedi ve makinede duruyor**; ikisi de bu dalgaya aittir,
   canlı veri değildir. Kayda geçti, düzeltilmedi.
7. **Bu dalga canlı veriye yazmadı.** Tüm restore hedefleri scratch DB / scratch bucket'tı;
   canlı `entropia` DB'si ve `entropia-artifacts` bucket'ı yalnız okundu.
8. **Destekleyici pytest dalgası yarıda kesildi** ve kayda dahil edilmedi (§işaretçiler).
   (a)–(e) semantiği bu dalgada **hiçbir katmanda** doğrulanmış değildir.
