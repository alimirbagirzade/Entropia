<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular).

# ADIM 72 — kayıtsız inen İKİ slice'ın ritüeli: C5 (#740) + E5 (#738)

## Neredeyiz

İki ölçüm slice'ı indi ve **ikisi de sıfır ürün satırı** sevk etti. `C5` bir planı düzeltti,
`E5` bir slice'ı durdurdu. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

- **`C5` (#740, `df7df92`)** — R-1 allocation pinning **zaten sevk edilmişti**. Plan onu
  koşulabilir diye listeliyordu; ADR §10.2'nin üç yargısının üçü de yanlış çıktı.
- **`E5` (#738, `6ca478c`)** — `C4` **kurulamaz**: ön koşulu `C3`, `C3` yok, `C2` de yok.
- **En önemli sonuç:** `C1` (#735) P-E4'ün Blocker 1'ini kapattı → **ajanın kapatabileceği
  mühendislik ön koşulu KALMADI. Sıradaki hamle bir İMZADIR (`G9` + `G13`).**

alembic head `0043_i08_registry_strategy_fks` · `ENGINE_VERSION` değişmedi · OpenAPI değişmedi ·
`SHARED_ALLOCATION_STATUS` = `future_dev` (dokunulmadı).

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- `application/commands/readiness_check.py::_resolve_allocation` — R-1'in **doğru** hâli:
  `_pinned_revision(...) is None` **tek** draft dalıdır.
- `::_pinned_revision` — `plan.enabled` + head pointer çözünürlüğü; çözülmeyen pointer
  **hiçbir şey** pinlemez.
- `::_pinned_config_hash` — revizyonun **saklanmış** `config_hash`'ini yeniden hesaplamaya
  tercih eder.
- `tests/integration/test_allocation_revision_pin.py` — 3 test, **kendi anti-vacuity guard'ı
  var** (`assert live != revision.config`). Negatif kontrolle **taşıyıcı** olduğu kanıtlandı.
- `domain/backtest/execution/provenance.py::sleeve_amount_divergences` — `build_portfolio_manifest`
  içinde bağlı; yarım-cent tie testi mevcut.
- `docs/audit/closure_c5_r1_allocation_pinning_measurement_2026-08-17.md` ve
  `…closure_e5_worker_precondition_measurement_2026-08-17.md` — iki ölçümün tam kaydı.

## Pazarlıksız — bu slice'ın öğrendikleri

- **PARTİ SEÇMEDEN ÖNCE ÖLÇ.** `C5` bir plan satırı yüzünden işe alındı; iş **bitmişti**.
  Plan 2026-08-14'te yazıldı, düzeltme ondan önce sevk edilmişti. **Plan bayattı, kod değil.**
  Bir slice'a başlamadan önce kriterin adlandırdığı davranışı `backend/src`'te **ara**.
- **MERGE SONRASI YENİDEN ÖLÇ.** `#734` slice ortasında dala girdi ve `readiness_check.py`'ye
  dokundu. Allocation yolu etkilenmedi (**0 hit**) ama **satır numaraları +3 kaydı** →
  imzalanan ADR satırı imzalandığı gün yanlış satır alıntılayacaktı.
  **SATIR NUMARASI YAZMA, SEMBOL ADI KULLAN** (CLAUDE.md'nin kendi kuralı).
- **BİR KAYIT KAYBOLMUŞ GÖRÜNÜYORSA ÖNCE DELİLE BAK.** İmza commit'i dalda yoktu; ilk okuma
  *"docs regresyonu, geri yükle"* idi. Ölçüm çürüttü: geri alım **tam ve içsel olarak
  tutarlıydı** (audit belgesi ve plan notu da imza-öncesi metne döndü) → **kaza değil karar**.
  Kazalar yarım iz bırakır: ADR düşer ama belgeler "SIGNED" demeye devam eder. **O iz yoktu.**
- **BİR ÖLÇÜM SLICE'I BİR KAYDI İMZALAYAMAZ.** İmza istendi, verildi, uygulandı, sonra ürün
  sahibi geri aldı. Ajanın işi bunu **olduğu gibi kaydetmek**, tekrar denemek değil.
  **`R-1`'in ADR kaydı imzasızdır ve geri uygulanmamalıdır.**
- **DEĞİŞMEYEN GATE'İN NEGATİF KONTROLÜ OLMAZ.** `E5` containment gate'i değiştirmedi, o
  yüzden negatif kontrol **koşulmadı** — ve bu bir eksik değil. Tarif ettiği yol yokken
  gate'i yeniden yazmak onu **tatmin etmez, KÖR EDER**.

## Sıradaki tasarım işaretleri — hâlâ `C2` (E4b), ve önündeki İKİ İMZA

`E5` bunları bağımsız olarak yeniden ölçtü ve **doğruladı** (miras almadı):

| Gerekli | Var mı? | Ölçüm |
|---|---|---|
| `ItemParticipant.settle` / `.finalize` | **YOK** | 0 grep hit |
| P10 (`PHASE_ORDER`) | **YOK** | 8 faz: `P1 P3 PV P4 P5 P6b P7 P9` |
| `iter_portfolio` | **YOK** | `backend/src`'te 0 hit |
| `domain/backtest/participant.py` (`C3`) | **YOK** | dosya mevcut değil |
| `backend/src`'te `ItemParticipant` impl'i | **SIFIR** | ikisi de test sahipli |
| **`G9`** (ADR §16 Gate 1) | **NOT REQUESTED** | plan §5 |
| **`G13`** (P10 equity noktası) | **UNDECIDED** | plan §5 |

**Sıra:** `G9` + `G13` imzaları → `C2` → importer-allowlist kararı (**insan**) → `C3` → `C4`.
**İlk iki adım da ajanın işi değildir.** `C1` sonuncu mühendislik ön koşuluydu ve indi.

**Blocker D hâlâ canlı:** containment gate'in importer kontrolü yalnız
`domain/backtest/portfolio_engine.py`'yi allowlist'ler ve yalnız `execution/` altındakileri
muaf tutar → `domain/backtest/participant.py` **yapı gereği** kırmızı verir. Genişletme
**incelenmiş bir karardır**, ajanın tercihi değil.

## Çalışma yöntemi (bu slice'ta işe yarayan)

1. Ön koşulu **ağaca karşı** doğrula, plana ya da bir önceki ölçüm belgesine güvenme —
   P-E4'ün Blocker 1'i bu slice'ta **yanlış** çıktı çünkü `C1` arada inmişti.
2. Kapatıldığı iddia edilen her kriter için **negatif kontrol** koş: kusuru geri koy, testin
   **hangi satırda** kırmızı verdiğini gör, geri al, yeşili doğrula.
3. Dala main girdiyse **iddialarını yeniden ölç** — özellikle dokunduğu dosyalar seninkiyle
   kesişiyorsa. Satır numaraları kayar.
4. `cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check` →
   `documentation-truth gate OK` + exit 0 **görmeden push etme**.
5. Alt küme koşarken **`--no-cov`**; çıktıyı dosyaya yaz, `$?`'i **ayrı** oku.

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice

SESSION START:
  git fetch --all --prune && git status --short   (kirliyse DUR)
  git switch main && git reset --hard origin/main && git rev-parse HEAD

OKU (otorite sırası): docs/ADIM72_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §Next →
docs/implementation/final_closure_ordered_plan_2026-08-13.md §6 → docs/generated/repository_facts.md
(SAYISAL OTORİTE) → docs/PROJECT_HISTORY.md §ADIM 72.

DURUM: C5 (#740) ve E5 (#738) indi, ikisi de SIFIR ürün satırı. Blocker 1 (yalnız A-08),
BLOCKED. C1 (#735) describe/book ayrımını sevk etti.

PAZARLIKSIZ:
  - C-zinciri (C2 → C3 → C4) İKİ İMZASIZ İNSAN KAPISININ arkasında: G9 (ADR §6/§8
    amendment) ve G13 (P10 equity noktası). ONAYSIZ BAŞLAMA.
  - R-1'in ADR kaydı BİLEREK imzasızdır (ürün sahibi imza commit'ini geri aldı).
    GERİ UYGULAMA.
  - SHARED_ALLOCATION_STATUS "future_dev" KALIR. Containment gate'i ZAYIFLATMA.
  - Satır numarası yazma, sembol adı kullan.

YAPILACAK: planın §6 tablosundan ön koşulu KARŞILANAN bir kalem seç (C5 tükendi; açık
PR'lar #741/#742/#743'e bak, çakışma yaratma) ve o slice'ı yaz. Seçmeden ÖNCE, kriterin
adlandırdığı davranışın backend/src'te zaten sevk edilip edilmediğini ÖLÇ — C5 tam bu
yüzden boş çıktı.

TEST: kapattığın her kriter için negatif kontrol ZORUNLU (kusuru geri koy, kırmızıyı gör,
geri al). Alt küme koşarken --no-cov.

DOĞRULAMA: cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && uv run pytest -q ; cd .. &&
python scripts/generate_repository_facts.py --check

KAPANIŞ: 6 maddelik ritüel. Numara ÖLÇ (grep '^## ADIM' docs/PROJECT_HISTORY.md), merge'den
hemen önce BİR KEZ DAHA doğrula — merge edilen ad kazanır. PR aç, MERGE ETME.
```
