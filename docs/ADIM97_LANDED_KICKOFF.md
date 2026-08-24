<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM99_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 97 LANDED — kabul borcu batch 18 (doc 10 backend) · sıradaki slice için kickoff

**Taban:** main `fb3d771`. **Ürün kodu DEĞİŞMEDİ.**

---

## 1. Nerede duruyoruz

`RF-07` ve `RF-12` kapandı (ikisinde de son açık clause) → ikisi `covered`, ikisinin
`debt_class` **kaldırıldı**.

| | önce | sonra |
|---|---|---|
| `status.partial` | 73 | **71** |
| `status.uncovered` | 7 | 7 (değişmedi) |
| `debt_class.B` | 41 | **39** |
| açık borç | 80 | **78** (A=1 · B=39 · C=6 · D=32) |
| clause `covered` | 1046 | **1048** |

`total_criteria` **383** (TABAN, asla düşmez). **Blocker DEĞİŞMEDİ: 1 (A-08), BLOCKED.**

---

## 2. Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- **`_strategy_payload(..., rationale_family_id: str | None = "rf_1")`** ve
  **`_ready_composition(..., rationale_family_id=...)`**
  (`backend/tests/integration/test_backtest_persistence.py`) — **YENİ parametre.**
  `None` anahtarı **tamamen atar** (`null` yazmaz), çünkü `create_work_object` payload'u
  **birebir** saklar ve StrategyConfig doğrulaması yapmaz. *Bir alanı EKSİK bırakılmış bir
  Strategy'ye ihtiyacı olan her test bu deseni kullanabilir.* Varsayılan mevcut ~30 çağıranı
  bayt bayt aynı bırakır (ölçüldü: dosyanın tamamı yeşil).
- **`_count(session, model)`** — hem `test_backtest_persistence.py` hem
  `test_rationale_persistence.py` içinde, aynı imza.
- Yeni testler: `test_duplicate_active_name_writes_no_root_or_revision` (RF-07.c2) ·
  `test_family_less_strategy_blocks_run_admission_and_leaves_nothing_behind` (RF-12.c3).

---

## 3. Ürün tarafında ölçülen ve YAZILI bırakılan gerçekler

- **`create_work_object` payload'u DOĞRULAMAZ** — StrategyConfig ancak Ready Check'te parse
  edilir. Bu yüzden "geçersiz config'li kayıtlı revizyon" senaryoları **kurulabilir**.
- **`_check_name_available` `_op`'un İLK satırıdır** (`commands/rationale.py::create_family`),
  yani uniqueness bir **pre-insert** kapısıdır. `RF-07.c2` tam olarak bunu gözlenebilir yapar.
- **`request_backtest_run`'ın readiness kapısı manifest/run/job yazımından ÖNCEDİR**
  (`commands/backtest_run.py`, `blocker_count > 0` → `_readiness_blocked`).
- **`AppError.__init__` `remediation`/`suggested_action`'ı sınıf varsayılanından alır**; çıplak
  bir `raise` bunları `None` bırakır. Aynı dosyada **yirmi** sınıf `remediation` bildiriyor.

---

## 4. Sıradaki iş için işaretler

**HAT A (kabul borcu).** Doc 03 · 07 · 18 kapalı; doc 17 ve doc 10'un **backend** borcu bitti.
Bu freeze'de ölçülen kalın belgeler (**GÜVENME, yeniden ölç** — `--report` otoritedir):
doc 05 (5) · doc 12 (4) · doc 09 (3) · doc 06 (3) · doc 14 (3) · doc 21 (3) · doc 01 (3).
**doc 02'nin backend borcu #804 ile bitti** (ADIM 94).

> **UYARI — doc 12'nin dördü de KAYITLI BULGU** (`RD-01.c4`, `RD-05.c5`, `RD-12.c4`,
> `RD-13.c4`): dördü de sınıf-D şeklinde ve hiçbiri testle kapanmaz. Parti seçmeden önce
> **defterin `notes` alanını oku** — kalın görünen bir belge tamamen bulgulardan oluşabilir.

**En ucuz tek satır:** **`RF-18.c1`** (doc 10 **frontend**) — staged reassignment'larla
remount/refresh sonrası "1 pending change(s)" staging'inin gitmiş olması. Doc 10'u bitirir.

**HAT B (mühendislik).** Bu oturumda **hiç ellenmedi**: `C4` hattında **#805** açıktı.

## 6. NUMARA — bu slice'ın ikinci kez ödediği bedel

Bu kayıt **`ADIM 94` yazıldı, `ADIM 97`'e taşındı**: PR açıkken **#804** indi ve
**`ADIM 94` adını aldı** (kendi `docs/ADIM94_LANDED_KICKOFF.md` dosyasıyla birlikte).
**Parti numarası taşınmadı** — #804 batch 16'ydı, bu batch 18. İki numara **bağımsız
taşınır**; kapanışta ikisini de ayrı ayrı doğrula.

