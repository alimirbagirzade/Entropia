<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 22 landed — install / upgrade / restore kabul zinciri (kurulum-alanı devri)

> **Bu belge SIRADAKİ SLICE'IN tohumu DEĞİLDİR.** Sıradaki iş **PR B** (`ItemParticipant`
> adaptörü + worker call site) ve onun devri `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`'dir —
> oraya git. Buradaki belge **kurulum/upgrade/DR alanının** devri: ADIM 22'nin ne bıraktığı,
> hangi sembollerin yeniden kullanılacağı ve bu alanda kalan açık işler. İki belge rekabet
> etmez; ayrı alanları taşırlar.
>
> **Tam tarihsel kayıt:** `docs/PROJECT_HISTORY.md` §"ADIM 22 — install/upgrade/restore
> acceptance (PR #594, #601)".

---

## 1. Nerede duruyoruz

**HEAD `5e457e8`** · **alembic head `0043_i08_registry_strategy_fks`**.

ADIM 22 öncesinde kurulum zincirinin **harness'ları vardı ama kapısı yoktu**:
`scripts/e2e-acceptance.sh`, `backup.sh`, `restore.sh`, `backup-verify.sh` geliştirici
komutlarıydı ve **hiçbir workflow onları koşmuyordu** (denetim **H-07**). Artık dört job'lık bir
workflow var ve maliyete göre bölünmüş:

| Cadence | Job |
|---|---|
| her PR | `migration-acceptance` · `fresh-install` |
| nightly (03:17 UTC) / manual | `legacy-upgrade` · `disaster-recovery` |

**Kanıt:** Actions run **31038908690** — dördü de `success`. **Nüans:** o koşu `main`'de değil,
`fix/backup-object-storage-on-linux`@`84d1a5e`'de `workflow_dispatch` ile koştu. Heavy çift
push/PR'da koşmaz, yani `main`'e karşı ilk yürütmesi nightly cron'dur.

---

## 2. Reuse anchor'ları — tam sembol adlarıyla

| ne | nerede |
|---|---|
| provisioning kilidi (transaction-scoped advisory lock) | `apps/seed.py::lock_provisioning` |
| kilit anahtarı / zaman aşımı | `apps/seed.py::PROVISION_LOCK_KEY` (`220_000`) · `PROVISION_LOCK_TIMEOUT_MS` |
| kilit zaman aşımı hatası | `apps/seed.py::ProvisioningLockTimeout` |
| **çağrılabilir** provisioning (session çağıranın) | `apps/seed.py::provision(session, log)` |
| session sahibi CLI girişi | `apps/seed.py::_seed()` |
| migration/upgrade kapısı | `scripts/migration-acceptance.sh` · `make migration-accept` |
| DR kapısı | `scripts/dr-acceptance.sh` · `make dr-accept` |
| kurulum workflow'u (4 job) | `.github/workflows/install-acceptance.yml` |
| düzlem sağlığı iddiası (artık `worker-agent-executor` dahil) | `scripts/e2e-acceptance.sh::assert_planes_healthy` |
| eşzamanlılık testleri | `backend/tests/integration/test_provision_concurrency.py::test_concurrent_provisioning_runs_all_succeed` · `::test_concurrency_does_not_duplicate_an_unguarded_seed_block` |
| object storage yazıcıları (dört prefix) | `infrastructure/s3/datasets.py::put_raw_bytes` · `put_processed_parquet` · `put_source_asset_bytes` · `put_baseline_bytes` |

**REUSE listesi — yeni bir şey yazmadan önce:**
- Eşzamanlılık koruması gerekiyorsa `pg_advisory_xact_lock` deyimi zaten **üç** yerde:
  `seed.lock_provisioning`, `repositories/identity.py::lock_admin_count`,
  `repositories/manual.py::lock_stream`. **Dördüncü bir mekanizma icat etme.**
- Yeni bir acceptance iddiası `scripts/*-acceptance.sh`'in `ok` / `bad` / `warn` / `info`
  gramerini kullanır; yeni bir çıktı biçimi uydurma.
- Uzun ömürlü bir plane ekliyorsan loop ömrü desenini `apps/scheduler/__main__.py::run`'dan
  kopyala (tek `asyncio.run`, `asyncio.Event` stop flag, `finally` içinde engine dispose) —
  `asyncio.run`'ı tick/mesaj başına çağırma. Bu kusur üç yerde ayrı ayrı düzeltildi
  (#593 scheduler, #600 coordinator, #597 worker aktörleri); dördüncüsünü yazma.

---

## 3. Bu alanda ölçülen, güvenilebilecek gerçekler

- **Provisioning eşzamanlı-güvenli değildi ve bu üretildi:** taze migrate edilmiş bir DB'de
  3 paralel koşunun **2'si** `principals_pkey` ile exit 1.
- **Sessiz yarısı daha kötüydü:** unique constraint'i olmayan guard'lar hata vermeden duplike
  commit ediyordu — 3 eşzamanlı koşu **6 kanonik yerine 18** rationale family üretiyor.
  `test_concurrency_does_not_duplicate_an_unguarded_seed_block` bu sayıyı pinliyor.
- **`lock_timeout` `pg_advisory_xact_lock`'a uygulanıyor** — PostgreSQL 16'da ampirik
  doğrulandı (varsayım değil).
- **`minio/mc` `ENTRYPOINT ["mc"]` bildiriyor**, yani `docker run minio/mc sh -c '...'`
  argümanları mc parametresi olarak ayrıştırılır. `--entrypoint sh` olmadan, host'unda `mc`
  olmayan her makinede object storage **sessizce yedeklenmiyordu** (#601).
- **DR kapsaması sığdı:** run 31038908690'ın kendi transcript'i
  `[7] all three append-only planes were EMPTY` ve `[8] 1 objects` bastı.

---

## 4. Bu alanda açık kalanlar

| # | Ne | Durum |
|---|---|---|
| **PR #610** | DR kanıt derinliği: yedeklemeden önce gerçek iş akışı (`scripts/dr-workload.sh`) + kapsama tabanları (`DR_MIN_EVIDENCE_TABLES` / `DR_REQUIRE_APPEND_ONLY` / `DR_MIN_OBJECTS`) | **AÇIK** — CI'da doğrulandı (run 31050210323, 4/4 success), merge bekliyor |
| `agent_checkpoint` | DR [7]'de hâlâ kapsanmıyor — bir Agent tool çağrısı gerektiriyor | Açık; transcript her koşuda adını basıyor |
| `market/raw` · `create-package/baseline` | DR [8]'de hâlâ kapsanmayan iki key prefix'i | Açık; aynı şekilde adlandırılıyor |
| index adları | `alembic check` index-*adı* sapması + bir server default bildiriyor; **kolon** paritesi temiz ve gate'li | Bilerek kapsam dışı, ayrı temizlik |
| `metadata.create_all` | Integration suite şemayı hâlâ böyle kuruyor → migration-inserted satırlar pytest'te yok | `migration-acceptance.sh` [4] telafi ediyor |
| PITR · off-site replikasyon · zamanlanmış backup | `docs/BACKUP_DR.md` "Scope" | **V1 DIŞI (bilerek)** |

**Memory checkpoint yazılmadı.** Kapanış ritüeli hem ecc knowledge graph hem claude-mem
istiyor; **ADIM 22'yi kaydeden oturumda ikisi de erişilebilir değildi** (`~/.claude.json`
`claude-memory-kit` ve `memory-command` tanımlıyor ama hiçbir memory-yazma aracı açığa
çıkmıyordu; `codebase-memory-mcp` kaynak-kod grafiğidir, entity/observation deposu değil).
Kalıcı kayıt `PROJECT_HISTORY.md` + `STAGE2_HANDOFF.md` + bu belgededir; checkpoint bu
sunucuların bağlı olduğu interaktif bir oturumdan yazılmalı.

---

## 5. Yöntem (bu alanda işleyen)

- **Kurulum zinciri değiştiyse:** `make migration-accept` (~30 sn, Docker'sız), sonra gerekiyorsa
  `gh workflow run "Install acceptance" --ref <branch> -f run_heavy=true`. Heavy job'lar PR'da
  **koşmaz** — tetiklemezsen doğrulanmamış demektir.
- **Bir eşiği/uyarıyı değiştirdiysen mutation-check ZORUNLU:** eşiği gerçeğin üstüne koy, testin
  gerçekten kırmızıya döndüğünü göster; sonra varsayılan-kapalı hâlin hâlâ yeşil olduğunu
  göster. Ateşlenemeyen bir uyarı uyarı değildir.
- **Docker portları:** paralel worktree'ler 5432/8000/9000/6379'u tutabilir. İzole stack için
  `ENTROPIA_ENV_FILE` + `API_HOST_PORT` / `PG_HOST_PORT` / `MINIO_HOST_PORT` /
  `REDIS_HOST_PORT` ver ve `docker compose -p <proje>` kullan. Bir başka worktree'nin
  stack'i 19100/19101'i de tutabiliyor — çakışırsa port seç, `down -v` **etme**.
- **Code-review CRITICAL/HIGH bulgularını ampirik doğrula** — sıklıkla yanlışlar.

---

## 6. Paste-ready resume prompt (bu alan için)

> Sıradaki **ürün** slice'ı için bu prompt'u KULLANMA —
> `docs/ADIM16_STEPPER_LANDED_KICKOFF.md` §6'yı kullan. Aşağıdaki yalnızca kurulum/DR
> alanına dönüldüğünde geçerlidir.

```text
ENTROPIA V18 — kurulum/DR alanı: PR #610 sonrası kalan kapsama boşlukları

ROL: Entropia V18 üzerinde çalışan kıdemli principal engineer.
Dil: Türkçe. Teknik tanımlayıcılar İngilizce kalır.

ZORUNLU BAŞLANGIÇ
1. `git fetch --all --prune`; `git status --short` — temiz değilse DUR.
2. Current main SHA + açık PR/issue snapshot'ı al. Aşağıdaki HİÇBİR iddiayı
   doğrulamadan kabul etme; hepsi stale-by-default. Özellikle: PR #610 merge
   edildi mi? Edildiyse aşağıdaki "açık" kalemler değişmiştir.
3. Oku: docs/STAGE23_KICKOFF.md → docs/PROJECT_HISTORY.md §"ADIM 22" →
   docs/INSTALL_ACCEPTANCE.md → docs/BACKUP_DR.md.

İŞ (sırayla, ayrı PR)
A. DR [7]'de `agent_checkpoint` hâlâ kapsanmıyor. Bir Agent tool çağrısı
   üreten en KÜÇÜK gerçek iş akışını bul ve `scripts/dr-workload.sh`'e ekle.
   Sahte fixture üretme — üretilen her satırın ürün anlamı olmalı.
B. DR [8]'de `market/raw` ve `create-package/baseline` prefix'leri kapsanmıyor.
   Aynı kural: gerçek upload yolu, uydurma nesne değil.
C. Kapsadıktan sonra `DR_MIN_OBJECTS` / `DR_REQUIRE_APPEND_ONLY` tabanlarını
   yeni gerçekliğe göre YÜKSELT. Bir tabanı yeşil kalsın diye ASLA indirme.

TAVİZ VERİLEMEZ
- Her eşik değişikliği MUTATION-CHECK ister: eşiği gerçeğin üstüne koy → kırmızı
  olduğunu göster; varsayılan-kapalı hâl → hâlâ yeşil olduğunu göster.
- Kanıt şişirme: bir iddia kanıttan büyükse iddiayı küçült.
- Server-side policy, ownership, OCC, idempotency, audit ve lifecycle korunur.
- Başarısız test varken "Complete" yazma. PR merge etme, issue kapatma.

DOĞRULAMA
`make migration-accept` (Docker'sız) + heavy job'lar için
`gh workflow run "Install acceptance" --ref <branch> -f run_heavy=true`.
Heavy job'lar PR'da KOŞMAZ — tetiklemezsen doğrulanmamıştır.
Backend'e dokunduysan: cd backend && uv run ruff check . && uv run ruff format
--check . && uv run mypy src && uv run pytest -q (tam suite TEK çağrıda, ortada
öldürme, `| tail` KULLANMA, çıktıyı dosyaya yaz ve `$?`'i AYRI oku).

RAPOR
Base SHA, branch, commit, PR, changed behavior, unchanged boundaries, targeted
tests, mutation-check sonucu, full-suite exit code, kalan risk, sonraki tek adım.
```
