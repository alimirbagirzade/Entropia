<!-- doc-status: current -->

# ADIM 133 — OD-2 BAĞLAMA KARARI AÇILDI: ölçüm indi, **imza inmedi**

**Taban:** `origin/main` @ `c57ea644` (ADIM 132 / `C9` — containment lift).
**Bu slice DOCS-ONLY.** `backend/src`, `backend/tests`, `frontend/src`'te **sıfır satır**.

---

## Neredeyiz

`C9` indi: containment kalktı, `SHARED_ALLOCATION_STATUS = active_v1`, 22/22 ön koşul kapandı.
ADIM 132 kendi kaydına bir **dürüst sınır** yazdı — *"mark yolunun üretimde sıfır çağıranı var"* —
ve bu slice o sınırı **ölçtü** ve imzalanacak yeri açtı. **Hiçbir kutu doldurulmadı.**

**Kritik hatırlatma:** `C9` indi ama **RC verdict'i hâlâ BLOCKED** ve tek blocker **A-08 (#514)**
— ekran okuyucu denetimi. OD-2 kararı o hatta **dokunmaz**; hangi şık imzalanırsa imzalansın
verdict değişmez.

---

## Bu slice'ın bıraktıkları — **çapa isimleriyle**

### Yeni belge (tek teslimat)

`docs/decisions/closure_od2_mark_production_binding_2026-08-28.md` — **9 ölçüm + 3 karar, 10 boş
kutu, 0 dolu kutu.**

### Ölçülmüş kısıtlar — imza gelirse uygulayıcı bunları **yeniden ölçmesin, okusun**

| Kısıt | Ölçüm |
|---|---|
| **Bağlama `PV`'de olmak ZORUNDA** | `_phase_10_finalize` her açık pozisyonu `close_position` ile kapatır; gerçek üretim koşusunda terminal `ledger.positions == {}` ölçüldü → döngüden sonraki her hook **boş** rapor eder. |
| **Taşıyıcı `ledger.valuation()` olmak ZORUNDA** | `PortfolioAttribution` `stale_refused_items` **taşımıyor** — `attribute()` OD-2(a)'nın kendi sayacını düşürür. |
| **Yazım yeri `portfolio_engine.py` ya da `execution/portfolio_projection.py`** | `_AUTHORISED_PHASE_LOOP_IMPORTERS` **imzalı** ve iki modül adlandırıyor; worker'a yazmak `C4`'te reddedilen hamledir (üç dosyada beş assertion). |
| **`intents._price_for` public'e çıkarılmalı** | Private ve `__all__`'da yok; yeniden yazmak ADIM 126'nın drift dersini tekrarlar. |
| **Yeni finansal hesap GEREKMİYOR** | `MarkPrice`'ın üç alanı da bugün hesaplanıp **atılıyor**: `_price_for(view)` → `(price, authority)`, `ItemTickView.staleness_ms` → yaş. |
| **`valuation()` donmuş pencerede yasal** | Saf: `self`'e hiçbir atama yok, `_frozen_at`'e dokunmaz. |
| **`E(t)`'ye dokunulmuyor** | `portfolio_ledger.py` docstring'i otorite: *"`E(t)` is realized-only, so a mark never touches it."* Bağlama yalnız **rapor** eder. |

### Maliyet — **ölçüldü, tahmin edilmedi**

- **Golden:** dosyada `project_portfolio_run`/`iter_portfolio`/`run_portfolio` **0 kez**; dokuz
  `portfolio.*` senaryosunun hepsi `combine_item_runs` ya da allocation kuralı → unified yol
  golden'da **yok** → `(b)`/`(c1)` **0 digest**, yalnız `(c2)` `contract.execution_key`'i oynatır.
- **OpenAPI:** `mark_staleness` · `stale_refused` · `unmarked_items` · `execution_key` ·
  `engine_version` · `portfolio_policy` → **altısı da 0 kez**.
- **Migration:** **yok** — `DiagnosticArtifact.content` ve `ResultManifestSnapshot.manifest` JSONB.

### Kaydedilen, düzeltilmeyen bayatlıklar (ayrı ve ucuz bir slice)

