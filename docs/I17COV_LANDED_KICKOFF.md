<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# I-17-COV landed — sıradaki slice için kickoff

**Baseline:** `test/i17cov-acceptance-id-gaps` (PR TBD) · **test-only: `src/` değişmedi ·
migration YOK · alembic head `0039_backtest_run_cancellation` · ENGINE_VERSION bump YOK.**

> **STALE-BY-DEFAULT.** Bu dosyaya güvenmeden önce `git fetch && git log --oneline origin/main -6 &&
> gh pr list --state all` çalıştır; PR'ın gerçekten merge olduğunu ve **Backend CI'ının yeşil
> olduğunu** doğrula. Bu dosya `docs/I17_LANDED_KICKOFF.md`'nin yerine geçer (o dosyanın
> "Sıradaki adaylar §3" listesi artık kapalı — bkz. aşağıdaki tablo).

---

## Nerede duruyoruz

```bash
python3 docs/audit/acceptance_id_scan.py
```

**173/215 (%80)** · kapsam içi (doc 02/03/04/05/07/10) **118/130** · doc 05 Trade Log **COMPLETE**.
I-17 kapanışında sırasıyla 163/215 ve 108/130 idi.

Tam kayıt: `docs/PROJECT_HISTORY.md` §I-17-COV · denetim artefaktı
`docs/audit/acceptance_id_map.md` (**§H** = bu dalga, **§E.2–§E.4** = açılan üç kusur,
§C = doc 06/08/09 audit-local ID'leri).

---

## Bu slice'ın bıraktığı REUSE çapaları (birebir sembol adları)

| Çapa | Ne için |
|---|---|
| `backend/tests/integration/test_acceptance_esp_package_gaps.py` | ESP/paket kabul-ID deseni: `_trusted_esp()` (create→validate→activate zinciri), seed Family testi, katalog filtresi |
| `backend/tests/integration/test_acceptance_agent_parity_gaps.py` | Agent-parity deseni: `_draft_and_save()`, `_import_signal()`, insan/agent aynı komut hattı kıyası |
| `tests/integration/test_backtest_persistence.py::_ready_composition` + `_e2e_bars` | Gerçek run üreten hazır fixture (AT-24 bunu kullandı) |
| `tests/integration/test_strategy_integration.py::_valid_payload` | Tam geçerli StrategyConfig payload'ı — cross-module import ile kullanılabilir |
| `frontend/src/test/presentationState.test.tsx::writeRequests` | "hiç yazma isteği yok" assertion deseni (fetch mock üzerinden method filtresi) |
| `frontend/src/test/preCheckUntrustedStrings.test.tsx` | XSS/layout payload seti + "hiç element yaratılmadı" assertion'ları |
| `docs/audit/acceptance_id_scan.py` | Ölçümü yeniden üreten tarayıcı (rapor, gate değil) |

---

## Sıradaki adaylar (öncelik sırasıyla)

**1. `fix/pc19-soft-deleted-esp-must-not-resolve` — KUSUR, en yüksek öncelik.**
Soft-delete edilmiş bir ESP **yeni Pre-Check'te hâlâ çözülüyor**.
`commands/deletion.py::_soft_delete_preflight` yalnız `work_object` ve `rationale_family`
dallarını tanıyor; `queries/esp.py::resolve_embedded_dependency` sadece registry `trust_state`'ine
bakıyor, kökün `deletion_state`'ine hiç bakmıyor — üstelik fonksiyonun **kendi docstring'i**
(`queries/esp.py:228`) "deprecated / soft-deleted registry entry -> RESOLVER_NOT_ACTIVE" diyor.
Yapılacak: soft-delete registry'yi de kapatsın (veya resolve `deletion_state`'i okusun) +
`test_acceptance_esp_package_gaps.py`'deki PC-19 testinin ikinci cümlesini ekle ve HOLE yorumunu
kaldır. Aynı slice'ta **ESP-17**'nin eksik preflight'ı da değerlendirilebilir (aktif trusted
resolver'ın soft-delete'i bloklanmıyor).

**2. `feat/gateway-strategy-and-signal-tools`.** `ToolName`'de `strategy.*` ve `trading_signal.*`
yok; AT-21/TS-20'nin "via Tool Gateway" cümlesi karşılıksız. S4'ün allocation/trade_log deseni
(`test_gateway_parity_s4.py`) birebir kopyalanabilir.

**3. `feat/esp19-export-carries-contract-facts`.** `export_package` manifest'i yalnız paket
revision'ından kuruluyor; `runtime_adapter` + `evidence` `embedded_resolver_contract`'ta duruyor.

