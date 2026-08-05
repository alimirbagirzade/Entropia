# ADIM 18 landed — kickoff for **ADIM 18b** (resumable stepper + worker wiring)

> **Bu belgeyi taze bir oturumda ilk okuduğun şey yap.** En altta **paste-ready resume prompt**
> var. Önceki slice'ın (ADIM 19 / PR #581) kapanışında kickoff **üretilmemişti** — bu belge o
> boşluğu da kapatıyor.

---

## Nerede olduğumuz

`origin/main` @ **`b0bb4a0`** üzerine ADIM 18 indi: `domain/backtest/portfolio_engine.py` —
ADR 0002 §8'in **per-tick faz döngüsü**. Migration yok, OpenAPI değişmedi, `ENGINE_VERSION`
değişmedi, **46 golden digest'in hiçbiri oynamadı**. Rollback = commit'i revert et.

**Bu oturumda kapanan iki insan kapısı:**

| Kapı | Karar |
|---|---|
| ADR 0002 `Proposed` idi, §16 onay şart koşuyordu, beş slice onaysız inmişti | **`Accepted` (2026-08-05)**, geriye dönük kapsıyor. **§13 çözülmedi — OD-1…OD-7 hepsi açık.** |
| ADR §12 numaralandırması sevk edilenle uyuşmuyordu | **Amendment**: ADR **§12.1** = numara ↔ PR eşlemesi + eksik kalemin **ADIM 18b** olarak geri planlanması |

> ⚠️ `docs/adr/README.md`: *"ADRs are immutable once **Accepted**"*. ADR 0002 artık Accepted —
> bundan sonra onu **düzenleme**, gereken olursa **ADR 0003** yaz.

---

## ADIM 18'in bıraktığı — tam sembol adlarıyla (REUSE ANCHOR)

| ne | nerede |
|---|---|
| faz döngüsü + bütün sıra değişmezleri | `domain/backtest/portfolio_engine.py::run_portfolio` |
| **doldurulacak protokol** | `portfolio_engine.ItemDriver` — `mandatory(view)` / `propose(view, snapshot)` / `apply(grant, intent, held)` |
| P1/P2/P3 olgu tipleri | `CashEvent` (funding/fee/other_cost) · `FillEvent` · `CloseEvent` (`resulting` = partial exit kalanı) |
| P7 sonucu | `AppliedFill` — **toplam** pozisyon, delta DEĞİL; `commission` pozisyondan ÖNCE bookenir |
| flat'ten açılış | `default_fill` — scale basis'i **uydurmaz**, `ScaleBasisNotSuppliedError` verir |
| çıktı + digest | `PortfolioRun.identity` / `.ticks` / `.equity_points` / `.contribution` · `TickRecord` |
| manifest adaptörü | `portfolio_manifest_for(run, ...)` → `provenance.build_portfolio_manifest` |
| hata zarfı | `PhaseLoopError` + `IncoherentRunInputsError` / `MisdirectedEventError` / `SnapshotLeakError` / `TickOrderError` / `ScaleBasisNotSuppliedError` |
| versiyon | `PHASE_LOOP_VERSION = "phase-loop-v1"` (manifeste **yazılmadı** — ADIM 20) |

Önceki slice'ların anchor'ları değişmedi: `execution/clock.py::iter_ticks`,
`execution/intents.py::form_intents` / `form_mandatory_intent` / `PortfolioSnapshot`,
`execution/portfolio_ledger.py::PortfolioLedger` (`publish_snapshot` / `begin_apply` /
`resolve_capacity` / `commit_tick` / `valuation` / `ledger_for_items`),
`execution/arbitration.py::arbitrate` / `resolve_policy` / `profiles_from_pins`,
`execution/attribution.py::attribute` / `build_contribution_report`,
`execution/provenance.py::build_portfolio_manifest`.

---

## Sıradaki: **ADIM 18b** — iki yarım, bu sırayla

**Bu, ADR'nin hiç yazılmamış ADIM 16'sıdır.** `engine.py:1782` hâlâ monolitik
`for batch in bar_batches:`; worker hâlâ `jobs/backtest_engine.py:298` item döngüsünü koşuyor.

1. **Saf refactor.** Bar-loop gövdesini bir öğeyi verilen `t`'ye ilerletebilen stepper'a çıkar.
   `run_engine` imzasını **ve semantiğini** korur, o stepper üzerinde ince bir sürücü olur
   (ADR §3.2). **Tek kanıt: 46 golden digest'in hiçbiri oynamamalı** — başka assertion'a
   güvenme (ADR R-4).
