<!-- doc-status: historical -->

# ADIM 116 landed — unified Result'ın provenance'ı sevk edildi; sıradaki hamle HÂLÂ bir imza, kod değil

## Neredeyiz

`main` + PR #840. Taban `a57e552`, dal **rebase** sonrası `8a1d52d` (ADIM 115 = #839) üzerine
oturur. Migration **YOK** · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`** · kabul borcu tavanları **el değmedi**
(54/6 · A1 B21 C6 D32) · blocker **1** (yalnız A-08), **BLOCKED**.

`C4` (#799/#805) dalın **koştuğunu**, ADIM 115 (#839) o dalın **arbitrajını** pinlemişti.
ADIM 116 üçüncü soruyu kapatır: o koşunun ürettiği Result **kendisinin ne olduğunu söyler mi?**
Söylemiyordu — ve şimdi söylüyor.

## Bu slice ne bıraktı

**Kapatılan boşluk:** `portfolio_mode` `unified_clock`'u **TEK** şeye bağlar (Result'ın
manifest snapshot'ındaki `portfolio_simulation` bölümü) ve o bölümü **üretimde hiçbir şey
yazmıyordu**; `build_portfolio_manifest`'in üretim çağıranı **hiç yoktu**. Paylaşımlı saatte
ko-simüle edilmiş her Result **`unknown`** okunuyordu. **Okuyucu tamdı; yazıcı yoktu.**

**Görevin öncülü yarı bayattı:** `project_portfolio_run`'ın çağıranı **vardı**
(`CLAUDE.md`'nin *"sıfır importer"* bloğu ADIM 59'dan kalma) → **duplicate fix yazılmadı.**

### Yeniden kullanım çapaları (birebir adlar)

| Sembol / dosya | Ne için |
|---|---|
| `execution/portfolio_projection.py::build_portfolio_provenance` | bölümü kuran **seam**; bilerek `execution/` **İÇİNDE** |
| `execution/portfolio_projection.py::_allocation_provenance` | doc 13 §13 allocation kaydı; **`plan=None` gerekçesi docstring'inde** |
| `execution/portfolio_projection.py::MissingPinOrdinalError` | atanmamış pin ordinal'i = fail-closed |
| `execution/portfolio_projection.py::PinnedItem.pin_ordinal` | **opsiyonel**; projeksiyon okumaz, provenance ister |
| `execution/provenance.py::money_str` | manifest'in **kanonik** para yazımı (eskiden `_money_str`) |
| `execution/provenance.py::build_portfolio_manifest` | artık `ConflictPolicyRule` **veya ham token** alır |
| `jobs/backtest_engine.py::_UnifiedOutcome` | output + provenance **birlikte** taşınır |
| `repositories/backtest.py::_snapshot_manifest` | bölümü snapshot'a **kopyalayarak** pinler |
| `repositories/backtest.py::PORTFOLIO_SIMULATION_KEY` | okuyucu ile yazıcının **tek** sabiti |
| `tests/integration/test_unified_portfolio_provenance.py` | 10 case; uçtan uca round trip |

### Pazarlıksız olarak öğrenilenler

1. **BİR SINIFLANDIRICI, KANITI KİMSE YAZMIYORSA SESSİZCE "unknown" DÖNER.** Sözleşme
   doğruydu, testliydi; **yazıcı** yoktu ve hiçbir şey kırmızı değildi.
2. **NEGATİF KONTROL KÜMESİ DE EKSİK OLABİLİR.** İlk küme **iki** containment dosyası
   taşıyordu; ağaçta **ALTI** per-modül importer guard'ı (`_imports_provenance` ·
   `_imports_portfolio_ledger` · `_imports_intents` · `_imports_arbitration` ·
   `_imports_attribution` + unified clock) **artı iki gate** var. Yeni parti başlarken
   **hepsini** kümeye koy.
3. **İMZALI BİR ALLOWLIST GENİŞLETİLMEZ — IMPORT ETMEKTEN VAZGEÇİLİR.** İlk commit
   `resolve_policy`'yi import edip arbitration'ın **dördüncü** importer'ı oldu. Çözüm:
   token'ı `provenance` **kendisi** çözer (zaten onun işi).
4. **TAM SUITE, ALT KÜMENİN GÖREMEDİĞİNİ GÖRÜR** (ADIM 76'nın birebir tekrarı) — bir CI turu.
5. **NEGATİF KONTROL, KENDİ TESTİNDEKİ TOTOLOJİYİ YAKALAYABİLİR.**
   `ordinals == sorted(ordinals)` **bedavadır** (`pinned_items_from_identities` zaten sıralar).
6. **BİR NC KIRMIZI VERDİĞİ HÂLDE REDDEDİLEBİLİR** — *doğru sebep, yanlış kapsam* (NC-3) ve
   *RUN'ı düşürüp assertion'ı izole edemeyen kusur* (NC-4).
7. **BİLDİRİMİN EXIT CODE'UNA GÜVENME**, `ps` ile **eski koşuyu** ara, **cwd'yi doğrula** —
   üçü de bu oturumda sahte kırmızı/yeşil üretti.

## Ölçülmüş, kapatılmayan sınır

* **`manifest_hash` adjudicated:** unified Result'ta snapshot hash'i saklanan belgenin
  **tamamını kapsamaz** (bölüm kendi hash'ini taşır). İki yönde pinli, bilerek.
* **`data_revisions` per-item pinlenMEDİ** — manifest böyle bir harita taşımıyor; run düzeyi
  veri provenance'ı (`tick_data`, `data_time_context`) aynı manifest'te zaten var.
* **`divergences` boş = ölçüm yokluğu, anlaşma değil** — donmuş `derived_amounts` manifest'te
  yok → `plan=None`.
* **Frontend'e dokunulmadı, bilerek** — `unified_clock` zaten temsil edilebilirdi.
* **Eski Result'lar `unknown` KALIR ve KALMALIDIR** — geri doldurma **yok** (kanıt yok).

## Sıradaki hamle — KOD DEĞİL, İMZA (değişmedi)

`G8` (#559) · `G14` (#544) hâlâ **KARARSIZ**; `G11`+`G12` → `C6`; `G15` (leg 3); `G10` hiç
talep edilmedi. Sonra `C6`, ön koşul 15–18 ve 22, en son `C9`.
Sıra ve gerekçe: `docs/audit/final_closure_delta_audit_2026-08-25.md` §10.

## Paste-ready resume prompt

```
ENTROPIA — oturum devamı (ADIM 116 sonrası)

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT):
  git fetch && git log --oneline origin/main -6
  gh pr list --state all   (ya da mcp__github__list_pull_requests)
