<!-- doc-status: historical -->
# ADIM 134 landed — GH #854 pin taşıma kusuru koşuldu; düzeltmesi İMZA bekliyor

## Neredeyiz

- **Taban:** `origin/main` @ `8b3a24b0`. Bu slice **ürün kodunda sıfır satır** değiştirdi.
- alembic head `0044_drop_net_conflict_policy` (**migration YOK**) · `ENGINE_VERSION`
  **değişmedi** · OpenAPI **değişmedi** · golden **el değmedi** · `SHARED_ALLOCATION_STATUS`
  = `active_v1` (**el değmedi**).
- Toplanan test **3868 → 3870** (366 → 367 dosya). Blocker **DEĞİŞMEDİ** (1 — yalnız A-08),
  verdict **BLOCKED**.

## Bu slice ne bıraktı (reuse çapaları — tam sembol adlarıyla)

| Çapa | Nerede | Ne işe yarar |
|---|---|---|
| `test_reusing_the_same_batch_moves_the_pin_and_blocks_the_untouched_item` | `backend/tests/integration/test_external_import_pin_stability.py` | Trade Log yüzeyi: READY → BLOCKED dizisini uçtan uca sürer |
| `test_the_trading_signal_twin_moves_its_pin_the_same_way` | aynı dosya | Signal yüzeyi, **gerçek** `create_trading_signal_and_attach` → `create_trading_signal_revision` çiftiyle |
| `_seed_signal_import` | aynı dosya | accepted normalized Signal revision; `earliest_available_time` **geçmiş instant** (anti-lookahead) |
| `_codes` | aynı dosya | readiness sonucundan issue kodları kümesi |
| `closure_i854_external_import_pin_stability_2026-08-28.md` | `docs/decisions/` | **iki karar, sekiz boş kutu** |

**Yeniden kullanılanlar (kopyalanmadı):** `_ready_composition` / `_seed_principals`
(`test_backtest_persistence`), `_attach_trade_log` / `_trade_log_payload`
(`test_external_object_run_provenance`), `_signal_payload`
(`test_backtest_manifest_pinning`). `fake_object_store` **yerelde** tanımlandı — ağaçta
**on** modül kendi kopyasını taşıyor ve paylaşılan bir conftest fixture'ı **yok**.

## Sıradaki kalem — KOD DEĞİL, İMZA

`docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md` **sekiz** kutu
taşıyor ve sekizi de **BOŞ**:

- **Karar 1** — aynı batch'i paylaşan revision'lardan hangisi çözülsün: `(a)` statüko ·
  `(b)` set-once · `(c)` ikinci pin'i reddet · `(d)` link tablosu · `(e)` ileri çözüm.
- **Karar 2** — `(d)`/`(e)` seçilirse **imzalı** `G15`/Karar 4'ün konusuz kalması kabul mü.

**Ajan bu kutuları dolduramaz.** İmza gelirse uygulama kısıtları **ölçülmüş** hâlde hazır:

- Yazıcılar `link_batch_to_revision` (`repositories/trade_log.py`) ve
  `link_normalized_to_revision` (`repositories/trading_signal.py`); her biri komut modülünde
  **iki** yerden çağrılır — **dördünü birden** değiştir, yoksa bir yüzey sessizce kalır.
- `(c)` seçilirse kapı `_require_ready_import`'a gider ve **O-02 zarfıyla** yeni bir hata
  kodu ister (`shared/errors.py`, kategori + `retryable` bildirilerek).
- `(d)`/`(e)` seçilirse `_resolve_external` **ve** `readiness_repo.resolve_trade_log_batches` /
  `resolve_signal_revisions` birlikte değişir; `G15` belgesi `historical` işaretlenir,
  **silinmez**.
- **Hangi seçenek seçilirse seçilsin bu slice'ın iki testi KIRMIZI olur.** Bu tasarımdır:
  onları **kasıtlı** güncelle, docstring'lerdeki *"characterization"* çerçevesini kaldır.

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **İzole DB:** `entropia_i854` yaratıldı, `LC_ALL=C.UTF-8 PYTHONUTF8=1` ile
  `alembic upgrade head`, sonra
  `TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_i854"`.