**Aynı merge kabul defterini de bayatlattı:** dal `3994725`'e karşı **77/45** dondurulmuştu,
`d47c5ba`'ya taşınıp `--ratchet` **yeniden koşuldu** → **73/41**. İki freeze'i elle çıkarmak
yanlış tavan üretirdi.

---

## 5. Dürüst sınırlar

- Postgres bu container'da **ayakta ve migrate edilmiş** → iki case + üç negatif kontrol
  **gerçekten koştu**.
- **Frontend'e sıfır satır** dokunuldu → frontend kapıları koşulmadı; otorite CI.
- **e2e / `@a11y`** suite'lerine hiçbir assertion yazılmadı.
- **BİR YENİ BULGU** (`RF-08.c2`) kaydedildi, **üzerine gidilmedi**, **yeniden
  sınıflandırılmadı**.

---

## Paste-ready resume prompt (temiz oturuma yapıştır)

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, tavanı ya da PR durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  TAVANI DOSYADAN OKU: docs/audit/acceptance_coverage_baseline.json .ceilings
  (bu satır yazılırken 71 partial / 7 uncovered / A1 B39 C6 D32, total 383 — BAYAT olabilir)

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA — ve DOSYA YOLUNA bak, başlığa değil:
  list_pull_requests(state=open) → her açık PR'ın EKLEYECEĞİ docs/ADIM<n>_LANDED_KICKOFF.md
  yolunu çıkar. Çakışma başlıkta değil DOSYA YOLUNDADIR ve check_classification onu görmez.
  Kabul defteri SERİ bir kaynaktır: paralel bir batch varsa ikinci inen REBASE edip tavanı
  YENİDEN ÖLÇER. İki freeze'i elle ÇIKARMA — batch 15'te partial tesadüfen aynı çıkmış,
  B ve uncovered çıkmamıştı.

HAT A — kabul borcu batch 19. Doc 03/07/18 kapalı; doc 02, doc 17 ve doc 10'un BACKEND borcu bitti.
  EN UCUZ TEK SATIR: RF-18.c1 (doc 10 FRONTEND) — staged reassignment'larla remount sonrası
  "1 pending change(s)" staging'i gitmiş olmalı; doc 10'u bitirir.
  UYARI: doc 12'nin dört sınıf-B satırının DÖRDÜ DE kayıtlı bulgudur (sınıf-D şeklinde).
  Parti seçmeden önce defterin notes alanını OKU.
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report

HAT B — mühendislik: C4 / E5. #805 açıktı (containment gate düzeltmesi). ÖLÇ, sonra karar ver.

HER CLAUSE İÇİN PAZARLIKSIZ:
  1. Mevcut testler bu kusur altında YEŞİL mi kalıyor? Kalıyorsa yeni assertion BAŞKA eksende.
  2. "raise ediyor" ile "YAZMADAN raise ediyor" AYNI ŞEY DEĞİLDİR → satırları SAY ve geri oku.
  3. Refüz testinde ROLLBACK YAPMA: rollback post-insert bir guard'ın yazdığını da atar ve
     test vacuous geçer. flush() + expire_all() ile veritabanından oku.
  4. Bir HARNESS parametresi eklediysen, red'in SENİN değişikliğine atfedilemeyeceğini ayrı
     bir negatif kontrolle göster (davranışı geri koy → assertion yeşile dönmeli).
  5. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü OKU. Eski bir testin yeşil kalması
     kusur değil KANITTIR.
  6. Koşamadığın suite'e (e2e / @a11y) assertion YAZMA.
  7. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

ORTAM: Postgres bu container'da kuruldu ve MİGRATE EDİLDİ. Yeniden kaldırmak için:
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/entropia_pgdata \
      -l /tmp/pg.log -o '-p 5432 -k /tmp' -w start"
  Taze kurulum gerekiyorsa: initdb -U entropia --auth=trust --locale=C.UTF-8 -E UTF8,
  sonra CREATE DATABASE entropia ve DATABASE_URL=... uv run alembic upgrade head.
  MİGRASYONU ATLAMA: integration conftest şemayı create_all ile kendi kurar ama contract
  testleri MİGRATE EDİLMİŞ DATABASE_URL veritabanını kullanır → ~40 sahte hata
  ('relation "human_users" does not exist'). Frontend'de node_modules YOK → npm ci.
  Alt küme koşarken --no-cov. `pytest … | tail` KULLANMA: exit code tail'in olur.
  Test eklediysen repository_facts'i YENİDEN ÜRET; defter değiştiyse --write-ledger +
  --write-report koş.

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