Sonra oku: docs/ADIM116_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (§Next) →
docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*.

NEREDEYİZ: ADIM 116 (PR #840) unified portfolio Result'ının PROVENANCE'ını sevk etti.
`build_portfolio_provenance` (execution/portfolio_projection.py) `portfolio_simulation`
bölümünü kurar; `create_result` onu Result'ın manifest SNAPSHOT'ına kopyalayarak pinler;
`portfolio_mode`'un `unified_clock` dalı artık GERÇEK bir Result'tan ulaşılabilir.
Containment KALDIRILMADI (`SHARED_ALLOCATION_STATUS` = `future_dev`).

PAZARLIKSIZ:
- İmzalı importer allowlist'ini GENİŞLETME. Contained bir modüle (execution.provenance,
  execution.arbitration, …) `execution/` DIŞINDAN import ekleme; seam'i `execution/` içinde
  kur. Ağaçta ALTI per-modül importer guard'ı + iki gate var — negatif kontrol kümene
  HEPSİNİ koy.
- `manifest_hash` RUN'ın admission hash'idir, yeniden türetilmez (doc 15 §7/§8.4).
- Yeni bir provenance alanı eklerken: arkasında sevk edilmiş alan yoksa `[]`/boş YAYIMLAMA
  (ADIM 66) — yokluk boşluktur, beyan değil.
- Eski Result'ları geri doldurma; `unknown` doğru cevaptır.

SIRADAKİ HAMLE KOD DEĞİL İMZA: `G8` (#559) · `G14` (#544) · `G11`+`G12` (→ `C6`) · `G15`.
Sıra: docs/audit/final_closure_delta_audit_2026-08-25.md §10.

YEREL DOĞRULAMA (container ÇIPLAK başlayabilir):
  cd backend && uv sync --all-extras
  Postgres 16 kur + başlat (root initdb yapamaz → `su postgres`), `entropia` DB'sini yarat
  ve `LC_ALL=C.UTF-8 PYTHONUTF8=1 uv run alembic upgrade head` koş — contract testleri
  MİGRATE EDİLMİŞ DATABASE_URL DB'si ister (yoksa `relation "human_users" does not exist`).
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
  TUZAK: `pytest | tail` KULLANMA (exit code tail'in olur); çıktıyı dosyaya yaz, $?'i AYRI oku;
  arka plan bildiriminin exit code'una GÜVENME; koşmadan önce `ps -eo pid,cmd | grep bin/pytest`
  ile eski bir koşu kalmadığını doğrula (deadlock = sahte kırmızı); cwd `backend` OLMALI.
```