- **Alt küme koşarken `--no-cov`**, ve **exit code çıktıdan AYRI okunur** (`| tail` kullanma).
- **Negatif kontrolde geri alma bellekteki anlık görüntüden yapılır**, VCS geri alma komutuyla
  DEĞİL — commit edilmemiş çalışma silinir (ADIM 111). Her turdan sonra `git status`.
- **TUZAK, bu slice'ta iki kez yaşandı:** `guard-git.sh` **komut dizesinin tamamında** desen
  arar, o yüzden bir heredoc'un *prozası* içinde geçen `git ch<eckout> --` gibi bir literal
  **append'i bloklar**. Metni yeniden yaz ya da dosyaya yazıp öyle koştur.
- **Test ekleyen slice `repository_facts`'i tazeler:** üretici **repo kökünden** koşar
  (`backend/.venv/bin/python scripts/generate_repository_facts.py`), `backend/` içinden
  koşarsan `openapi.json`'ı bulamaz.

## Dürüst sınır

Kusur **düzeltilmedi**; #854 **kapatılmadı** (insan kararı). `G15` belgesi ve imzası el
değmedi. Frontend'de sıfır satır → frontend kapıları **koşulmadı**. Tam suite **koşulmadı**
(yerelde 5 dosya / 36 test yeşil) → **geçen sayı ve coverage CI'ın otoritesinde**. Üretimde
kaç revision'ın batch paylaştığı **sayılmadı ve ikame edilmedi**.

---

## Paste-ready resume prompt

```
ENTROPIA — #854 PIN TAŞIMA: İMZA GELDİ Mİ? ÖNCE ONU ÖLÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -n '☑\|☐' docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md

DURUM: ADIM 134 #854'ün kusurunu İKİ yüzeyde de koşulur hale getirdi
(test_external_import_pin_stability.py, 2 case) ve düzeltmeyi karara açtı. SEKİZ kutu
vardı, SEKİZİ DE BOŞTU. Kutuları YALNIZ ürün sahibi doldurur.

KUTULAR HÂLÂ BOŞSA -> DUR. Kod yazma, varsayılan seçme, "muhtemelen (b)" deme.
  A-08 (#514) ayrı hattır ve tek blocker odur. Başka bir kaleme geç
  (ölçülmüş adaylar: #703 native_asset_id hiç yazılmıyor · #532/#534 diagnostics
  taksonomi boşlukları).

KARAR 1 İMZALIYSA, şıkka göre:
  (a) -> hiçbir kod yazılmaz. Kaydı yaz, kapat.
  (b)/(c)/(d)/(e) -> DÖRT çağrı yerini birden değiştir (link_batch_to_revision ve
     link_normalized_to_revision, her biri create + revision). Sonra:
     - (c) ise: kapı _require_ready_import'a gider, O-02 zarfıyla YENİ hata kodu
       (shared/errors.py, kategori + retryable bildirilir).
     - (d)/(e) ise: ÖNCE Karar 2'nin imzasını oku. _resolve_external ile
       resolve_trade_log_batches / resolve_signal_revisions BİRLİKTE değişir;
       G15 belgesi historical işaretlenir, SİLİNMEZ.
     - HER ŞIKTA: bu slice'ın iki testi KIRMIZI olur. Kasıtlı güncelle,
       docstring'lerdeki "characterization" çerçevesini kaldır.

YASAKLAR: imza kutusunu DOLDURMA. #854'ü kapatma. G15/Karar 4'ü imzasız konusuz bırakma.
  A-08'e dokunma. "Kusur düzeltildi" deme — Karar 1 imzalanıp KOD İNENE kadar duruyor.

ORTAM: Postgres :5432 (entropia/entropia). İzole DB + alembic:
  LC_ALL=C.UTF-8 PYTHONUTF8=1, TEST_DATABASE_URL=postgresql+asyncpg://...
  Alt küme koşarken --no-cov; exit code'u pytest'ten AYRI oku.
  repository_facts üreticisi REPO KÖKÜNDEN koşar.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
  İŞARETLEME; kapanış ritüeli ZORUNLU.
```