2. **Wiring.** Stepper üzerinde `ItemDriver`'ı uygula, worker'ın `>1 öğe` yolunu
   `run_portfolio`'ya bağla. **Digest'ler burada oynar:** 9 `portfolio.*` senaryosu tek tek
   gerekçelendirilir; başkası oynarsa regresyondur.

**Wiring'den önce karara bağlanacak üçüncü şey — retention.** Döngü bugün her tick için tam
bir `TickRecord` (snapshot, iki intent kümesi, arbitration raporu, attribution satırı) saklıyor
ve her tick'i attribute ediyor. Contained, *incelenmek için* var olan bir döngü için doğru şekil
— değişmezler o kayıtlara karşı doğrulanıyor — ama bir yıllık 1 dakikalık eksenin istediği şekil
bu değil: ADR §11 peak memory'nin **düşmesini** şart koşuyor ve clock zaten tam bu yüzden
streaming (`timeline_identity` artımlı hesaplanıyor). Üretimden erişilemediği için bugün bir
maliyeti yok; **worker'ı bağlamadan önce uzun bir koşunun ne sakladığına karar ver**, sonra
memory grafiğinde keşfetme. ADIM 18'de bilerek spekülatif bir retention knob'u ile
çözülmedi — worker'ın istediği şekil henüz bilinmiyor.

**ADIM 20 bundan ÖNCE merge edilemez.** Stepper olmadan worker bitmiş koşuları katlıyor, yani
containment'ı kaldırmak ADR §1.2'nin %66 şişirdiği sequential eğriyi kanonik Result olarak
yayımlamak olurdu.

---

## Tuzaklar — üçü de bu slice'ta ısırdı

1. **Containment testleri düz substring arar.** Yeni bir ÜRETİM dosyası eklediğinde, yorumlarında
   bile `execution.<contained_modül>` dotted yazımı geçerse test kırılır. Her yeni üretim
   dosyasından sonra altı containment suite'ini **yeniden koş**.
2. **Aynı bayt uzunluklu mutasyon stale `.pyc` bırakır.** `if extra:` → `if False:` aynı
   uzunlukta; Python bytecode'u geçersizleştirmedi, mutant hiç koşmadı ve test "geçti". Mutasyon
   koşarken `__pycache__`'i sil + `PYTHONDONTWRITEBYTECODE=1`.
3. **pytest exit 4 ≠ exit 1.** Script `--timeout=300` geçiriyordu (bu repoda plugin yok);
   her mutant **kullanım hatasıyla** çıkıyor ve "öldü" sayılıyordu. Sahte 14/14, gerçek 11/14.
   Mutasyon script'in exit code'u **ayırt etmeli**.

Ayrıca: alt küme koşarken `--no-cov` ekle; tam suite'i **tek** pytest çağrısında koş, çıktıyı
dosyaya yaz ve `$?`'i **ayrı** oku; `| tail` kullanma. Worktree'ye özel `TEST_DATABASE_URL`
(`postgresql+asyncpg://`) kullan.

---

## ADIM 20 için hâlâ açık kapılar (hiçbiri bu slice'ta kapanmadı)

- **OD-1…OD-7'nin yedisi de açık.** R-5: her biri manifestte versiyonlu politika olarak kayda
  geçmeden containment kaldırılamaz. Özellikle **OD-2** (stale mark) ve **OD-3** (jointly
  insolvent seçimi) bugün kodda "açık" diye etiketli.
- **R-1** (ADR §10.2 revision pinning drift) — ADIM 20'den önce ayrı dar bir PR.
- **#544 (NET)** · **#559 (DST)** · **#550/#551/#552** · **#556/#557/#558** · **#539** · **#514**.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 18b: resumable stepper + run_portfolio worker wiring

ROL: Entropia V18 üzerinde kıdemli principal engineer. Yeni özellik icat etme; canonical
Production V1 sözleşmesini current origin/main üzerinde kanıtla, yalnız doğrulanmış boşluğu
dar bir PR ile kapat, sistemi geriletme.

