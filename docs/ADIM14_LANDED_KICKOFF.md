# ADIM 14 landed — Unified-clock portfolio ADR (PR #563) · sıradaki slice kickoff'u

> Bu belge **ADIM 14'ün** kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

| | |
|---|---|
| ADIM 14 | commit `992ac9d` · base `f4e2fd3` · **PR #563 MERGED** → `fb57cc8` (2026-08-04T18:27:28Z). Bu kapanış **`801791f`** üzerine rebase edildi (ADIM 13'ün kapanışı PR #562 arada merge oldu). |
| Landed | `docs/adr/0002-unified-clock-portfolio-simulation.md` (**761 satır**) + `docs/adr/README.md` indeks satırı |
| ADR statüsü | **Proposed** — PO / maintainer onayı bekliyor. **Accepted DEĞİL.** Onay gelmeden ADIM 15 başlamaz (§16). |
| Migration | **YOK** — alembic head `0043_i08_registry_strategy_fks`, tek head, dokunulmadı |
| OpenAPI | **196 operation / 151 schema** — değişmedi |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **ADIM 14 değiştirmedi** (bu değeri PR #555 getirdi) |
| Production kod | **DEĞİŞMEDİ** — docs-only, tek satır kod/test yok |
| Test suite | **KOŞULMADI.** Çalıştırılabilir hiçbir şey değişmedi; koşmuş gibi sayı raporlamak yanıltıcı olurdu. |
| Codemap | **Tazelenmedi — gerekmiyor.** Yeni endpoint / tablo / sayfa / job yok; `docs/CODEMAPS/` haritalarının hiçbirinin girdisi değişmedi. |

**Bir sonraki base:** `origin/main` @ `801791f` (veya bu kapanış PR'ı merge olduktan sonrası).
**Dallanmadan önce `git fetch` + merge doğrulaması yap** — bu seride `origin/main` oturum
ortasında birden fazla kez ilerledi.

## ✅ Numaralandırma çakışması — çözüldü (ADIM 14 = ADR, frontend slice = F-26)

`origin/main` üzerinde **ADIM 14 = bu ADR'dır** — ADR metni kendini böyle adlandırıyor
(§16: "Per the ADIM 14 brief") ve ADIM **15–20**'yi unified-clock programı için donduruyor (§12).

Bir süre **PR #562** (ADIM 13'ün kapanışı, merge `801791f` — ADR'dan **sonra** indi) kendi
"Next"inde **ADIM 14 = #539 + #533 frontend capability disclosure** diyordu; iki tanım aynı
numarayı kullanıyordu.

**Karar (2026-08-04): ADIM 14 = ADR, frontend slice = `F-26`.** ADR immutable ve merge edilmiş
gerçeğin tarafında olduğu için taşınan taraf slice oldu. `F-26` seçildi çünkü (1) iş saf
frontend sunum işidir ve F-serisi tam olarak bunu adlandırır — `F-01…F-25` doluydu, `F-26` ilk
boş numara; (2) ADIM 15–20 unified-clock'a rezerve olduğundan ADIM serisinden numara
harcanmamalıydı. Slice **PR #564 ile landed** (`5887f3f` → merge `b8d62e2`).

`STAGE2_HANDOFF.md` içinde #562'nin "Next" bloğu **"Eski Next"** başlığıyla duruyor — silinmedi,
etiketi F-26 olarak düzeltildi; slice'ın sonuç kaydı aynı belgede
`## F-26 — Strategy formu capability disclosure landed (PR #564)`, tam kaydı
`docs/PROJECT_HISTORY.md` §F-26.

## ADIM 14 ne bıraktı — reuse anchor'ları

Bu slice'ın çıktısı kod değil, **dondurulmuş sınırlardır**. Üçü de ADR içinde, tam yerleriyle:

### 1. ADIM 15–20 sınırları (ADR §12) — her adım tek branch, tek PR, bağımsız revert edilebilir

| ADIM | Ne | Birincil dosyalar | Kapı |
|---|---|---|---|
| **15** | Merged-axis clock primitive: `t_ms` anahtarı, item bar iterator'ları üzerinde streaming k-way merge, `(pin_ordinal, item_id)` tie-break. **Saf; engine kullanmıyor.** | yeni `domain/backtest/execution/clock.py` | yeni unit testler (dedup, tek-item indirgemesi, interleaving, boş eksen, stream-not-materialize) |
| **16** | `run_engine`'in bar-döngü gövdesini **resumable stepper**'a çıkar; `run_engine` imzasını **ve semantiğini** korur, stepper üzerinde ince sürücü olur. **Saf refactor.** | `domain/backtest/engine.py`, `execution/state.py` | **46 golden digest'in tamamı değişmemeli** |
| **17** | `PortfolioLedger` + `PortfolioSnapshot`; tek `E(t)`'den türeyen `Ci(t)`; `R0`/`U0` bir kez tutulur. Yalnız multi-item yol. | `execution/state.py`, `execution/sizing.py`, yeni `execution/portfolio_ledger.py` | doc 13 §14 test 10 (3600/3150/1350, U0=900) |
| **18** | `ItemIntent` + tick başına faz döngüsü (§8), **yeni** `run_portfolio(...)` girişinde; worker yalnız >1 item yürütürken çağırır. `run_engine` buradan geçmez. | `application/jobs/backtest_engine.py`, yeni `domain/backtest/portfolio_engine.py` | doc 13 §14 test 11 + cross-item batch invariance |
| **19** | Çatışma/exposure arbitrasyonu (§9): simetrik, deterministik, solvency **reject** (asla kısmi, asla borç), tam karar izi. `PriorItemInterval` forward-only önceliğini emekliye ayırır. | `execution/rules.py`, `domain/allocation/rules.py` | doc 13 §14 test 12, 13; beş `portfolio.rules_*` digest'i yeniden kaydedilir |
| **20** | Manifest alanları (§10.1), `ENGINE_VERSION` bump, digest yenileme, **containment lift**, Result portfolio metadata + OpenAPI, codemap'ler. | `manifest.py`, `capability.py`, `readiness_check.py`, `docs/openapi.json`, `docs/CODEMAPS/*` | §14 acceptance matrisinin tamamı |

**ADIM 15–20'nin parçası OLMAYAN önkoşullar** (ayrı planlanmalı): **#559** (DST) — merged
eksen karışık-zaman-dilimli kaynakları kapsamadan önce; **#544** (NET) — ADIM 19 ile ya da
öncesinde; **R-1** (§10.2 revision pinning) — ADIM 20'den önce; **OD-1…OD-6** — her biri
bağlı olduğu adımdan önce.

**`test_shared_allocation_containment.py` re-digest EDİLMEZ, yeniden yazılır.** Merkezî testi
kusuru bilerek doğruluyor (`:139-190`); saat inince iddiaları tersine döner (eğri zaman-sıralı
olur, `max_drawdown` `3000.00`'a döner). **Bu tersine dönüş kabul kanıtının kendisidir.**

### 2. Yedi açık karar (ADR §13) — **tahmin etme, karar aldır**

| ID | Soru | ADR'ın önerisi (onay gerekir) |
|---|---|---|
| **OD-1** | Engine `record_time_basis`'i (BAR_OPEN/BAR_CLOSE/EVENT_TIME) onurlandırmalı mı? | (a) sevk edilmiş konvansiyon korunur **+** farklı basis bildiren pinli revision'lı shared run **bloke** edilir |
| **OD-2** | Kendi item'ının taze barı olmayan tick'te açık pozisyon nasıl mark edilir? | (a) son kapanan bar ileri taşınır; bildirilmiş `stale_after` sınırı + diagnostic sayaç ile |
| **OD-3** | Tek tek karşılanabilir ama birlikte karşılanamayan intent'lerden hangisi reddedilir? | (a) `(pin_ordinal, item_id)` sırasıyla kabul, kalanı reddet — (b) tam simetrik "hepsini reddet" ciddi alternatif |
| **OD-4** | `Ci(t)` yalnız **girişte** yeni notional'ı mı sınırlar, yoksa tutulan notional'ı sürekli mi? | (a) yalnız giriş/scale anında (literal kanonik okuma) |
| **OD-5** | FX dönüşümü kapsamda mı? | (a) hayır — shared run'lar **tek para birimi**, uyuşmazlık blocker kalır |
| **OD-6** | Trading Signal / Trade Log item, engine onun için hiçbir şey koşmazken sleeve tutabilir mi? | (a) ADIM 20 için **bloke et**; (c) icra implementasyonu ayrı program |
| **OD-7** | Daha eksiksiz equity serisi `METRIC_SET_VERSION` bump'ı gerektirir mi? | (a) hayır — `ENGINE_VERSION` zaten namespace'i çatallıyor |

### 3. Kabul matrisi A1–A22 (ADR §14) — containment lift'in kapısı

Kritik olanlar: **A4** item sırası sonucu değiştirmez (permütasyon → aynı digest);
**A13** 37 portföy-dışı golden digest değişmez, yalnız 9 `portfolio.*` senaryosu hareket eder;
**A15** `ENGINE_VERSION` bump + `execution_key` namespace kayması; **A17** PR #560'ın
point-in-time testleri **zayıflatılmadan** yeşil; **A19** eski shared-pool Result byte-identical
okunur ve `LEGACY_SEQUENTIAL_RESULT_NOTE` ile etiketlenir; **A20** rollback kanıtlanır
(`SHARED_ALLOCATION_STATUS` geri çevrilince shared run yine reddedilir); **A22** full backend
suite `--cov-fail-under=90` kapısında yeşil.

## Açık kalemler (bu slice'ın devraldığı + bulduğu)

1. **R-1 — ADR'ın kendi bulduğu latent kusur (§10.2).**
   `application/commands/readiness_check.py::_resolve_allocation` (`:805-838`) kendini
   *"plan'ın mevcut revision config'ini pinler, yoksa canlı draft"* diye belgeliyor ama kod
   **koşulsuz** `config = _plan_to_config(plan, entries)` ile **canlı draft satırlarından**
   kuruyor, sonra `plan_revision_id = plan.current_revision_id`'yi çıplak pointer olarak
   yazıyor. Pinlenen config'in adı geçen revision satırıyla
   (`PortfolioAllocationPlanRevision.config`) byte-eşleştiğini **hiçbir şey doğrulamıyor.**
   Snapshot bir kez alınıp bir daha join edilmediği için bu canlı-join kusuru DEĞİL — ama
   "plan revision N" ile "gerçekte simüle edilen" ayrışabilir. **ADIM 20'den önce, ayrı ve dar
   bir PR.** Worktree `claude/allocation-revision-pin-fix-bb18c9` (`f4e2fd3` üzerinde) açık ama
   **boş** — iş henüz yapılmadı.
2. **Manifest'te eksik üç kanonik alan (§10.1).** Doc 13 §13 + Modül 11 §10 shared-mode
   manifest'inin **resolved sleeve amounts**, **currency/FX refs** ve
   **`engine_allocation_policy_version`** taşımasını istiyor. Sevk edilen `capital_execution`
   snapshot'ı yalnız `{enabled, plan_id, plan_revision_id, config_hash, config}` taşıyor
   (`readiness_check.py:829-835`); `grep -rn "allocation_policy" backend/ docs/openapi.json`
   **hiçbir şey** döndürüyor. Bugün zararsız çünkü shared mode contained. **ADIM 20'den önce kapanmalı.**
3. **#544 (NET)** — cross-item conflict policy kanonda tanımsız. ADIM 19 ile ya da öncesinde.
4. **#559 (DST)** — DST fold/gap sessizce çözülüyor; merged eksen bunu **cross-item** hale getirir.
5. **#539 (CRITICAL, ADIM 11'den)** — 22 `future_dev` satırının 11'i Strategy formunda devre dışı
   bırakılmıyor. Engine aritmetiğinden bağımsız; düzeltmesi **açık PR #564**'te.
6. **#550 / #551 / #552** (ADIM 12'den, hepsi açık) — sizing/booking uyuşmazlıkları. Bu ADR
   onlara dokunmuyor ve onlar da unified clock'u bloke etmiyor, ama #550 karara bağlanmadan
   sizing üzerine yeni iş yapılmamalı (saved revision migration'ı ister).

## Bir sonraki slice için tasarım işaretleri

**Sıradaki tek adım yine kod değil, bir onay: ADR'ın statüsü.** §16 açık —
implementasyon PO/maintainer onayına kadar başlamaz. Onay gelirse statü **Accepted** olur,
§13'ün kararları bir amendment tablosuna ya da takip ADR'ına **çözüm olarak** yazılır ve
ADIM 15 §12 sınırlarına karşı başlar.

**Onay beklenirken paralel yürütülebilecek, ADR'ı bloke etmeyen işler:** R-1 dar PR'ı;
#559 (DST) kararı; #539 (PR #564 zaten açık); #544 (NET) ürün kararı.

**ADIM 15'e başlanırsa dikkat:** clock primitive'i **saf** kalmalı — engine'e hiçbir import
bağlanmamalı. ADIM 15'in tek kanıtı kendi unit testleri; "engine artık onu kullanıyor" ADIM 18'in
işi. ADIM 16'nın tek kanıtı ise **hiçbir şeyin kımıldamaması** (46 golden digest); başka hiçbir
iddiaya güvenilmez (ADR R-4).

**REUSE listesi:** ADR §12 tablosu (PR sınırı ve dosya listesi — kendi bölmeni icat etme),
§13 OD tablosu (kanonun sessiz olduğu her yer; bir OD'yi "herhalde böyledir" diye kapatma),
§14 A1–A22 (kabul kanıtı; yeni kanıt icat etmeden önce burada var mı bak),
§10.3 versiyon planı (hangi knob ne olur), `domain/allocation/capability.py` içindeki
6 numaralı kaldırma koşulu.

## Çalışma döngüsü (ADIM 14'te işe yarayan)

1. `git fetch --all --prune` → **merge'i doğrula** → `git switch -c <branch> origin/main`.
2. Her kod iddiasını **tek bir commit üzerinde** oku ve o SHA'yı belgeye yaz (ADR "Base:
   `f4e2fd3`" diyor ve her satır numarası o commit'e ait). Satır numarası veren ama base
   SHA'sını söylemeyen bir belge altı ay sonra doğrulanamaz.
3. Kanonun **sessiz** olduğu yeri "canon böyle diyor" diye raporlama — açık karar (OD) olarak
   ayır, seçenekleri ve öneriyi yaz, kararı insana bırak.
4. Belge yazarken bulunan kusur (R-1 gibi) **belgede kalır ve ayrı kalem olarak açılır** —
   aynı PR'da düzeltilmez.
5. Docs-only slice'ta **test suite'i koşma ve koşmuş gibi sayı yazma.** "Çalıştırılabilir
   değişiklik yok" dürüst sınırdır; eski bir koşunun sayısını yeni slice'a etiketlemek değildir.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 15: <BAŞLIK BURAYA — varsayılan: merged-axis clock primitive>

ROL VE ÇALIŞMA BİÇİMİ

Sen Entropia V18 üzerinde çalışan kıdemli principal engineer ve release-closure
sorumlususun. Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini
current `origin/main` üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile
kapatmak ve sistemi geriletmemektir.

Read-only subagent'ları araştırma/inceleme için kullan; production değişikliklerini
yalnız ana oturum yapsın; tek branch, tek PR, tek sorumlu writer.

HER OTURUMUN ZORUNLU BAŞLANGICI

1. `git fetch --all --prune` · `git status --short` — temiz değilse DUR.
2. `git reset --hard origin/main`; current main SHA + açık PR/issue snapshot'ı al.
3. **PR #563 (ADIM 14 ADR) merge edildi mi doğrula** — edildi (`fb57cc8`). Bu kapanış
   PR'ının (`docs/adim-14-landed`) merge durumunu da doğrula.
4. **`docs/adr/0002-unified-clock-portfolio-simulation.md` STATÜSÜNÜ OKU.** Hâlâ
   **Proposed** ise ADIM 15 BAŞLAMAZ (§16). Onay yoksa kod yazma; onay durumunu sor.
5. `docs/ADIM14_LANDED_KICKOFF.md` (bu belge) + ADR §12 (sınırlar), §13 (açık kararlar),
   §14 (kabul matrisi) — bu üçü slice'ın sözleşmesidir.
6. **Numaralandırma çözüldü — yeniden açma:** **ADIM 14 = bu ADR**, frontend capability
   disclosure slice'ı (#539 + #533) **`F-26`** olarak etiketlendi ve **PR #564 ile landed**.
   **ADIM 15–20 unified-clock'a rezervedir** — ADIM serisinden numara harcama; ADIM dışı
   işlere F-serisinden sıradaki boş numarayı ver.
7. İlgili `docs/CODEMAPS/` haritasını ve gerçek çağrı zincirini oku.
8. Eski README/CLAUDE.md/handoff/backlog iddiasını current truth sayma — kaynak dosyayı oku.

BU ADIMIN AMACI

<BRIEF BURAYA. ADIM 15 varsayılanı: ADR §12'nin 15 numaralı satırı — yeni
domain/backtest/execution/clock.py; t_ms anahtarı, item bar iterator'ları üzerinde
streaming k-way merge, (pin_ordinal, item_id) tie-break. SAF modül: engine ondan
hiçbir şey import etmez, worker onu çağırmaz. Kanıt yalnız kendi unit testleri:
dedup, tek-item indirgemesi (§3.2), interleaving, boş/tek-taraflı eksen,
materialize-etmeden-stream. Rollback = modülü sil, hiçbir şey import etmiyor.>

TAVİZ VERİLEMEZ KURALLAR

ADR §13'ün YEDİ açık kararı (OD-1…OD-7) KARARA BAĞLANMADAN o karara bağlı davranış
implemente EDİLMEZ; boşluğu boşluk olarak raporla, varsayılan uydurma. Containment
(SHARED_ALLOCATION_STATUS) yalnız ADIM 20'de ve yalnız §14 matrisi tam geçince kalkar.
46 golden digest ADIM 16'da DEĞİŞMEZ; hareket eden bir digest yalnız yazılı gerekçeyle
kabul edilir. ENGINE_VERSION yalnız ADIM 20'de bump edilir.

Trading Signal ve Trade Log Package değildir. Backtest Run ile Result aynı entity
değildir; yalnız SUCCEEDED Run immutable Result üretir. Agent human account değildir.
Uzun işler durable queue üzerinden yürür. UI hidden/disabled durumu authorization
değildir. Server-side policy, ownership, OCC, idempotency, audit ve lifecycle korunur.
Revision/snapshot/fingerprint/manifest/pinned revision geriye dönük bozulmaz. Research
Data için event_time ve available_time ayrımı korunur. Historical Result canlı
root/live registry join'iyle yeniden yorumlanmaz. Başarısız test varken `Complete`
yazılmaz.

ZORUNLU DOĞRULAMA

- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<wt>_db`
  ile **tek** pytest çağrısı, arka planda, çıktı dosyaya, exit code ayrı okunur
  (`| tail` KULLANMA — exit code tail'in olur).
- Golden digest ve engine suite'leri korunur; oracle paketi (`tests/unit/oracles/`)
  onların yerine geçmez ve zayıflatılmaz.

PR DİSİPLİNİ

Yalnız bu slice. İlgisiz refactor/dependency/görsel değişiklik yok. Migration varsa
single-head + up/down/up kanıtı. Engine semantiği değişiyorsa ENGINE_VERSION kararını
açıkça değerlendir. Public API değişiyorsa OpenAPI snapshot + frontend wire contract.
Claude merge etmez, tag/release oluşturmaz. PR sonunda base SHA, branch, commit, PR,
changed behavior, unchanged boundaries, targeted tests, full-suite exit code,
migration/OpenAPI/codemap etkisi, kalan risk ve sonraki tek adım raporlanır.
```
