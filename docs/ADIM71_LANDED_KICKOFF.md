<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı). **Canlı kickoff: `docs/ADIM72_KICKOFF.md`.**

# ADIM 71 LANDED — describe/book split (C1 / E4a) · sıradaki slice için kickoff

## Neredeyiz

**Squash `dc2902f` (PR #735)** · alembic head **`0043_i08_registry_strategy_fks`** ·
`ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
**`future_dev`** · migration **YOK**. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
verdict BLOCKED.**

C1 indi: `_ItemStepper`'ın üç karar fazı describe/book çiftlerine ayrıldı, **50 golden
digest oynamadan**. Paket C'nin sıradaki adımı **`C2`** ve o **iki imzasız insan kapısının
arkasında** — kod yazmadan önce §Sıradaki'ye bak.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

| Sembol | Nerede | Ne işe yarar |
|---|---|---|
| `_compute_carry(bar) -> _CarryPlan \| None` | `engine.py:2087` | P1 tarif — cursor'ı **ilerletmez** |
| `_book_carry(bar, plan)` | `engine.py:2143` | P1 book — `funding_idx`'i ilerletir |
| `_evaluate_held(bar) -> _HeldDecision \| None` | `engine.py:2459` | P3 tarif — `None` = flat |
| `_apply_held(bar, decision)` | `engine.py:2538` | P3 book — kolu uygular |
| `_evaluate_entry(bar) -> _EntryDecision \| None` | `engine.py:2677` | P4 tarif — **sıfır etki** (ölçüldü) |
| `_apply_entry(bar, decision, *, equity=None)` | `engine.py:2789` | P4 book — `equity` scope'u BURADA |
| `_LedgerEffect` / `_book_effects` | `engine.py:1409` | ertelenmiş sayaç + trace olayı |
| `_strength_value(bar)` | `engine.py:1385` | `_signal_strength`'in **saf** yazımı |
| `_CarryPlan` / `_HeldDecision` / `_EntryDecision` | `engine.py` modül düzeyi | karar kayıtları |
| `tests/…/test_backtest_engine_describe_book.py::_drive_split` | test | altı yarıyı `_step` sırasında süren driver |

**`_step` (`:3425`) karakter karakter aynı** — `.carry` / `.held` / `.entry` çağıranları
etkilenmedi; `_ItemStepper` altı alan **kazandı**, hiçbirini kaybetmedi.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **GEÇEN BİR NEGATİF KONTROL, TESTİN İYİ OLDUĞUNU DEĞİL YOLUN HİÇ KOŞULMADIĞINI SÖYLER.**
   İlk iki negatif kontrolüm geçti; sebebi senaryo kümemin hiçbir bastırma yoluna
   ulaşmamasıydı. Üç sayaç için üç **ayrı** vaka gerekti: `direction_veto`,
   `date_blackout`, `volatility_strength`. Bir kontrol geçtiğinde **önce vakanın o yolu
   gerçekten koştuğunu** kanıtla.
2. **Salt-okur iddiası ancak FINGERPRINT ile kanıtlanır.** `_ledger_fingerprint`
   `dataclasses.fields(led)` üzerinden okur — elle sayılmış bir liste değil; sonradan
   eklenen sayaç kimse hatırlamadan kapsanır.
3. **`_phase_tail` scaling AYRILAMAZ (paylaşımlı koşu için).** Guard'ı `position` ve
   `len(led.trades) == trades_before_bar` okur; stacking bölümü ikisini de yazar
   (`:3091`, `:3098`, `:3220`, `:3221`). → **G12 bir sözleşme sorusudur**, tercih değil.
   **`_phase_tail`'e dokunma** — F3 de onu talep ediyor.
4. **Trail anchor describe yarısında ilerler ve bu BİLİNÇLİDİR** — piyasanın yüksek-su
   işareti, idempotent. Yeni bir describe yarısı yazarken *"bu bir booking mi yoksa
   piyasanın kaydı mı"* diye sor.
5. **`docs-history-guard` başlık YENİDEN ADLANDIRMASINI kayıt silme sanır** — çare
   **rebase** (§ADIM 61). Guard'ı kapatma, merge'i rebase'e çevir.
6. **E2E görsel kırmızısı çoğu zaman senin diff'in DEĞİLDİR.** `npm test` ve
   `npm run visual` **aynı compose stack'ini** paylaşır (`e2e.yml` tek `up` `:59`,
   `down -v` `:140`); bir flake retry'si satır ekler ve `fullPage` snapshot uzar.
   **TABANI GÜNCELLEME.** Önce: diff'in frontend dosyasına dokunuyor mu, ve alınan
   yükseklik denemeler arası **zıplıyor mu** (zıplıyorsa belirlenimsiz → layout değil).

## Sıradaki tasarım işaretleri — `C2` (E4b) ve ÖNÜNDEKİ İKİ İMZA

**`C2` = `ItemParticipant.settle` + `.finalize`, P10, `iter_portfolio`.**
Protocol bugün **write-only**: loop bir kaleme ne yaptığını söyleyemez. `settle` olmadan
book edilebilecek tek yer `entry()`'nin içidir — yani **arbitrasyondan ÖNCE**, arkasında
`PortfolioSnapshot` olmayan sermaye taahhüdü.

> **İKİ İMZA GEREKİR, İKİSİ DE AGENT TARAFINDAN KAPATILAMAZ:**
> **G9** = ADR-0002 §6/§8 amendment'ı — **`Accepted`** bir ADR'yi değiştirmek onu kabul
> eden imzayı ister (ADR §16: *"gate bir formalite değildir"*).
> **G13** = P10 end-of-data equity noktası: son `t_ms`'e **ekle** mi **katla** mı?
> Eklemek aynı ana iki nokta koyar ve **A5**'in by-construction sıralılık iddiasını kırar.

**`settle`/`finalize` ZORUNLU Protocol üyesi olmalı, `hasattr` ile YOKLANMAMALI** —
yoklama fail-open'dır, `settle`'ı unutan participant sessizce düz koşar. mypy yapısal
olarak zorlayamıyorsa **dur ve seam'i yeniden düşün** (plan `C2` stop condition).

**`C3` (adapter) ayrıca importer-allowlist kararı ister:** `portfolio_engine.__all__`
Protocol'ün tiplendiği **altı tipin hiçbirini** yeniden yayımlamıyor (`ItemBarStream`,
`ItemTickView`, `ItemIdentity`, `PortfolioSnapshot`, `ItemIntent`, `OpenPosition`), o
yüzden `execution/` dışındaki her implementasyon containment gate'in importer kontrolünü
**zorunlu olarak** kırmızıya çevirir — **bilinçli, gözden geçirilmiş** bir genişletme
ister. Ölçüm: `docs/audit/closure_e4_adapter_precondition_measurement_2026-08-17.md`.

**İmzalar yoksa: `C5` ve `R1` ARTIK AÇIK DEĞİL — ölçüldü (2026-08-17).**

- **`C5` (R-1 allocation plan revision pin) ZATEN İNMİŞ.** `readiness_check.py::_resolve_allocation`
  revision varsa `config`'i **frozen kayıttan** okuyor ve
  `tests/integration/test_allocation_revision_pin.py` byte-eşitliği + negatif kontrolü
  assert ediyor (**3 passed**). Plan bu kalemde **bayat**.
- **`R1` (TimingProvenance) `#734` ile İNDİ** — `domain/research_data/timing_provenance.py`,
  manifest ve Ready Check yüzeylerini tek `from_row` üzerinden birleştiriyor ve
  `execution_key` byte-identity'sini pinliyor.

**`R1`'in ARTIĞI açık ve ölçüldü:** `jobs/research_data.py::_pin_member` (`:558`-`:563`)
altı timing anahtarını **hâlâ elle** yazıyor ve `TimingProvenance`'ı import etmiyor — yani
value object var ama üçüncü kopya duruyor. Bugün onu tutan tek şey
`test_research_point_in_time_parity.py`'nin üç yönlü parity testi (kaymayı **yakalar**,
**imkânsız kılmaz**). Küçük ve net şekilli bir iş; **C7 manifest'e dokunurken birlikte
yapmak** iki kez aynı alanlara girmekten ucuz (insan kararı).

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Aşamalı split + her aşamada golden koş.** carry → doğrula → held → doğrula → entry.
  Tek seferde üçünü yazma; 474 satırlık bir closure'da hata nerede olduğunu söylemez.