OTURUM BAŞLANGICI (zorunlu):
1. git fetch --all --prune; git status --short (temiz değilse DUR, silme/stash yok)
2. main'i origin/main'e sıfırla; SHA + tarih + açık PR/issue snapshotını kaydet
3. ADIM 18 PR'ının main'e MERGE edildiğini DOĞRULA; edilmediyse DUR
4. Oku: docs/ADIM18_LANDED_KICKOFF.md -> docs/STAGE2_HANDOFF.md ->
   docs/adr/0002-unified-clock-portfolio-simulation.md §3.2, §12.1, §14, §16 ->
   docs/PROJECT_HISTORY.md §ADIM 18 -> docs/CODEMAPS/BACKEND_LAYERS.md
5. Eski README/CLAUDE.md/handoff iddiasını current truth sayma; kod ve testle doğrula.

ADR 0002 artık Accepted (2026-08-05) ve README'ye göre Accepted ADR'ler DEĞİŞMEZ —
ADR 0002'yi düzenleme; gerekirse ADR 0003 yaz. §13'ün OD-1..OD-7'si HÂLÂ AÇIK.

BU ADIMIN AMACI (ADR §12.1'de ADIM 18b olarak planlandı; ADR'nin hiç yazılmamış ADIM 16'sı):
YARIM 1 — SAF REFACTOR: run_engine'in bar-loop gövdesini (engine.py:1782-1783) bir öğeyi
verilen t'ye ilerletebilen resumable stepper'a çıkar. run_engine imzasını VE semantiğini
korur, stepper üzerinde ince bir sürücü olur (ADR §3.2).
TEK KANIT: 46 golden digest'in HİÇBİRİ oynamamalı. Başka assertion'a güvenme (ADR R-4).
YARIM 2 — WIRING: stepper üzerinde portfolio_engine.ItemDriver'ı uygula ve worker'ın
>1 öğe yolunu run_portfolio'ya bağla. Digest'ler BURADA oynar: 9 portfolio.* senaryosunu
tek tek gerekçelendir; başka bir digest oynarsa regresyondur.
Tercihen iki ayrı PR; en azından iki ayrı commit.

REUSE ZORUNLU (yeniden yazma):
- domain/backtest/portfolio_engine.py: run_portfolio, ItemDriver, CashEvent, FillEvent,
  CloseEvent, AppliedFill, default_fill, PortfolioRun, portfolio_manifest_for
- execution/clock.py, intents.py, portfolio_ledger.py, arbitration.py, attribution.py,
  provenance.py — hepsi yerinde, hiçbiri yeniden yazılmaz

WIRING KIRACAK (bilerek, kazara değil):
test_nothing_imports_the_phase_loop · test_the_worker_still_loops_over_items · altı
containment suite'i. Containment testleri dosya metninde DÜZ SUBSTRING arar — yeni bir
üretim dosyası eklediğinde yorumlarında bile "execution.<modul>" geçerse kırılır; her yeni
üretim dosyasından sonra containment suite'ini YENİDEN KOŞ.

YAPMA: containment lift (SHARED_ALLOCATION_STATUS future_dev kalır), ENGINE_VERSION bump,
manifest alanlarını shipped manifest.py'ye bağlama (hepsi ADIM 20), margin/cross (ADR §9.5),
OD-2 mark policy seçimi, OD-3 seçim kuralı, NET semantiği (#544).

DOĞRULAMA: cd backend && uv run --extra dev ruff check . && uv run --extra dev ruff format
--check . && uv run --extra dev mypy src && uv run --extra dev pytest
(TEST_DATABASE_URL ile worktree'ye özel postgresql+asyncpg:// DB; TEK çağrı, çıktıyı dosyaya
yaz ve $?'i AYRI oku; `| tail` KULLANMA) +
uv run --extra dev python -m entropia.apps.api.openapi_export --check
Yeni davranışı MUTASYONLA sına: __pycache__'i her mutasyondan sonra SİL (aynı bayt uzunluklu
mutasyon stale .pyc bırakır) ve pytest exit 1 (test hatası) ile 4 (kullanım hatası) AYIR.

PR SONUNDA RAPORLA: base SHA, branch, commit, PR, changed behaviour, unchanged boundaries,
targeted tests, full-suite exit code, digest diff'i senaryo senaryo, migration/OpenAPI/codemap
etkisi, kalan risk, sonraki tek adım.

DURMA KOŞULU: Containmentı ADIM 20'den önce KALDIRMA. Wiring inince PR aç ve dur.
```
