<!-- doc-status: historical -->
> **EVIDENCE RECORD — 2026-08-07.** Bu belge o gün, o ağaç üzerinde koşulan oracle,
> determinizm ve containment kanıtının kaydıdır. Sayılar koşuldukları anın değerleridir;
> güncel otorite `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 29 / P7 — Oracle determinizmi ve Future-Dev containment

**Verdict: PASS — BLOCKED değil.** Dört başlığın dördü de geçti. Determinizm dört ayrı
süreçte ve üç ayrı hash-seed rejiminde **bit-bit** doğrulandı; `ENGINE_VERSION` kıpırdamadı;
unified portfolio'nun üç containment kanıtı da yeşil; pinli artefakt etiketleri manifest'ten
geliyor ve canlı registry join'i ile yeniden yorumlanmıyor.

PR B (`ItemParticipant` adaptörü + `jobs/backtest_engine.py:298`) **sokulmadı** — bu koşu
salt-okuma doğrulamadır, hiçbir kaynak dosya değiştirilmedi.

## Ağaç ve ortam

| | |
|---|---|
| HEAD | `6c239e4` (`origin/main` ile aynı, `git fetch` sonrası doğrulandı) |
| Branch | `claude/oracle-determinism-future-dev-d08e62` (worktree) |
| Working tree | temiz (`git status --porcelain` boş, koşu boyunca da öyle kaldı) |
| Python | 3.12.13 (CPython) |
| pytest | 9.1.1 |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` |
| İzole DB | `entropia_p7_oracle` (bu koşu için `CREATE DATABASE`; paralel worktree oturumlarıyla paylaşılmıyor) |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://entropia:***@localhost:5432/entropia_p7_oracle` |
| `LC_ALL` | `en_US.UTF-8` |

> **Alt-küme koşusu → `--no-cov`.** Her pytest çağrısı `--no-cov` taşıdı; kapı (`--cov-fail-under=90`)
> yalnız tam suite koşusunda anlamlıdır ve alt kümede sahte kırmızı verir. Bu belge **coverage
> iddiası taşımaz** — o P1'in işidir.

---

## 1. Oracle paketleri, determinizm ve reconciliation

### 1.1 Koşu — golden + bağımsız oracle, iki kez

```
uv run --extra dev pytest tests/unit/oracles/ tests/unit/test_backtest_engine_golden.py --no-cov -q
```

| Koşu | Sonuç | Exit |
|---|---|---|
| RUN 1 | 113 passed, 0 failed, 0 xfail | 0 |
| RUN 2 | 113 passed, 0 failed, 0 xfail | 0 |

Dağılım (collection): bağımsız oracle paketi **111** test / 10 modül + golden guard **2** test.

| Modül | Test |
|---|---|
| `oracles/test_oracle_costs.py` | 14 |
| `oracles/test_oracle_entry_exit_timing.py` | 10 |
| `oracles/test_oracle_orders.py` | 10 |
| `oracles/test_oracle_portfolio_capital.py` | 11 |
| `oracles/test_oracle_portfolio_clock.py` | 10 |
| `oracles/test_oracle_portfolio_containment_gate.py` | 4 |
| `oracles/test_oracle_position_lifecycle.py` | 9 |
| `oracles/test_oracle_properties.py` | 10 |
| `oracles/test_oracle_protection_stops.py` | 20 |
| `oracles/test_oracle_sizing.py` | 13 |
| `test_backtest_engine_golden.py` | 2 |

**Oracle paketinde `xfail`/`skip` sayısı sıfır** (`grep -c` = 0) — CLAUDE.md'nin "Oracle
paketinde xfail sıfır" ifadesi bu ağaçta doğrulandı.

Ham çıktı: [`p7_oracle_runs.txt`](p7_oracle_runs.txt).

### 1.2 Determinizm — aynı girdi, iki koşu, bit-bit aynı Result mı?

