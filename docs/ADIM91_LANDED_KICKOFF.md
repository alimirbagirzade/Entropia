<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** ADIM 92 ile `historical`a demote
> edildi; canlı kickoff `docs/ADIM92_LANDED_KICKOFF.md`. Aşağıdaki SHA'lar, tavanlar ve "next"
> maddeleri yazıldıkları anı dondurur — §NUMARA'nın *"#799 `docs/ADIM89_LANDED_KICKOFF.md`
> ekliyor"* ölçümü DAHİL: o ölçüm yazıldığı anda doğruydu, ama bu belge 91 olarak **önce
> inince** 89 numarası `check_classification` için kullanılamaz hâle geldi (kapı canlı
> kickoff'un ağaçtaki EN YÜKSEK numara olmasını ister) ve #799 **92**'ye taşındı.

# ADIM 91 — kabul borcu batch 15 (doc 17 backend) landed

**PR:** `feat/…` → bu dal `claude/entropia-v18-next-slice-5uu06a`.
**Taban:** main `ee5ab38`. **Ürün kodu DEĞİŞMEDİ.**

---

## 1. Nerede duruyoruz

Bu slice doc 17'nin (Arrange Metrics) **dört** sınıf-B kabul kriterini kapattı:
`AM-03`, `AM-05`, `AM-06`, `AM-07`. Dördünde de kapanan clause kriterin **son** açık
clause'uydu → dördü de `covered`, dördünün de `debt_class` **kaldırıldı**.

Tavanlar (ölçüldü, `--ratchet` çıktısından):

| | önce | sonra |
|---|---|---|
| `status.partial` | 83 | **79** |
| `status.uncovered` | 7 | 7 (değişmedi) |
| `debt_class.B` | 51 | **47** |
| açık borç toplamı | 90 | **86** (A=1 · B=47 · C=6 · D=32) |
| clause `covered` | 1034 | **1039** |

`total_criteria` **383** (TABAN, asla düşmez).

**Blocker sayısı DEĞİŞMEDİ: 1 (yalnız A-08), verdict BLOCKED.**

---

## 2. Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

Hepsi `backend/tests/integration/test_arrange_metrics.py` içinde:

- `_seed_run_and_job(session, *, workspace_id, result_id)` — **YENİ**. SUCCEEDED bir
  `BacktestRun` + onun `Job` satırını seed eder. *"Bir işlem run oluşturmuyor"* iddiasını
  **boş olmayan** bir tabloya karşı ölçmek isteyen her test bunu kullanabilir.
- `_run_and_job_ids(session) -> tuple[list[str], list[str]]` — **YENİ**. `backtest_run` ve
  `jobs` tablolarının id listeleri (sıralı). Sayı değil **kimlik** döner: bir satırın
  eklenip başkasının silinmesi de yakalanır.
- `_seed_result(session, *, workspace_id, result_id, owner, ledger_rows=0)` — mevcut,
  **değiştirilmedi**. `BacktestResult` + dokuz `MetricValueRow` (biri **NULL**) +
  `ResultManifestSnapshot` + ledger/diagnostic/signal satırları.
- `_seed_registry` / `_seed_principals` / `_workspace` — mevcut, değiştirilmedi.

Yeni testler:

| Test | Kapattığı |
|---|---|
| `test_profile_apply_creates_no_run_and_leaves_manifest_untouched` | `AM-03.c2` + `.c3` |
| `test_empty_selection_refusal_leaves_canonical_revision_in_place` | `AM-05.c2` |
| `test_lock_unlock_cycle_leaves_result_values_unchanged` | `AM-06.c3` |
| `test_foreign_unlock_denied_and_the_lock_preference_grants_nothing` | `AM-07.c2` |

---

## 3. Ürün tarafında ölçülen ve YAZILI bırakılan gerçekler

- `create_metric_profile_revision` **Apply / Lock / Unlock için tek komuttur**; ayrım
  `is_locked` + seçimdedir (`domain/metric_profile/profile.py::transition_reason`).
- **`normalize_selection` `run_idempotent` gövdesinin DIŞINDA koşar** (saf girdi doğrulaması),
  bu yüzden boş seçim hiçbir hedef çözümlemesine ulaşmadan reddedilir. `AM-05.c2`'nin
  kapanması tam olarak bunun **gözlenebilir** hâle getirilmesidir.
- **`ensure_can_edit` kilit kontrolünden ÖNCE koşar** (`_resolve_existing` → sonra
  `_enforce_lock_precondition`), yani kilit hiçbir zaman bir yetki kaynağı değildir.
  `AM-07.c2` bunu artık **sürüyor**.
- **Saf unlock** = `is_locked` false'a döner **ve seçim AYNI kalır**; başka her şey kilitliyken
  `METRIC_PROFILE_LOCKED`.
- Sistem varsayılanına ikinci bir Apply **stale**'dir (kişisel profil varsa) — bu yüzden
  kilit/unlock testleri ilk revizyondan sonra **kişisel `profile_id`'yi** hedeflemelidir.

---

## 4. Sıradaki iş için işaretler

**HAT A (kabul borcu).** Doc 03 · 07 · 18 kapalı. Bu slice'tan sonra doc 17'de **testle
kapanacak sınıf-B satır kalmadı**. Kalan kalın belgeler bu freeze'de şöyle ölçüldü
(**GÜVENME, yeniden ölç** — `--report` otoritedir): doc 02 (8 partial, 2 uncovered) ·
doc 05 (6 partial, **#797 `TL-18`'i kapattı**) · doc 10 (6 partial) ·
doc 12 (6 partial) · doc 06 (5 partial) · doc 09 (5 partial) · doc 21 (5 partial) ·
doc 22 (5 partial, çoğu `deliberate_future_dev` komşusu).

**HAT B (mühendislik).** `C4` / `E5` bu oturumda **hiç ellenmedi**: **#799**, **#800** ve
**#801** aynı işi sürerken dördüncü bir yazım çöp olurdu. Başlamadan önce hangisinin indiğini
ölç.

**NUMARA — bu slice'ın en pahalı dersi.** Bu kayıt **ADIM 89 yazıldı ve 91'e taşındı**: #799
`docs/ADIM89_LANDED_KICKOFF.md`, #802 ise `docs/ADIM90_LANDED_KICKOFF.md` **ekliyor**, ikisi de
açık. **Çakışma başlıkta değil DOSYA YOLUNDADIR** ve `check_classification` bunu **asla**
yakalayamaz — çakışan dalların her biri kendi içinde tutarlıdır. Numaranı seçmeden önce her
açık PR'ın **ekleyeceği** `docs/ADIM<n>_LANDED_KICKOFF.md` yolunu listele.

---

## 5. Dürüst sınırlar

- Bu container'a **PostgreSQL 16 kuruldu** (`initdb` + `pg_ctl` + **`alembic upgrade head`**);
  dört case ve **beş** negatif kontrolün hepsi gerçekten koştu
  (`test_arrange_metrics.py` **17 → 21 passed**).
- **Migration'ı atlamak yerelde ~40 sahte hata üretir** — integration conftest şemayı
  `create_all` ile kendi kurar, ama contract testleri **migrate edilmiş** `DATABASE_URL`
  veritabanını kullanır (`relation "human_users" does not exist`). Atıf **kanıtla** yapıldı:
  dalın hiç dokunmadığı bir contract dosyası ayrı bir DB'de aynı hatayı verdi.
- **Frontend'e sıfır satır** dokunuldu → frontend kapıları koşulmadı; otorite CI.
- **e2e / `@a11y`** suite'lerine hiçbir assertion yazılmadı.
- **Yeni bulgu YOK**; hiçbir kriter yeniden sınıflandırılmadı.

---

## Paste-ready resume prompt (temiz oturuma yapıştır)

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, tavanı ya da PR durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff'u BULDUR (ilk satırda ara, gövdede DEĞİL):
    for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do
      head -1 "$f" | grep -q 'doc-status: current' && echo "$f"
    done
  TAVANI DOSYADAN OKU: docs/audit/acceptance_coverage_baseline.json .ceilings
  (bu satır yazılırken 79 partial / 7 uncovered / A1 B47 C6 D32, total 383 — BAYAT olabilir)

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA:
  mcp__github__list_pull_requests(state=open) → dokunacağın dosyaya dokunan açık PR var mı?
  Kabul defteri SERİ bir kaynaktır — paralel bir batch varsa ikinci inen rebase edip
  YENİDEN DONDURUR; iki freeze'in farkından aritmetikle sayı TÜRETME.

HAT A — kabul borcu batch 16. Doc 03, 07, 18 BİTTİ; doc 17'de testle kapanacak sınıf-B
  satır KALMADI. Kalan kalın belgeler (ÖLÇEREK doğrula): doc 02 · doc 05 · doc 10 · doc 12.
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report

HAT B — mühendislik: C4 / E5 (worker dalı). 2026-08-19'da ÜÇ açık PR birden sürüyordu
  (#799, #800, #801). Başlamadan önce hangisinin indiğini ÖLÇ; birden fazlası hâlâ açıksa
  bu hat KAPALIDIR, HAT A'ya geç.

HER CLAUSE İÇİN PAZARLIKSIZ:
  1. Mevcut testler bu kusur altında YEŞİL mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı.
  2. İddiayı, karşıtının ÜRETİLEBİLECEĞİ bir dünyada ölç, ve olayın GERÇEKLEŞTİĞİNİ ayrı bir
     assertion ile gözle. ADIM 91: "run oluşmuyor" iddiasını BOŞ bir tabloda ölçmek zayıftır
     (önce bir run + job seed et); "hiçbir şey kıpırdamadı" iddiası, işlemin gerçekten indiği
     ayrıca assert edilmezse hiçbir şey yapmayan bir çağrı için de geçer.
  3. Guard'ı mutasyonun ALTINA taşıyan negatif kontrol istisnayı AYNI ŞEKİLDE fırlatır →
     pytest.raises tek başına bir "durum değişmedi" clause'unu ASLA kapatmaz; satırı
     flush() + expire_all() sonrası VERİTABANINDAN geri oku.
  4. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü OKU. Eski bir testin yeşil kalması
     kusur değil KANITTIR: o test kusurun bulunduğu dalı hiç geçmiyordur.
  5. Koşamadığın bir suite'e (e2e / @a11y) assertion YAZMA.
  6. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

ORTAM: Postgres KURULABİLİR ve bu container'da kuruldu:
  PGDATA=/var/lib/postgresql/entropia_pgdata
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -U entropia --auth=trust \
      --locale=C.UTF-8 -E UTF8"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log \
      -o '-p 5432 -k /tmp' -w start"
  psql -h localhost -U entropia -d postgres -c "CREATE DATABASE entropia"
  (integration conftest <db>_test'i kendisi yaratır). Postgres'siz integration suite SESSİZCE
  skip eder — pg_isready ile ÖLÇ. Frontend'de node_modules YOK → önce `cd frontend && npm ci`.
  Alt küme koşarken --no-cov. `pytest … | tail` KULLANMA: exit code tail'in olur ve 200
  collection error'ü exit 0 gibi gösterir (bu oturumda birinci elden yaşandı).
  Test eklediysen repository_facts'i YENİDEN ÜRET; kabul defterine dokunduysan
  --write-ledger + --write-report koş (traceability raporu --check kapsamında DEĞİL).

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
