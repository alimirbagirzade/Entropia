# ADIM 16 landed — resumable stepper; sıradaki iş PR B (adaptör + worker call site)

> Bu belge **PR A'nın devri**dir. Otorite sırası: (1) bu belge, (2)
> `docs/adr/0002-unified-clock-portfolio-simulation.md` (§3.2, §12 düzeltme notu, §15 R-4),
> (3) `docs/STAGE2_HANDOFF.md` en alttaki `## Next:`, (4)
> `docs/audit/unified_portfolio_oracle_acceptance.md`. En altta **paste-ready resume prompt**.

---

## 1. Nerede duruyoruz

`run_engine`'in bar döngüsü artık **resumable**. PR **#602** (`refactor(adim-16)`, merged) ADR
§12'nin *atlanmış* ADIM 16'sını gerçekten yazdı — faz döngüsünün yerine değil, **worker call
site'ının ön koşulu** olarak (ADR §12 düzeltme notu bunu birebir böyle söylüyordu).

`run_engine` **imzasını, docstring'ini ve semantiğini korudu**; gövdesi dokuz satırlık bir
sürücüye indi. Kurulum yarısı `_build_stepper(...)` oldu ve bir `_ItemStepper` döndürüyor.

---

## 2. PR B'nin devralacağı reuse anchor'ları — tam sembol adlarıyla

| ne | nerede |
|---|---|
| stepper fabrikası | `domain/backtest/engine.py::_build_stepper` |
| stepper kaydı | `engine.py::_ItemStepper` |
| bir barı ilerlet | `_ItemStepper.step(bar: _Bar) -> None` |
| gün sonu (resting order iptali + açık pozisyon kapanışı) | `_ItemStepper.finalize() -> None` |
| sonucu projekte et | `_ItemStepper.output() -> EngineOutput` |
| tutulan pozisyonu oku | `_ItemStepper.open_position() -> _Position \| None` |
| canlı defter / çözülmüş run ayarları | `_ItemStepper.ledger` (`_Ledger`), `_ItemStepper.ctx` (`_RunConfig`) |
| ham dict → `_Bar` | `execution/state.py::_normalize` (modül düzeyinde, saf) |
| eşdeğerlik kanıtı (şablon) | `tests/unit/test_backtest_engine_stepper.py` |

**Sözleşme:** `_build_stepper(...)` `run_engine`'in **tüm** anahtar argümanlarını alır, **yalnız
`bar_batches` hariç** — bar akışını artık çağıran sahiplenir. Fail-closed
`UnresolvedStrategyError` **fabrikada** atılır, ilk bardan önce.

**Neden `_ItemStepper` bir dataclass ve state closure'da kaldı:** replay durumu eskiden
`run_engine`'in frame'indeydi; onu bir `self`'e taşımak 1355 satırın her adını
`self.` ile yeniden yazmak demekti — yani "saf refactor" iddiasını kaybetmek. Bu yüzden state
tam olarak durduğu yerde bırakıldı ve kayıt yalnız closure'lara işaret ediyor.

---

## 3. Bu slice'ta ölçülen, PR B'nin güvenebileceği gerçekler

- **Bar'lar arası taşınan state tam 10 addır** (AST ile ölçüldü, tahmin değil):
  `current_day · exit_touch · funding_idx · pending · position · prev_entry_signal ·
  prev_scale_signal · scale_signal · working_limit · working_stop`.
  Gövdenin bağladığı diğer **83** ad bar-içi geçicidir — kesin-atama (definite-assignment)
  analizi her okuma öncesi yazıldıklarını kanıtladı.
- **Yerinde mutate edilenler** (rebind değil, bu yüzden `nonlocal` gerekmez): `led.*`,
  `position.*`, `window` (deque). Bir katılımcı adaptörü bunları `stepper.ledger` /
  `stepper.open_position()` üzerinden okur.
- `position_seq` `_do_open`'ın `nonlocal`'ı olarak fabrikada kaldı — `_step` ona dokunmaz.

---

## 4. Sıradaki tek adım — PR B (ADIM 20 DEĞİL)

Stepper'ın üstüne `portfolio_engine.ItemParticipant`'ı uygulayan bir adaptör yaz
(`carry` / `mandatory_exit` / `entry`), ve `jobs/backtest_engine.py:298`'deki item döngüsünü
`run_portfolio` ile değiştir — **yalnız >1 item çalışırken**; tek item `run_engine`'de kalır
(ADR §3.2, tek-öğe indirgemesi).

### 4.1 ÖLÇÜLDÜ: PR B literal kapsamıyla ulaşılabilir DEĞİL — önce bir karar gerekiyor

Bu slice kapanırken sözleşme okundu ve **üç somut engel** çıktı. Hiçbiri "adaptör yaz" ile
kapanmıyor; PR B'ye başlayan oturum bunları veri olarak devralsın diye buraya yazıldı.