Test'in yeşil olması determinizm kanıtı **değildir** (aynı testin iki kez geçmesi, çıktının
aynı olduğunu göstermez). Bu yüzden ayrı bir prob koşuldu: **sevk edilmiş** golden senaryo
matrisini (`_scenarios()`, 46 senaryo) ve **sevk edilmiş** portfolio harness'ı yeniden
kullanan, kendi hiçbir beklenen değeri hesaplamayan bir betik. Her `EngineOutput`'un TAM
kanonik projeksiyonu (summary + trades + equity points + decision events + diagnostics +
position intervals; `Decimal` asla float'a çökmeden) SHA-256'ya indirgenir.

Ölçülen üç şey:

1. **Aynı süreç içinde** matris iki kez hesaplandı → 46/46 digest özdeş;
2. **Aynı süreç içinde** `run_portfolio` (unified-clock faz döngüsü) iki kez koşuldu →
   `PortfolioRun` digest'i özdeş;
3. **Ayrı süreçlerde**, `PYTHONHASHSEED` ∈ {`0`, `1`, `12345`, `random`} → dördünde de
   aynı aggregate digest.

| Ölçüm | Değer |
|---|---|
| Senaryo sayısı | 46 |
| `engine run A == run B` | **True** (4/4 süreçte) |
| `portfolio run A == run B` | **True** (4/4 süreçte) |
| `ENGINE_AGGREGATE_DIGEST` | `fa4a24e0b7c25bd86f0f65d2b77d5769ca00de6d216be1914abddd3dfb85ade2` |
| `BASELINE_AGGREGATE_DIGEST` (commit'li JSON) | `fa4a24e0b7c25bd86f0f65d2b77d5769ca00de6d216be1914abddd3dfb85ade2` |
| `PORTFOLIO_RUN_DIGEST` | `345b91a68399d5c8975141a1cac014ae1da84facaf4686388174094c409f3a79` |

Dört sürecin dördü de aynı iki digest'i üretti ve motor digest'i `engine_golden_digests.json`
taban çizgisiyle **birebir** eşleşti. `PYTHONHASHSEED=random` altında da sabit kalması,
çıktının sözlük yineleme sırasına bağlı olmadığını gösterir.

**Sonuç: aynı girdi iki koşuda bit-bit aynı Result üretiyor.** Doc 15 §17'nin
reproducibility sözleşmesi bu ağaçta karşılanıyor.

Ham çıktı: [`p7_determinism_probe.txt`](p7_determinism_probe.txt).
Prob kaynağı repoya **girmedi** (scratchpad'de kaldı) — sevk edilmiş kod değiştirilmedi.

### 1.3 Reconciliation — golden ile bağımsız oracle arasındaki fark toleransı

**Tolerans = 0. Sayısal tolerans diye bir şey yok, olması da gerekmiyor.** Görev bu ikisini
"uzlaştırılacak iki bağımsız hesap" gibi soruyor; ağaçtaki gerçek yapı bu değil ve olduğundan
farklı raporlamak yanlış olurdu:

| | Golden guard | Bağımsız oracle paketi |
|---|---|---|
| Ne yapıyor | Sevk edilmiş motorun TAM çıktısını dondurulmuş SHA taban çizgisiyle karşılaştırır | Elle canon'dan türetilmiş `Decimal` literalleri sevk edilmiş motorun çıktısıyla karşılaştırır |
| Beklenen değer nereden | Önceki bir koşudan (regresyon freeze) | İnsan, spec'ten (bağımsız türetme) |
| Karşılaştırma | Digest eşitliği (bit-bit) | `Decimal` tam eşitlik |
| Tolerans | yok | yok |

İkisi de **aynı** motoru (`entropia.domain.backtest.engine`) ölçer; farklı bir referans
implementasyon yoktur. Oracle paketinin tamamında `pytest.approx`, `math.isclose`, `rel=`,
`abs=` veya herhangi bir tolerans parametresi **yok** (grep: yalnızca "disclosed/discloses"
kelimelerinden gelen yanlış pozitifler). Örnek assertion'lar tam eşitlik biçimindedir:

```
test_oracle_costs.py:69   assert trade.pnl == Decimal("80.00")
test_oracle_costs.py:86   assert trade.pnl == Decimal("48.50")
test_oracle_sizing.py:73  assert _entry_size(out) == Decimal("50.00000000")
```

Yani "fark toleransı" sorusunun dürüst cevabı: **fark yok, tolerans da yok** — 113 testin
hepsi tam eşitlikle geçiyor. Bir gün ayrışırlarsa bu bir tolerans ayarı değil, ya bir
regresyon (golden kırmızıya döner) ya da bir spec hatası (oracle kırmızıya döner) olur;
`engine_golden_digests.json` sadece `ENGINE_VERSION` bump'ı ile yeniden üretilebilir ve
`test_the_golden_baseline_records_the_engine_version_it_was_taken_at` bunu kilitler.

---

## 2. `ENGINE_VERSION` — değişmemeli, değişmedi

| Kaynak | Değer |
|---|---|
| `domain/backtest/manifest.py:126` | `backtest-engine-v18-gap-adjusted-stop-fill` |
| `docs/generated/repository_facts.md:26` | `backtest-engine-v18-gap-adjusted-stop-fill` |
| `engine_golden_digests.json` `engine_version` | `backtest-engine-v18-gap-adjusted-stop-fill` |
| `test_oracle_portfolio_containment_gate.py:194` (pin) | `backtest-engine-v18-gap-adjusted-stop-fill` |

**Dördü de aynı → ÇELİŞKİ YOK.** Ek olarak üreteç kapısı bağımsız koşuldu:

```
uv run --extra dev python ../scripts/generate_repository_facts.py --check --root ..
→ documentation-truth gate OK — artefacts fresh, documents classified, no stale claims.   (exit 0)
```

`ENGINE_VERSION` üç ayrı yerde bağımsız olarak pinlidir (golden baseline JSON, containment
gate, üretilmiş facts) — birini kıpırdatan bir değişiklik diğer ikisini kırmızıya çevirir.

---

## 3. Unified portfolio = Future-Dev capability (RC blocker DEĞİL)

İstenen üç kanıtın üçü de sağlandı. Bu üçü birlikte **"sahte job / sahte output / sessiz
fallback yok"** demektir: mod açılamaz (kanıt A), açılsa bile onu koşacak bir üretim yolu
yok (kanıt B), ve bu iki gerçek çalıştırılabilir olarak kilitli (kanıt C).

### A. `SHARED_ALLOCATION_STATUS == "future_dev"`

```
backend/src/entropia/domain/allocation/capability.py:105
SHARED_ALLOCATION_STATUS: SharedAllocationStatus = "future_dev"
```

`docs/generated/repository_facts.md:27` → `future_dev` (üretilmiş, CI `--check` kapılı).
`shared_allocation_is_executable()` → `False`. Bu tek cevap dört yüzeyin hepsini besliyor:
`domain/allocation/rules.py` (blocker), `domain/readiness/validators.py`
(`ALLOCATION_SHARED_MODE_NOT_IN_BUILD`), `application/commands/backtest_run.py` (admission
guard, readiness bypass edilse bile tutar) ve Portfolio sayfasının capability view'i.

### B. `run_portfolio` üretimde çağrısız

`backend/src/` içindeki **tüm** `run_portfolio` geçişleri:

| Dosya:satır | Ne |
|---|---|
| `domain/backtest/portfolio_engine.py:1` | modül docstring'i |
| `domain/backtest/portfolio_engine.py:479` | **tanım** (`def run_portfolio(`) |
| `domain/backtest/portfolio_engine.py:569` | `__all__` girdisi |
| `domain/backtest/execution/portfolio_ledger.py:20` | docstring prose |
| `domain/backtest/execution/intents.py:15` | docstring prose |
| `domain/backtest/execution/arbitration.py:11` | docstring prose |

**Tek tanım, sıfır çağrı.** Kalan üç geçiş docstring metnidir, çalıştırılabilir kod değil.
`frontend/src/` içinde hiçbir referans yok. Çağıranların tamamı testtir (8 test dosyası,
oracle harness dahil).

Worker hâlâ eski yolu yürüyor — PR B'nin hedefi olan iki satır **dokunulmadan** duruyor:

```
application/jobs/backtest_engine.py:100   from ...execution.portfolio import combine_item_runs
application/jobs/backtest_engine.py:298   for prepared in prepared_items:
application/jobs/backtest_engine.py:363   output = combine_item_runs(
```

Hiçbir istek, retry veya job tick döngüsüne ulaşamaz → sevk edilmiş hiçbir Result değişemez.

### C. Containment gate testi YEŞİL

```
tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it  PASSED
```

Bu test iddiayı statik olarak da kanıtlıyor: `_SRC.rglob("*.py")` üzerinden (i) `run_portfolio`'yu
tanımlayan tek üretim modülü olduğunu, (ii) altı unified-clock modülünün faz döngüsü dışında
üretim importer'ı olmadığını, (iii) `callers == []` olduğunu, (iv) worker'ın item döngüsünü ve
`combine_item_runs`'ı koruduğunu assert eder.

Paketin diğer üç testi de yeşil — özellikle
`test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock`, contained defect'in
büyüklüğünü tek trade seti üzerinde gösteriyor (sıralı fold `max_drawdown=5000.00`, birleşik
saat `3000.00` — %66 abartı), ve
`test_the_containment_flag_and_engine_version_are_both_untouched` bayrak + versiyon çiftini
birlikte kilitliyor.

### Daha geniş containment yüzeyi (istenmedi, yine de koşuldu)

```
pytest tests/unit/test_shared_allocation_containment.py \
       tests/integration/test_shared_allocation_containment.py \
       tests/contract/test_repository_facts_guard.py --no-cov -q
→ 44 passed, exit 0   (9 unit + 7 integration + 28 contract)
```

Aralarında `test_admission_guard_holds_when_ready_check_is_bypassed`,
`test_retry_of_a_shared_composition_is_refused`,
`test_run_admission_refuses_and_leaves_nothing_behind` (yarım kayıt bırakmıyor),
`test_independent_mode_still_runs_to_a_result` (independent mod bozulmadı) ve
`test_a_legacy_shared_pool_result_stays_readable_and_unmodified` var.

Ham çıktı: [`p7_containment.txt`](p7_containment.txt).

---

## 4. Historical Result / manifest canlı registry join'i ile yeniden yorumlanmıyor

**Doğrulandı.** Etiket, artefakt YAZILIRKEN pinlenir; okuma yolunda canlı composition'a
join yoktur.

### Boru hattı (kaynak)

```
domain/backtest/manifest.py:160        def pinned_item_labels(item_manifest)
domain/backtest/manifest.py:257        "mainboard_item_labels": pinned_item_labels(item_manifest)
application/jobs/backtest_engine.py:295  item_labels = _manifest_item_labels(manifest.manifest)
application/jobs/backtest_engine.py:327  item_label=item_labels.get(prepared.item_id)
application/jobs/backtest_engine.py:633  def _manifest_item_labels(manifest) -> dict[str, str]
```

`mainboard_item_labels` anahtarı **hash'lenen execution içeriğinin DIŞINDA** tutulur — okumak
`execution_key`'i perturbe edemez; bir rename aynı kompozisyonun reproducibility kimliğini
çatallamaz. F-07 §4.4'ün ayrımı budur. Manifest bu anahtardan önce yazılmışsa boş map döner ve
satır ham id'ye düşer — **uydurulmuş isim yok**.

### Testler

| Koşu | Sonuç |
|---|---|
| `tests/unit/test_f07_manifest_item_labels.py` + `tests/unit/test_backtest_portfolio_mode.py` | 28 passed, exit 0 |
| `tests/integration/test_f07_display_labels.py` + `test_backtest_manifest_pinning.py` + `test_portfolio_simulation_mode.py` (gerçek DB) | 16 passed, exit 0 |

İddiayı doğrudan taşıyan testler:

- `test_renaming_the_item_does_not_relabel_an_existing_report` — item rename edildikten sonra
  mevcut rapor **yeniden etiketlenmiyor**;
- `test_a_later_composition_edit_does_not_relabel_an_existing_result` — aynısı Result için;
- `test_labelling_does_not_rewrite_the_immutable_artifact` — okuma-zamanı etiketi artefakta
  geri yazılmıyor (doc 15 §3.2 immutability);
- `test_the_history_index_labels_each_row_from_its_own_evidence` — history satırı kendi pinli
  kanıtından etiketleniyor, komşu satırdan veya canlı kayıttan değil;
- `test_unlabelled_scope_reports_null_not_a_derived_name` — isimsiz nesne **NULL** veriyor,
  id'den türetilmiş isim değil;
- `test_labels_do_not_change_the_execution_key` / `test_labels_are_absent_from_the_hashed_pin_set`
  — pinli etiketin `execution_key`'e sızmadığı.

Legacy shared-pool Result'ları okuma zamanında `LEGACY_SEQUENTIAL_RESULT_NOTE` ile dürüstçe
etiketleniyor (`domain/backtest/portfolio_mode.py:152`), ama artefakt **mutate edilmiyor** —
not projeksiyonda yaşıyor.

### Okuma yolunda join denetimi

`application/queries/results_history.py` içindeki tek `join(EntityRegistry, ...)` (satır 122)
**yetki kapsamı** içindir (`visible_composition_stmt` — hangi composition'ı görebilirsin),
etiket çözümlemesi değil. Satır 153'teki `outerjoin` `MetricValueRow` üzerinedir (sıralama
metriği). Satır DTO'su `composition_context` olarak yalnız id + **pinli** fingerprint taşır;
`engine_version` ve `manifest_hash` saklanmış satırdan gelir.

Ham çıktı: [`p7_pinned_labels.txt`](p7_pinned_labels.txt).

---

## Dürüst sınırlar

1. **Bu koşu tam suite değildir.** 113 + 44 + 44 test koşuldu, hepsi yeşil; bu, backend'in
   tamamının yeşil olduğu iddiası **değildir** ve coverage kapısı hakkında hiçbir şey söylemez
   (`--no-cov` ile koşuldu). Tam suite otoritesi CI'dır.
2. **Determinizm probu tek makinede ölçüldü** — aynı CPU, aynı CPython 3.12.13, aynı
   `libmpdec`. Farklı mimari/derleme üzerinde bit-bit aynılık bu koşuyla kanıtlanmadı;
   `Decimal` aritmetiği bunu taşımalıdır ama **ölçülmedi**.
3. **Oracle'lar KARARLARI değil DÖNGÜYÜ kanıtlar.** `portfolio_harness.ScriptedItem` neyi
   açacağını, neyin kapanmaya zorlandığını ve ne ücretlendirildiğini **fixture verisi** olarak
   bildirir; gerçek bir item bunları kendi indikatör evaluator'ından, stop resolver'ından ve
   pinli funding schedule'ından türetirdi. Harness'ın kendi docstring'i bunu açıkça beyan eder.
   Bu, oracle paketinin bilinen ve kabul edilmiş sınırıdır, bu koşunun bulgusu değil.
4. **Containment'ın açık boşluğu değişmedi:** worker'ı bağlamak gerçek motorla desteklenen bir
   `ItemParticipant` gerektirir (ADR §12'nin **hiç yazılmamış** ADIM 16 stepper'ı). PR B
   post-V1'dir ve bu koşuda **sokulmadı**.
5. **CLAUDE.md'deki F-07 kalıntı ifadesi bu ağaçta doğrulanmadı** (P7 bulgusu değil, belge
   doğruluğu notu). CLAUDE.md `pages/PanelLogs.tsx:134`'ün "hâlâ id'den türetilmiş
   `Backtest Result <id>` başlığını bastığını" yazıyor; koddaki hücre
   (`PanelLogs.tsx:143-145`) `<code>{row.result_id}</code>` render ediyor ve oradaki yorum
   `display_title`'ın **bilerek render EDİLMEDİĞİNİ** söylüyor (I-16a, 2026-08-03'te kapandı).
   Id'den türetilmiş dize backend tarafında bir varsayılan başlık olarak duruyor
   (`queries/results_history.py:289`, `queries/panel_backtest_log.py::_row`) — **canlı bir
   join değil**, dolayısıyla P7 §4 iddiasını etkilemiyor. Kalıntının hangi biçimde açık
   olduğu insan tarafından yeniden ifade edilmeli.

## Üretilen kanıt dosyaları

| Dosya | İçerik |
|---|---|
| [`p7_oracle_runs.txt`](p7_oracle_runs.txt) | golden + oracle iki koşu, collection dökümü |
| [`p7_determinism_probe.txt`](p7_determinism_probe.txt) | 4 süreç × 3 hash-seed rejimi, digest'ler |
| [`p7_containment.txt`](p7_containment.txt) | üç containment kanıtı + 44 test + facts gate |
| [`p7_pinned_labels.txt`](p7_pinned_labels.txt) | F-07 etiket boru hattı + 44 test |
