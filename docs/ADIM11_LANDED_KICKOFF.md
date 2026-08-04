# ADIM 11 landed — kickoff for the next slice

> **Bu belge STALE-BY-DEFAULT'tur.** Herhangi bir iddiasına dayanmadan önce
> `git fetch && git log --oneline origin/main -6 && gh pr list --state all && gh issue list`
> ile doğrula. Aşağıdaki her SHA/sayı 2026-08-04 kapanışında **ölçüldü**, tahmin edilmedi.

## Nerede duruyoruz

| | |
|---|---|
| `main` | **`061d6d7`** — PR #538 merge (2026-08-04T12:35Z), CI **6/6 pass** (Backend 47m22s) |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` (değişmedi) |
| Alembic head | `0043_i08_registry_strategy_fks` (tek head, değişmedi) |
| OpenAPI | 196 operation / 151 schema (değişmedi — ADIM 11 kod değiştirmedi) |
| Capability matrix | **62 satır / 22 `future_dev` / 14 alan** (Python↔TS parity byte-exact, yeşil) |
| Son üç slice | ADIM 9 = PR #531 · ADIM 10 = PR #537 · **ADIM 11 = PR #538** |

## ADIM 11 ne bıraktı — reuse anchor'ları (tam sembol adlarıyla)

Tek çıktı: **`docs/audit/capability_matrix_canonical_adjudication.md`** (443 satır). Kod
değişmedi. Aşağıdakiler o denetimin **ölçülmüş** dayanakları — bir sonraki slice bunları
yeniden ölçmek zorunda değil, ama iddiaya dayanmadan önce dosya:satır'ı açsın.

### Enforcement zinciri (sağlam, dokunma)

* `domain/backtest/capabilities.py::CAPABILITY_MATRIX` — kanonik tablo; `CapabilityOption`
  dataclass'ı; `FUTURE_DEV_OPTIONS`, `MATRIX_FIELD_PATHS`, `option_status`,
  `future_dev_selections`, `capabilities_are_modelled`.
* **Reachability reader'ları** — `_read_scaling_timeframe`, `_read_scaling_timeframe_mode`,
  `_read_filter_types`, `_read_opposite_hedge`, `_read_limit_price_rule`,
  `_read_formula_type`. Kural: **çökmüş bir alt ağaçtaki değer SEÇİM DEĞİLDİR** ve boş tuple
  döner. Yeni bir yüzey eklerken bu kuralı kopyalama, reader'dan geçir.
* Engine choke point: `domain/backtest/engine.py:1438` — `_open` içinde
  `if not capability_ok or not sizing_ok or not leverage_ok or not strength_ok: return None`.
  Her giriş yolu (flat entry, conflict stack/replace, scaling ladder) buradan geçer.
* Ready Check: `domain/readiness/validators.py:434-447` — seçilen her `future_dev` opsiyonu
  için **ayrı** `STRATEGY_CAPABILITY_NOT_IN_BUILD` BLOCKER'ı.
* Generator + parity: `backend/tools/export_capability_matrix.py::render` →
  `frontend/src/lib/engineCapabilityMatrix.generated.ts`; pin
  `tests/unit/test_capability_matrix.py:490-506` **tam dosya string eşitliği** (byte-exact).
  `dependency` metnini değiştirirsen mirror'ı yeniden üret, yoksa CI kırmızı.

### Kırık olan (issue'ları açık)

* `frontend/src/components/StrategyGraphForm.tsx` — generated matrix'i **hiç import etmiyor**;
  kendi `SelectField`'ı (`:122-168`) `capabilityField` parametresi taşımıyor. 11 `future_dev`
  satırı buradan sıradan seçenek olarak çıkıyor. → **#539 (CRITICAL)**
* `frontend/src/lib/strategyGraph.ts::MODELLED_FILTER_TYPES` — engine allow-list'inin elle
  bakımlı kopyası, parity testi yok. → #539