- *"CONTAINED — nothing in production imports this module"* → `attribution.py`, `provenance.py`,
  `portfolio_ledger.py` (sonuncusunun **beş** importer'ı var).
- *"not yet built"* OD-2 → `portfolio_engine.py` §HONEST BOUNDARY md. 3, `clock.py::ItemTickView`.
- ADR §13.1 OD-2 satırı: *"Not built. `run_portfolio` marks nothing"* — **ikinci yarısı bugün hâlâ
  doğru**; satır **el değmedi** (ADR karar tablosunu yeniden yazmak adjudication'dır).

---

## Sıradaki kalem — **KOD DEĞİL, İMZA**

Üç kutu, üçü de boş, ve **ajan dolduramaz**:

1. **Karar 1** — bağlansın mı, nereye: `(a)` statüko · `(b)` diagnostics · `(c1)` provenance
   `execution_content` **dışında** · `(c2)` **içinde** (bump + golden zorunlu).
2. **Karar 2** — `MARK_STALE_AFTER_MS` = 900 sn, kanonik merdivende **9'un 5'ini** sıfırlıyor
   (30m/1h/2h/4h/1D → 0 bar taşıma). `A` dokunma · `B` timeframe'e göreli (yeni `vN` + ikinci
   bump) · `C` devret.
3. **Karar 3** — diagnostics-only bir değişiklik `ENGINE_VERSION` bump'ı gerektirir mi? Depoda
   **hiç yorumlanmamış**: `execution_key` manifest'ten türer, `EngineOutput`'tan değil.

`(a)` **zayıf değildir ve belge bunu açıkça yazar**: ön koşul 17'nin literali *"OD-2 mark policy
**flip**"*, R-5 ise *"recorded in the manifest as a versioned policy"* — **ikisi de bağlamayı
istemez** ve ADIM 132 ikisini de harfi harfine karşıladı.

---

## Paste-ready resume prompt

```
ENTROPIA — OD-2 BAĞLAMA: İMZA GELDİ Mİ? ÖNCE ONU ÖLÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -n '☑\|☐' docs/decisions/closure_od2_mark_production_binding_2026-08-28.md

DURUM: ADIM 133 OD-2 mark yolunun üretime bağlanmasını ÖLÇTÜ ve karara açtı. ÜÇ kutu
vardı ve ÜÇÜ DE BOŞTU. Kutuları YALNIZ ürün sahibi doldurur (G10/G11/G12/G14 emsali).

KUTULAR HÂLÂ BOŞSA -> DUR. Kod yazma, varsayılan seçme, "muhtemelen (b)" deme.
  Yapılacak tek şey: talebi tazele (ADIM 130'un "yeniden talep" biçimi) ve BAŞKA bir
  kaleme geç. A-08 (#514) ayrı hattır ve tek blocker odur.

KARAR 1 İMZALIYSA, şıkka göre:
  (a) -> hiçbir kod yazılmaz. Kaydı yaz, kapat.
  (b)/(c1)/(c2) -> ÖNCE Karar 3'ün imzasını oku (bump gerekir mi). Sonra:
     - bağlama PV'de (_run_tick, publish_snapshot'tan hemen sonra) — döngüden SONRASI
       P10 yüzünden YAPISAL OLARAK BOŞ, ölçüldü (ledger.positions == {}).
     - taşıyıcı ledger.valuation() — attribute() stale_refused_items'ı DÜŞÜRÜR.
     - intents._price_for public'e çıkar (yeniden yazma: drift).
     - yazım yeri portfolio_engine.py / execution/portfolio_projection.py — WORKER'A YAZMA
       (imzalı allowlist'i genişletir; C4'te reddedildi, üç dosyada beş assertion).
     - (c2) ise: ENGINE_VERSION bump + golden yeniden üretimi AYNI commit'te.

YASAKLAR: imza kutusunu DOLDURMA. MARK_STALE_AFTER_MS'i Karar 2 imzasız DEĞİŞTİRME.
  ADR §13.1'in OD-2 satırını yeniden yazma (adjudication). A-08'e dokunma.
  "OD-2 üretimde akıyor" deme — Karar 1 (b)/(c) imzalanıp KOD İNENE kadar akmıyor.

TUZAKLAR:
  - manifest.py execution/ altındaki sabitleri İMPORT EDEMEZ; değerler yeniden yazılır ve
    drift test_a16_manifest_policy_parity.py ile kapatılır.
  - Alt küme koşarken --no-cov. Exit code'u pytest'ten AYRI oku (wrapper subshell değil).
  - Uzun suite koşarken docs/ düzenleme (documentation-truth kapısı sahte kırmızı verir).

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB.
  backend/.venv yoksa `cd backend && uv sync --all-extras`.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
  İŞARETLEME; kapanış ritüeli ZORUNLU.
```