**(a) Stepper atomik, faz döngüsü değil.** `portfolio_engine._run_tick` katılımcıya ayrı ayrı
girer: `P1 carry` → `P3 mandatory_exit` → **PV `publish_snapshot` (defter DONAR)** → `P4 entry`
→ P5/P6b arbitrate → P7 apply. `carry` **snapshot yayımlanmadan ÖNCE** bilinmek zorunda, çünkü
paylaşılan deftere ondan önce işleniyor. `_ItemStepper.step(bar)` ise P1..P8'in hepsini **tek
çağrıda** yapar ve sonucu **kendi** `_Ledger`'ına yazar. Aynı barı üç kez adımlamak çift
booking'dir; adımlamadan `carry`/`mandatory_exit` sormak mümkün değil. → **Barın kendisi fazlara
bölünmedikçe gerçek engine bir `ItemParticipant`'ı besleyemez.**

**(b) `entry` item-local warmup ister, ama booking istemez.** `CarryCharges` / `MandatoryExit`
docstring'leri bu ikisinin **sevk edilmiş resolver'lardan** (`costs.due_funding_charges`,
`fills._resolve_stop` + `engine._plan_exit`) geldiğini söylüyor — yani stepper olmadan da
kurulabilirler. Stepper'a gerçekten ihtiyaç duyan tek hook **`entry`**: boyut
`costs._effective_fill` → `sizing._position_size` zincirini ve **indicator evaluator warmup'ını**
ister, ki bu tam olarak stepper'ın closure'ında duran item-local state'tir. Yani ihtiyaç duyulan
şey "bir barı ilerlet" değil, **"sinyali değerlendir ama hiçbir şey book etme"** — stepper'da
böyle bir giriş yok.

**(c) `run_portfolio`'nun çıktısı Result'a bağlanamıyor.** `run_portfolio` →
`PortfolioRun{ledger, ticks}`. Worker'ın Result assembly'si ise `ItemRun.output`
(`EngineOutput`: summary / trades / equity_points / signal_events / diagnostics /
position_intervals) üzerinden `combine_item_runs` ile çalışıyor. **`PortfolioRun → EngineOutput`
(ya da → Result artifact) projeksiyonu kod olarak YOK.** ADR'nin A4/A18 satırlarının "gerçek
`EngineOutput` digest'i ister" demesinin sebebi budur; o projeksiyon başlı başına bir slice.

**Ek olarak:** faz döngüsü **P2 pending fills** ve **P8 same-direction scaling**'i bilerek
modellemiyor (`UnsupportedIntentKindError`), ama gerçek bar gövdesi ikisini de yapıyor. Gerçek
engine ile beslenen bir katılımcı, scaling'i açık HERHANGİ bir stratejide anında raise eder.