- **Etki kümelerini mekanik karşılaştır** — eski fonksiyonun `led.*` / `_close(` / `_emit(`
  satırlarını çıkar, yeni çiftinkiyle **sıralı** karşılaştır. Bu, gözle okumanın
  yakalayamadığı sıra kaymasını yakalar.
- **`--no-cov` ekle** alt küme koşarken; **`pytest | tail` KULLANMA**.
- Golden dosyası için `git diff --exit-code` — ama **asıl kapı
  `test_backtest_engine_golden.py`'dir**, `tests/unit/oracles` **değil** (o dosya
  oracles'ta DEĞİL; sadece `--exit-code`'a güvenmek kapıyı hiç koşmamak olur).

## Paste-ready resume prompt

```
ENTROPIA V18 — PACKAGE C / SIRADAKİ SLICE
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

DURUM
  ADIM 71 (C1 / E4a) indi: describe/book split, 50 golden digest oynamadı.
  Base: main (`grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile numarayı DOĞRULA).
  Containment `future_dev`, blocker 1 (yalnız A-08), BLOCKED.

ÖN KOŞUL — SERT
  C2 yazacaksan: G9 (ADR-0002 §6/§8 amendment) ve G13 (P10 equity noktası) İMZALI MI?
  `docs/adr/0002-unified-clock-portfolio-simulation.md` §6/§8'de `settle`/`finalize`/P10
  var mı diye BAK. Yoksa C2'ye BAŞLAMA — insan kapısı.
  İmzasızsa: C5 ve R1 KAPALI (ölçüldü 2026-08-17) — C5 zaten inmişti, R1 #734 ile indi.
  Açık kalan: _pin_member'ı TimingProvenance'a bağlamak (bkz. §Sıradaki), ya da P paketi.