* `tests/unit/test_capability_matrix.py::_SCHEMA_FIELDS` — 14 alanın 9'unu kapsıyor. → #540
* `domain/allocation/rules.py:220-227` + `frontend/src/lib/allocation.ts:231` — NET için
  containment sonrası **karşı-olgusal** açıklama. → #544 (text-only kısmı bağımsız yapılabilir)

## Sıradaki tasarım işaretçileri

**Kod tarafında en yakın kalem: #539 (C-1).** Presentation-only, hiçbir ürün kararına bağlı
değil, denetimin en yüksek değerli düzeltmesi. Yapılacak: `StrategyGraphForm`'un
`SelectField`'ına `StrategyConfigForm.tsx:126-207`'deki `capabilityField` mekanizmasını
ver (blockedValues mevcut değeri hariç tutar, `disabled`, `— not available in this build`
son eki, `dependency` notu `aria-describedby` ile), üç alanı bağla
(`scaling_logic.timeframe`, `scaling_logic.timeframe_mode`,
`restrictions_filters.filters.filter_type`) ve **reachability'ye göre gate'le**
(`scaling.enabled` / `filter.enabled`) — değere göre değil; değere göre karar vermek #533'ün
kusurudur.

**Ürün kararı bekleyenler insana aittir, agent kapatamaz:** #542 (signal-strength
taksonomisi — aktif satırı da etkiliyor), #543 (correlation vs regime), #544 (NET), #545
(ikinci dataset pin'i + stale-quote eşiği), #546 (hangi filtre koşulları + action uzayı).
Bunlar açık **#535** ile aynı sınıf kanon↔şema sapmasıdır ve birlikte karara bağlanmalı.

**#547 (increasing_by_layer) implementasyonu P-7 kararına bağlı** ve `ENGINE_VERSION`
değerlendirmesi zorunlu — karar verilmeden başlama.

## REUSE listesi

| İhtiyaç | Nereden al |
|---|---|
| Bir option'ın gerçekten çalışıp çalışmadığı | `capabilities_are_modelled` / `future_dev_selections` — call site'ta yeniden türetme |
| UI'da bir option'ı devre dışı bırakma | `StrategyConfigForm.tsx::SelectField` + `capabilityField` (kopyalanacak referans implementasyon) |
| Ready Check blocker'ı | `validators.py:434-447` deseni — mesaj + remediation `CapabilityOption`'dan gelir |
| Tick bağımlılığı | `execution/fills.py::tick_data_required` (`intrabar_policy.tick_policy == "require"`) |
| Shared allocation'ın çalışabilirliği | `domain/allocation/capability.py::shared_allocation_is_executable` — call site'ta yeniden türetme |
| Denetim dokümanı biçimi | `docs/audit/capability_matrix_canonical_adjudication.md` ve `docs/audit/strategy_conflict_matrix_closure.md` |

## Çalışma yöntemi (bu slice'ta işe yarayan)

1. **Kanonu önce oku, koda sonra bak.** Bu denetimin en değerli üç bulgusu (D-7, D-9, D-10)
   kanon ile şemanın karşılaştırılmasından çıktı, kod okumaktan değil.
2. **Read-only subagent'lar kanıt üretsin, hüküm ana oturumda verilsin.** Dört subagent
   kullanıldı; **üç sonucu geçersiz kılındı** ve bir sembol adı (`_ReferenceLeg` →
   `_ReferenceSeries`) yanlıştı. Disposition değiştiren her iddiayı kendin yeniden ölç.
3. **Davranış iddiasını probe ile üret.** "Bu satır aslında future_dev olmalı" hipotezi ancak
   gerçek engine üzerinde iki koşu karşılaştırılarak çürütülebildi.
4. **Kanonik boşlukta formül uydurma.** Boşluğu adlandır, `canonical_gap` de, ürün kararına
   bağla.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 12

ROL: Entropia V18 üzerinde çalışan kıdemli principal engineer ve release-closure sorumlusu.
Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini current origin/main
üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile kapatmak, sistemi geriletmemek.

ZORUNLU BAŞLANGIÇ
1. git fetch --all --prune
2. git status --short — temiz değilse DUR, hiçbir şey silme/stash etme
3. git switch main && git reset --hard origin/main
4. Current main SHA + açık PR/issue snapshotını kaydet
5. Önceki adımın PR'ının merge edildiğini doğrula; edilmediyse DUR
6. Dokunacağın alanın docs/CODEMAPS/ haritasını ve gerçek çağrı zincirini oku
7. Eski README/CLAUDE.md/handoff/kickoff/backlog iddiasını current truth SAYMA
8. Kusuru önce test/probe ile yeniden üret; üretilemiyorsa kod yazma

BAŞLANGIÇ DURUMU (2026-08-04 kapanışında ölçüldü — DOĞRULA)
- main = 061d6d7 (PR #538 merge), CI 6/6 pass
- ENGINE_VERSION = backtest-engine-v18-same-candle-entry-exit
- alembic head = 0043_i08_registry_strategy_fks (tek head)
- capability matrix = 62 satır / 22 future_dev / 14 alan, Python↔TS parity byte-exact
- Açık issue: #514 (a11y, insan kapatır) · #533 · #534 · #535 · #536 · #539–#547
- Tam kayıt: docs/PROJECT_HISTORY.md §ADIM 11 · docs/ADIM11_LANDED_KICKOFF.md
  · docs/audit/capability_matrix_canonical_adjudication.md

BU ADIMIN İŞİ
Kullanıcı brief vermediyse varsayılan olarak #539'u (C-1) al: engine capability matrix'ini
StrategyGraphForm'a bağla. 22 future_dev satırının 11'i (scaling_logic.timeframe ×10,
scaling_logic.timeframe_mode, restrictions_filters.filters.filter_type ×4) formda sıradan
seçilebilir seçenek olarak render ediliyor; sunucu run'ı reddediyor ama kullanıcı bunu ancak
Ready Check'te öğreniyor. #539'daki ölçülmüş probe çıktısını önce yeniden üret.

TAVİZ VERİLEMEZ
- Presentation-only: route path, react-query key, OCC token (If-Match / expected_*_version /
  X-*-Version), Idempotency-Key, hook, SSE taksonomisi, API çağrısı, lib/*.ts data logic
  DEĞİŞMEZ; app/nav.ts NAV/ALL_NAV_ITEMS birebir kalır
- v18 mockup (docs/spec/index_guncellenmis_duzeltilmis_v18.html) görsel referanstır
- CAPABILITY_MATRIX ve hiçbir status literal'i değişmez; hiçbir capability aktif edilmez
- Reachability'ye göre gate'le (scaling.enabled / filter.enabled), değere göre DEĞİL —
  değere göre karar vermek #533'ün kusurudur
- Kaydedilmiş bir future_dev değeri sessizce silinmez/yeniden yazılmaz; seçilebilir kalır
  (pin: frontend/src/test/engineCapabilityMatrix.test.tsx:107-125)
- Kanonik boşlukta formül/öncelik/time-ordering/ürün kararı uydurulmaz
- Başarısız test varken Complete/Done yazılmaz

DOĞRULAMA
cd frontend && npm run typecheck && npx vitest run --no-file-parallelism <targeted>
  (vitest için --no-file-parallelism ZORUNLU; node_modules yoksa önce npm ci —
   ilk koşudaki ERR_MODULE_NOT_FOUND test hatası değil)
cd backend && uv run pytest -q --no-cov tests/unit/test_capability_matrix.py
  (alt küme koşarken --no-cov ekle; tam suite tek çağrıda koşulur ve ortada öldürülmez)

PR DİSİPLİNİ
Branch fix/<slug>, conventional commit, AI attribution YOK, tek PR, ilgisiz refactor yok.
Claude merge etmez/tag atmaz. PR sonunda raporla: base SHA, branch, commit, PR, changed
behavior, unchanged boundaries, targeted tests, full-suite exit code, migration/OpenAPI/
codemap etkisi, kalan risk, sonraki tek adım.
```