**Sonuç — PR B'den önce insan kapısı.** ADR §16 onay kapısının bir kez sıra dışı işletildiğini
kaydediyor ve *"should hold for ADIM 20, which is the first slice that changes a shipped
number"* diyor. (a)+(c)'yi kapatmak `run_engine`'in bar gövdesini fazlara bölmek demek — yani
PR A'nın kapattığı byte-identity sorusunu yeniden açmak. **Bu bir ADR amendment'ı gerektirir,
sessizce yeniden planlanamaz.** Seçenekler:
1. **Barı fazlara böl** (yeni slice, kabul yine 46 digest) → sonra adaptör → sonra projeksiyon.
2. **Katılımcıyı sevk edilmiş primitiflerden kur** (stepper'ı yalnız sinyal/warmup için kullan,
   bunun için stepper'a book-etmeyen bir değerlendirme girişi ekle) → yine projeksiyon borcu.
3. **Önce projeksiyonu yaz** (`PortfolioRun → Result`), çünkü hangi yol seçilirse seçilsin
   gerekiyor ve tek başına test edilebilir.


**Beklentiler:** 37 non-portfolio digest **KIMILDAMAMALI**. `portfolio.*` digest'lerinin
kımıldaması bekleniyor — **her biri tek tek gerekçelendirilir**. `ENGINE_VERSION`'a
DOKUNMA, containment'ı KALDIRMA (ikisi de ADIM 20).

**Sonra ADIM 20.** Hâlâ açık ön koşullar: A17 (4 strict xfail — #556 ×2, #557, #558) ·
OD-1/OD-2/OD-6 kapıları **kod olarak yok** · `MARK_STALENESS_POLICY` +
`CONTENTION_SELECTION_STATUS` flip'i · #544 (NET) · #559 (DST).

---

## 5. Bu slice'ta işleyen yöntem (PR B'de tekrarla)

1. **Arayüzü ölç, okuma.** 1355 satırlık bir gövdenin hangi adı taşıdığını gözle çıkarmak
   güvenilir değil; AST ile çıkarıldı ve kesin-atama analiziyle kapatıldı.
2. **Taşınan her satırın birebirliğini kanıtla.** Düzenlemeden sonra taşınan aralıklar
   `HEAD`'e karşı satır satır karşılaştırıldı (setup 955 · step 1351 · finalize 44 · output 15).
   Formatter'ın dedent sonrası tek satıra topladığı bir `max(...)` çağrısı tek istisna.
3. **Golden'ın göremediği yarıyı ayrıca test et.** `run_engine` stepper'ı tek kesintisiz
   geçişte besler; bar-içi yerel olmuş bir taşınan ad yine de kayıtlı digest'i üretebilirdi.
   Testler senaryoları **bar başına bir çağrıyla, her bar arasında askıya alarak** koşar.
4. **Yerel doğrulama:** `uv run --extra dev ruff check . && ruff format --check . && mypy src`
   + tam suite **tek çağrıda**, çıktı **dosyaya**, `$?` **ayrı**. `TEST_DATABASE_URL` ile
   worktree'ye özel `postgresql+asyncpg://` DB. Alt küme koşarken `--no-cov`.
   **`uv run` `uv.lock`'u kirletiyor** — commit'e sadece değişen yolları stage et.
5. **GateGuard:** YENİ dosya → Bash heredoc (gate-free). Mevcut dosyaya EDIT/WRITE → 4 olgu sun.

---

## 6. Paste-ready resume prompt

```text
ENTROPIA V18 — worker call site PR B: ItemParticipant adaptörü + run_portfolio call site

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -rn "run_portfolio(" backend/src    # üretimde çağıran VAR MI?
  grep -n "_build_stepper\|_ItemStepper" backend/src/entropia/domain/backtest/engine.py

OKUMA SIRASI:
  1. docs/ADIM16_STEPPER_LANDED_KICKOFF.md                  ← bu belge (PR A'nın devri)
  2. docs/adr/0002-unified-clock-portfolio-simulation.md    ← §3.2, §12 düzeltme notu, §15 R-4
  3. backend/src/entropia/domain/backtest/portfolio_engine.py  ← §"HONEST BOUNDARY" ÖNCE oku
  4. backend/tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant  ← referans katılımcı
  5. docs/STAGE2_HANDOFF.md — en alttaki "## Next:"

DURUM: PR #602 ile run_engine'in bar döngüsü resumable stepper'a çıktı (_build_stepper →
  _ItemStepper{step, finalize, output, open_position, ledger, ctx}). run_engine imzası/semantiği
  değişmedi, 46/46 golden digest sabit. run_portfolio HÂLÂ üretimde çağrısız;
  jobs/backtest_engine.py:298 item döngüsü, :363 combine_item_runs.
  SHARED_ALLOCATION_STATUS = future_dev.

GÖREV:
  (a) Stepper üstüne portfolio_engine.ItemParticipant'ı uygulayan bir adaptör yaz:
      carry / mandatory_exit / entry. DİKKAT: entry kendi ItemIntent'ini kurmalı (boyut item'ın
      StrategyConfig'ini ister), ve stepper bir barı BÜTÜN OLARAK ilerletirken faz döngüsü aynı
      barı FAZLARA BÖLÜNMÜŞ ister — bu boşluğu kapatmak bu PR'ın asıl tasarım işi, mekanik
      ikame değil. Uyduramadığın fazı fail-closed reddet, sessizce modelleme.
  (b) jobs/backtest_engine.py:298 item döngüsünü run_portfolio ile değiştir — YALNIZ >1 item
      çalışırken; tek item run_engine'de kalır (ADR §3.2).
  (c) Containment guard'ını (tests/unit/oracles/test_oracle_portfolio_containment_gate.py::
      test_the_phase_loop_exists_but_no_production_path_reaches_it) GEVŞETME — yeniden YAZ:
      artık üretim yolu var, assertion'lar korunur, adlar düzeltilir, importer'lar ADLANDIRILIR.

KABUL:
  - 37 non-portfolio golden digest KIMILDAMAMALI.
  - portfolio.* digest'lerinin kımıldaması BEKLENİR — her biri tek tek gerekçelendirilir.
  - Tam backend suite yeşil + coverage kapısı (>=%90).

YAPMA:
  - ENGINE_VERSION'a dokunma. Containment'ı (SHARED_ALLOCATION_STATUS) KALDIRMA. İkisi ADIM 20.
  - Oracle'ların beklenen literallerini değiştirme; harness'a ikinci bir motor yazma.
  - NET'i desteklenir yapma (#544). Manifest policy alanı ekleme (ADIM 20).
  - run_engine'in imzasını/semantiğini değiştirme — tek-öğe yolu byte-identical kalır.

DOĞRULAMA:
  cd backend && uv run --extra dev ruff check . && uv run --extra dev ruff format --check . \
    && uv run --extra dev mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree_db> \
    uv run --extra dev pytest -q > /tmp/full.log 2>&1; echo $?   # tek çağrı, exit code AYRI
  Alt küme koşarken --no-cov. `git status backend/uv.lock` — uv run lock'u kirletir, stage etme.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```