**4. `AOS-12` — `KIND_REVISION_MISMATCH`** (kendi branch'i: `feat/aos12-kind-revision-mismatch`).

**5. Kalan 12 in-scope etiketsiz ID.** `AT-04/06/07`, `TS-10`, `PC-01/02/15/16/18`, `RF-13/18`.
Bunlar **gerçek boşluk listesinde hiç yoktu**; çoğu izlenebilirlik borcu (test var, ID'yi anmıyor —
ör. `AT-04` → `test_backtest_persistence.py::test_worker_fails_closed_on_instrument_mismatch`,
§D'de adjudicated). Her etiketi **testi okuyarak** doğrula.

**6. ID sütunsuz sayfalar.** Doc 01/11/12/13/15/17/19/20 hâlâ kabul tablolarını ID'siz yayımlıyor;
doc 06/08/09'un `docs/audit/` çözümü aynen uygulanabilir.

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce ampirik doğrula, sonra yaz.** Brief'in listesindeki bazı ID'lerin (ör. CP-05) aslında
  testi vardı — sadece ID'yi anmıyordu; bazılarınınsa (PC-19) implementasyonu spec'i tutmuyordu.
- **Kusuru probe ile kanıtla.** PC-19 için tek kullanımlık bir probe testi yazıldı, sonucu
  `AssertionError` ile dışarı taşındı, sonra dosya silindi. İddia böyle kanıtlanır; docstring'e
  bakarak "çalışıyordur" denmez.
- **Kısmi satırı kısmi olarak etiketle.** PC-19/ESP-19/TS-20 testleri hangi cümleyi kanıtladıklarını
  ve hangisini kanıtlamadıklarını docstring'de sayıyor; eksik yarı §E'de kayıtlı.
- **Yeni dosya = gate-free.** Testleri Bash heredoc ile YENİ dosya olarak yaz (GateGuard fact-force
  yalnız mevcut dosya düzenlemesinde tetikleniyor).
- **Ortam.** Backend: `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_i17cov`,
  alt küme koşarken `--no-cov`. Frontend: worktree'de önce `npm ci`, sonra
  `npm run coverage -- --no-file-parallelism`. Backend venv'i ilk kullanımda `uv sync --extra dev`
  ister — bunu **suite koşmadan önce** yap.

---

## Paste-ready resume prompt

```
Entropia — PC-19 kusuru: soft-delete edilmiş ESP yeni Pre-Check'te hâlâ çözülüyor (I-17-COV takibi).

Session START + git doğrulama: git fetch && git log --oneline origin/main -6 && gh pr list --state all.
I-17-COV PR'ının (test/i17cov-acceptance-id-gaps) merge olduğunu ve Backend CI'ının YEŞİL olduğunu doğrula.

Bağlam: docs/audit/acceptance_id_map.md §E.2 + docs/PROJECT_HISTORY.md §I-17-COV.

KUSUR (ampirik doğrulandı, 2026-07-29):
  - commands/deletion.py::_soft_delete_preflight yalnız work_object ve rationale_family dallarını tanıyor;
    bir ESP kökü soft-delete edilince embedded_resolver_registry satırı TRUSTED_ACTIVE kalıyor.
  - queries/esp.py::resolve_embedded_dependency yalnız entry.trust_state'e bakıyor, kökün
    deletion_state'ine HİÇ bakmıyor → probe: ta.sma activate → root soft-delete → resolve →
    AYNI trusted revision döndü.
  - Fonksiyonun kendi docstring'i (queries/esp.py:228) tersini vaat ediyor:
    "deprecated / soft-deleted registry entry -> RESOLVER_NOT_ACTIVE".
Doc 07 PC-19: "new Pre-Check does not resolve soft-deleted/inactive ESP".

Yap:
1. Düzeltmeyi seç ve gerekçelendir: (a) soft-delete ESP dalında registry'yi UNAVAILABLE'a düşürsün,
   (b) resolve kökün deletion_state'ini okusun, ya da ikisi birden. Önce dependency_pins.py::_pin_defect'in
   aynı kör noktayı paylaşıp paylaşmadığını ampirik kontrol et.
2. backend/tests/integration/test_acceptance_esp_package_gaps.py'deki
   test_soft_deleted_esp_keeps_the_historical_dependency_manifest_readable testine ikinci cümleyi ekle
   ve docstring'deki "HOLE (empirically verified …)" bloğunu kaldır; PC-19 etiketi korunur.
3. Tarihsel manifest'in okunabilirliği BOZULMAMALI — testin birinci yarısı aynen geçmeli.
4. ESP-17 (aktif trusted resolver'ın soft-delete'i bloklanmıyor) aynı kapsamda mı, ayrı mı — karar ver ve yaz.
5. Verify: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
   && uv run pytest -q  (izole TEST_DATABASE_URL ile, tek çağrı, ortada öldürme).
6. Branch fix/pc19-soft-deleted-esp-must-not-resolve, ayrı PR, NO AI attribution.
   Kapanışta docs/PROJECT_HISTORY.md + docs/STAGE2_HANDOFF.md + CLAUDE.md §Current position +
   acceptance_id_map.md §E.2 güncelle.
```
