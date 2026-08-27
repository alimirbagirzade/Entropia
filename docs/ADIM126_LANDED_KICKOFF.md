<!-- doc-status: current -->

# ADIM 126 — `C7` (A16 manifest split + A15 bump) İNDİ · sıradaki kalem

> Bu belge **canlı** kickoff'tur. Bir önceki (`docs/ADIM125_LANDED_KICKOFF.md`) `historical`
> işaretlendi. Sayısal otorite **bu belge değil** —
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).

---

## Nerede duruyoruz

`C6` ADIM 125'te kapandı. `C7` bu slice'ta indi: **A16** (manifest policy provenance +
çözülmüş sleeve tutarları + FX ref'leri) ve **A15'in bump'ı**. `SHARED_ALLOCATION_STATUS`
hâlâ `future_dev`; **lift olmadı**. Blocker DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 126.

---

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Ne | Nerede |
|---|---|
| Dört policy sürümü, **literal** (import DEĞİL) | `domain/backtest/manifest.py::ENGINE_ALLOCATION_POLICY_VERSION` · `::CLOCK_POLICY_VERSION` · `::ARBITRATION_POLICY_VERSION` · `::MARK_STALENESS_POLICY` |
| Bloğu tek yerden kuran | `domain/backtest/manifest.py::_portfolio_policy` — manifest gövdesinde **ve** `execution_content`'te |
| Çözülmüş tutarlar + FX ref'leri | `application/commands/readiness_check.py::_resolve_allocation` → `capital_mode["derived_amounts"]`, `["settlement_currencies"]` |
| İki yazımın parite kapısı | `tests/unit/test_a16_manifest_policy_parity.py` |
| Admission wiring kanıtı (gerçek Postgres) | `tests/integration/test_allocation_manifest_provenance.py` |
| **`C9`'u ikinci bump'a zorlayan guard** | `tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_lifting_containment_requires_a_second_engine_version_bump` |

---

## `C9`'a devreden ve PAZARLIKSIZ olan tek şey

**`ENGINE_VERSION` TEKRAR BUMP EDİLMELİDİR** — lift commit'inin **kendisinde**.

`C7`'nin bump'ı A15'i **kapatmaz**: o bump A16'nın *kayıt* değişikliği için harcandı ve
hiçbir davranış değiştirmedi (50 golden'ın 49'u bayt bayt aynı). A15'in koruduğu kusur
contained-era bir Result'ın **unified-clock** bir re-RUN için idempotent yeniden
kullanımıdır; onu yalnız lift'in kendi kayması kapatır. Guard yukarıda; bayrağı çevirip
bump etmezsen **kırmızı** verir (NC-5'te ölçüldü). Bump ederken **golden baseline'ı aynı
commit'te yeniden üret**:

```
cd backend && uv run --extra dev python -m tests.unit.test_backtest_engine_golden
```

---

## Ön koşul defterinin durumu

`docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md` §2
(`doc-status: historical`, kolon `0f0651d`'de **DONMUŞ** — satırlara tarihli not eklenir,
`❌` çevrilmez).

Satır **22** (A15 + A16 + A19 + A22) **KIRMIZI KALIR**: A16 indi, **A15 lift'i bekler**,
**A19 ve A22 el değmedi**. Kalan kırmızılar: **17** (OD-2 mark policy — `MARK_STALENESS_POLICY`
hâlâ `"undefined_pending_od2"`), **18** (`CONTENTION_SELECTION_STATUS` flip), **21** (#559 —
insan), **22**.

---

## Yöntem (bu slice'ta işe yarayan)

- **Görevin öncülünü ölç, kabul etme.** Bu slice'ta dört öncülden üçü çürüdü (§17 yok;
  A15 testi zaten vardı; OpenAPI kırmızı vermedi). Ölçüm ucuz, yanlış öncül pahalı.
- **Bir NC yalnız kırmızı vermez, NEYİN yeşil kaldığını da söyler.** NC-2 burada bir
  **eksik assertion** buldu; NC-1 parite testinin neden var olduğunu ölçtü.
- **Yamayı bellekten geri yaz** (`git checkout` DEĞİL — ağaçta commit'siz iş var) ve geri
  yazmanın **bayt bayt** olduğunu assert et.
- **`manifest.py` `execution/`'dan import EDEMEZ.** Sabiti yeniden yaz + testte parite kur;
  yorumlarda modülü **YOL** biçiminde yaz (noktalı biçim taramayı tetikler).
- Alt küme koşarken **`--no-cov`**; exit code'u **ayrı** oku.

---

## Paste-ready resume prompt

```
ENTROPIA — C7 İNDİ (ADIM 126: A16 manifest + A15 bump). Sıradaki kalem C9 DEĞİL.

ÖNCE DOĞRULA (handoff BAYAT VARSAYILIR — bu prompt da öyle):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3
  A16 yerinde mi:
    grep -c "_portfolio_policy" backend/src/entropia/domain/backtest/manifest.py   # >= 3
    grep -n "ENGINE_VERSION = " backend/src/entropia/domain/backtest/manifest.py

DURUM: SHARED_ALLOCATION_STATUS = future_dev (lift OLMADI). Blocker 1 (yalnız A-08), BLOCKED.
  Ön koşul defterinin kırmızıları: 17 · 18 · 21 · 22.

SIRADAKİ KALEMLER (sıra ürün sahibinin):
  - Ön koşul 17: OD-2 mark policy'yi UYGULA, sonra MARK_STALENESS_POLICY'yi
    "undefined_pending_od2"dan çevir. DİKKAT: o literal artık execution_content'te →
    çevirmek TÜM execution_key'leri kaydırır, yani kendi ENGINE_VERSION bump'ını ister.
  - Ön koşul 18: CONTENTION_SELECTION_STATUS flip (arbitration.py).
  - C9 (lift): EN SONDA, ve ADR §16 Gate 2 (G10) AYRI bir insan kapısıdır —
    2026-08-26'da "B — ERTELE" imzalandı (red değil, yeniden talep bekliyor).

C9'A ÖZEL, PAZARLIKSIZ: ENGINE_VERSION'ı lift commit'inde TEKRAR bump et. C7'nin bump'ı
  A15'i KARŞILAMAZ (kayıt değişikliği için harcandı, davranış değişmedi). Guard:
  test_lifting_containment_requires_a_second_engine_version_bump — bayrağı çevirip bump
  etmezsen kırmızı. Golden'ı AYNI commit'te yeniden üret.

YASAKLAR: manifest.py'ye execution/'dan import EKLEME (imzalı allowlist iki modül adlandırır;
  değerler bilerek yeniden yazıldı, parite tests/unit/test_a16_manifest_policy_parity.py'de).
  shared_shapes.py'ye İMZASIZ satır ekleme. engine.py::conflict_downgraded_from_net DOKUNULMAZ.
  #544/#559 human-only.

TUZAKLAR: _strategy_payload varsayılanı next_candle_open = G11 ihlali (paylaşımlı fixture'da
  execution={"entry_timing": "current_candle_close", ...} geç). Test EKLEYEN slice
  docs/generated/repository_facts.* dosyalarını TAZELEMELİ (collection sayısı oynar):
  cd backend && uv run python ../scripts/generate_repository_facts.py --root ..
  CLAUDE.md'de ENGINE_VERSION'ı ANAN tarihsel satırlar "(o gün)" ile hedge edilir — kapının
  kendi escape hatch'i budur, geçmişi yeniden yazma.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  alt küme koşarken --no-cov; her yeni assertion için AYIRT EDİCİ negatif kontrol
  (yalnız hedef kırmızı, mevcutlar yeşil); GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.

ORTAM: Postgres :5432 (entropia/entropia). backend/.venv yoksa `uv sync --all-extras`.
  Tam backend suite 10 dk'yı AŞAR: arka planda --no-cov ile tek çağrıda koştur, ortada KESME.
```