YAPILACAK (C2, imzalar varsa)
  portfolio_engine.py: `settle` + `finalize` ZORUNLU Protocol üyesi (hasattr YOK),
  PHASE_ORDER'a P10, `iter_portfolio` generator + `run_portfolio` iki satırlık wrapper.
  _ScriptedParticipant'a no-op çift ekle. Faz sırası testini BİLEREK güncelle.

PAZARLIKSIZ
  engine.py / manifest.py / worker / containment gate DOKUNMA.
  ENGINE_VERSION DEĞİŞMEZ. Golden 50 digest BAYT BAYT AYNI kalmalı.
  Oracle dosyalarını ADIYLA pinle, SAYIYLA değil.

TEST
  cd backend
  uv run pytest tests/unit/test_backtest_engine_golden.py tests/unit/oracles \
                tests/unit/test_backtest_engine_describe_book.py -q --no-cov
  git diff --exit-code -- tests/unit/engine_golden_digests.json    # 0 ZORUNLU
  Sonra tam suite + ruff + ruff format + mypy + openapi --check + repository_facts --check.
  ALT KÜME KOŞARKEN --no-cov. `pytest | tail` KULLANMA.
  Test EKLEDİYSEN repository_facts'i TAZELE (ADIM 60 dersi).

DİKKAT
  Yeni bir describe yarısı yazarken: yazdığı her şeyi karar nesnesine ERTELE.
  Her assertion'ı NEGATİF KONTROLDEN geçir — ve kontrol GEÇERSE önce vakanın o yolu
  gerçekten koştuğunu kanıtla (ADIM 71 dersi).
  main'i içeri alırken MERGE DEĞİL REBASE (docs-history-guard başlık yeniden
  adlandırmasını kayıt silme sanır).

COMMIT / PR
  DAL: feat/closure-c2-participant-settle-finalize
  commit: feat(closure-c2): <konu>
  MERGE ETME (kullanıcı açıkça istemedikçe). Kapanış ritüeli 6 madde.

FINAL RESPONSE — [ORTAK ŞABLON] +
  Containment status / Containment gate yeşil mi / Golden digest oynadı mı
DUR.
```
