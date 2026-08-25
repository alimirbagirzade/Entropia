<!-- doc-status: current -->

# ADIM 114 landed — Karar 1 imzalandı; sıradaki hamle YİNE bir imza, kod değil

## Neredeyiz

`main` = `fba6bd1` (PR #831 merged, 2026-08-25T19:43:02Z). Alembic head
`0043_i08_registry_strategy_fks` (migration yok) · `ENGINE_VERSION` **değişmedi**
(`backtest-engine-v18-percent-sizing-per-fill-commission`) · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = `future_dev` · 50 golden digest **bayt bayt aynı**.
Blocker sayısı **1** (yalnız A-08), verdict **BLOCKED**. Kabul borcu tavanları
**54 partial / 6 uncovered · A1 B21 C6 D32** — bu slice onlara **dokunmadı**.

**Sayısal otorite bu belge DEĞİL** → `docs/generated/repository_facts.md` (üretilmiş, CI'da
`--check` bloklayıcı). Bu belge **ölçtüğü anı dondurur**.

## Bu slice ne bıraktı

**Karar 1 imzalandı ve uygulandı.** Komisyonun **tabanı** artık açık bir alan; **dağılımı**
(`per_fill`) onaylandı ve manifest'te **beyan ediliyor**. Varsayılan altında hiçbir sayı
oynamadı, o yüzden `ENGINE_VERSION` bump'ı gerekmedi.

Ayrıca `#550/#551/#552` **doğrulandı** (hepsi #720 ile inmişti) ve **duplicate fix yazılmadı** —
kayıt `docs/audit/financial_closure_evidence.md`.

### Yeniden kullanım çapaları (birebir adlar)

| Ne | Nerede |
|---|---|
| Taban alanı | `domain/strategy/config.py::CostsModel.commission_basis` (`Literal["flat","bps"]`, **default `"flat"`**) |
| **Ücretin TEK türetimi** | `domain/backtest/execution/costs.py::FillCosts.fee(notional)` |
| Basis'i taşıyan tuple | `execution/costs.py::_cost_params` → **dört** üye döner (basis dördüncü) |
| `FillCosts`'un tek kurulum yeri | `engine.py::run_engine` — `FillCosts(half_spread, slippage, commission, commission_basis)` |
| Manifest beyanı | `domain/backtest/manifest.py::COMMISSION_MODEL` (`"per_fill"`), **`execution_content` DIŞINDA** |
| bps sabiti | `execution/costs.py::_BPS_PER_UNIT` (`Decimal("10000")`) |
| Taban oracle'ları | `tests/unit/oracles/test_oracle_costs.py::test_the_default_basis_is_flat_and_charges_the_amount_verbatim` · `::test_bps_charges_the_rate_against_each_fills_own_notional` · `::test_the_bps_fee_is_linear_in_the_rate` |
| Participant ücret oracle'ı | `tests/unit/oracles/test_oracle_engine_participant.py::test_the_mirrored_exit_commission_is_the_fee_charged_not_the_configured_rate` |
| Manifest testleri | `tests/unit/test_karar1_manifest_commission_model.py` (3 case) |
| İmza | `docs/decisions/closure_product_decisions_2026-08-13.md` §Karar 1 İMZA SATIRI + §Yerleşim |

**`fee()`'NİN ALTI ÇAĞRI YERİ — BEŞİ ÜCRET ALIR, BİRİ AYNALAR.** Yeni bir fill yüzeyi eklersen
**`FillCosts.fee()`'den geçir**, inline etme (bu, #552'nin kusurunun birebir şekliydi):

| çağrı yeri | ne yapar |
|---|---|
| `booking.py::close_position` | ücret alır (çıkış fill'i) |
| `booking.py::absorb_remainder` | ücret alır |
| `engine.py` giriş fill'i | ücret alır |
| `engine.py` stacking | ücret alır |
| `engine.py` scale layer | ücret alır |
| `participant.py::_closed_by` | **aynalar** — charged ücreti havuza bildirir, kendisi almaz |

**SAYIYI DEĞİL ADI SAY.** Bu bloğun ilk yazımı *"ALTI ÜCRET YERİ … üçü `engine`"* diyordu ve
`booking`'i üç sanıyordu (iki var), ayrıca aynayı ücret yeri sayıyordu. #835 kaynaktaki ikizini
düzeltti. Prozadaki elle sayı bu depoda üç kez bayatladı.

## Sıradaki oturum — SIRADAKİ HAMLE KOD DEĞİL, İMZA

`Karar 1` indi; başlığın kalan iki imzası **değişmedi**:

1. **`G8` (#559)** — DST fold/gap. İmza bloğu `docs/decisions/closure_g8_dst_fold_gap_2026-08-25.md`,
   **KARAR YOK**. Ölçülmüş sınır (ADIM 112): **hiçbir seçenek folded saatin ikinci occurrence'ını
   geri getirmez** — seçim *"kullanıcıya söylenip söylenmediği"* eksenindedir.
2. **`G14` (#544)** — NET conflict policy. `docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md`,
   **KARAR YOK**. Ölçülmüş: tek değerin **iki** sevk edilmiş davranışı var, ve **NET'i kaldırmak
   bir MIGRATION'dır** (`portfolio_allocation_plan.conflict_policy` VARCHAR + CHECK).
3. Sonra **`G11`+`G12` → `C6`** (kod), **`G15`** (leg 3), ön koşul 15–18 ve 22, **en son `C9`**.
   Sıra: `docs/audit/final_closure_delta_audit_2026-08-25.md` §10. `G10` **hiç talep edilmedi**.

**A-08 kendi hattında** ve RC verdict'ini bağımsız blokluyor (2/184 hücre · 0/10 akış · 0/4
çıkış kriteri · #514 açık).

**Kabul borcu partisi ARTIK KURULAMAZ** — ADIM 113 ölçtü: açık 21 sınıf-B satırın **21'inin de**
kayıtlı bulgusu var, yani bir test slice'ının sahip olduğu tanıma uyan **tek satır yok**.

### Bu slice'ın açıkça BIRAKTIĞI iş

* **Frontend'de `commission_basis` seçici YOK, bilerek.** v18 mockup görsel otoritedir ve böyle
  bir alan içermiyor (`:5621` Commission'ı birimsiz çiziyor). bps bugün yalnız API'den
  ayarlanabilir. UI'a çıkarmak **önce bir mockup güncellemesi** ister — o gelmeden eklemek
  §UI/frontend kuralının ihlalidir.
* **`ta.atr` benzeri bir "recognized ama computable değil" ayrımı komisyonda YOK** — `bps` ve
  `flat` ikisi de tam sevk edilmiş.

## Tuzaklar — bu slice'ta ölçüldü

* **Bir kusuru ararken kullandığın DESEN, kusurun bulunduğu yeri belirler.** Ücret yerlerini
  (equity mutasyonu) grep'lemek altısını buldu, **rapor eden** yedinciyi kaçırdı. Yeni bir
  "tek türetim" refactor'ında **hem mutate eden hem RAPOR EDEN** tüketicileri ara.
* **Varsayılan altında koşan bir suite, varsayılan-dışı bir kusuru GÖREMEZ.** Participant
  hatasında 0 test kırmızı oldu. Yeni bir mod eklerken **o modu koşan bir case yaz**, yoksa
  yeşil hiçbir şey söylemez.
* **Şema anahtarını doğrula.** `limits` yazıp `position_size_limits` sanmak pydantic'te
  **sessizce yutulur** ve ölçümü FAIL gibi gösterir (bu oturumda bir kez oldu, kusur sanılmadan
  önce şema okundu).
* **`| tail` bir kapıyı GİZLER** — exit code `tail`'in olur. Çıktıyı dosyaya yaz, `$?`'i **ayrı**
  oku. Bu oturumda `repository_facts --check` bir kez böyle yanlış yeşil göründü.
* **Test ekleyen slice üretilmiş olguları TAZELEMELİ** (ADIM 60 emsali, bu slice'ta **iki kez**
  yaşandı): `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..`
* **Sunucu tarafı "Update branch" düğmesi CI'ı sıfırlar** (~50 dk) ve tarihsel olarak bir docs
  kaydını sessizce düşürmüştü. main'i içeri almak gerekiyorsa **rebase**. Bu slice'ta düğme
  kullanıldı, hasar **ölçüldü** (yoktu), ama bedel ödendi.
* **Memory checkpoint bu container'da YAZILAMAZ.** `--sync --only …` exit 1 verir
  (`agentmemory-mcp: not found`) — `memory_server.sh` *"zaten canlı"* dese bile. **Borç değil:**
  indeks `PROJECT_HISTORY.md`'den türetilir, argümansız `--sync` geri getirir; CI'ın kapısı
  `--check` ve o yeşil (127 kayıt, id'ler tekil). Elle checkpoint **YAZMA** (ADIM 53).
* **Contract testleri Postgres ister.** Bu container'da `:5432` boş → `test_auth_mode_login_gate`
  yerelde düşer, **CI'da geçer**. Yerel kırmızıyı atfetmeden önce **kökünü oku**.

## Paste-ready resume prompt

```
Entropia — ADIM 115 seed. Oturum START protokolünü UYGULA (CLAUDE.md): önce `git fetch`,
`git log --oneline origin/main -6`, açık PR'ları listele; handoff/summary STALE-BY-DEFAULT.

Taban: main = `fba6bd1` (PR #831 / ADIM 114 merged). ENGINE_VERSION değişmedi, 50 golden digest
sabit, alembic head `0043_i08_registry_strategy_fks`, SHARED_ALLOCATION_STATUS=future_dev,
blocker 1 (yalnız A-08), BLOCKED.

ADIM 114 ne yaptı: Karar 1'i imzaladı ve uyguladı — komisyonun DAĞILIMI (`per_fill`) onaylandı
ve manifest'te `COMMISSION_MODEL` olarak beyan edildi (`execution_content` DIŞINDA); TABANI açık
bir alan oldu (`CostsModel.commission_basis`, flat|bps, default flat). Ücretin tek türetimi
`FillCosts.fee(notional)` ve ALTI ücret yeri + rapor eden yedinci tüketici ondan geçiyor.
Varsayılan altında hiçbir sayı oynamadı. Ayrıca #550/#551/#552 doğrulandı, duplicate fix
yazılmadı (`docs/audit/financial_closure_evidence.md`).

SIRADAKİ HAMLE KOD DEĞİL, İMZA. Kalan iki kapı: `G8` (#559, DST fold/gap) ve `G14` (#544, NET
conflict policy) — ikisinin de imza bloğu `docs/decisions/` altında AÇIK ve KARARSIZ. Sonra
`G11`+`G12` → `C6`, `G15`, en son `C9`. Sıra: `docs/audit/final_closure_delta_audit_2026-08-25.md`
§10.

Bir imza slice'ı yazma yetkin YOK — karar ÜRÜN SAHİBİNİNDİR. Yapabileceğin: kararın
seçeneklerini ÖLÇÜLMÜŞ sonuçlarıyla hazırlamak (migration gerekiyor mu, kaç golden digest oynar,
göç tuzağı var mı, UI kullanıcıya ne söylemiş) ve sormak. ADIM 114'ün Karar 1'i iki eksene
ayırarak imzalatması bu şeklin emsalidir.

Kabul borcu partisi ARTIK KURULAMAZ (ADIM 113: 21 sınıf-B satırın 21'i de kayıtlı bulgu).

Kapılar: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
&& uv run pytest -q`. Alt küme koşarken `--no-cov`. `| tail` KULLANMA — exit code'u ayrı oku.
Test eklersen üretilmiş olguları tazele. Kapanışta CLAUDE.md §Session CLOSING ritüelinin ALTI
maddesini de koştur; `## Next:` BAŞLIĞINI değiştirme, gövdesine güncelleme bloğu ekle.
```
