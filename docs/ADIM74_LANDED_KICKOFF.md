<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM76_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 74 — R2 + R3 landed · sıradaki slice için kalkış

## Neredeyiz

`TimingProvenance` zinciri **kapandı**. Bir research revizyonunun timing sözlüğü artık
**dört yüzeyin dördünde de tek yerden** okunuyor:

| Yüzey | Nereden | Hash'lendiği yer |
|---|---|---|
| Run manifest | `backtest_run_context.py::_research_entries` → `as_manifest_revision()` | `execution_key` |
| Ready Check | `readiness_check.py::_resolve_research_sources` → `TimingProvenance` alanları | — (karar girdisi) |
| Agent bundle | `jobs/research_data.py::_pin_member` → `as_bundle_member()` | `bundle_hash` |
| Evidence bundle | aynı `_pin_member` | `bundle_hash` |

Bu, R1 (#734) → R2 (#742) → R3 (#745) üçlüsünün toplam sonucudur. **İki ayrı hash uzayı**
söz konusu ve ikisi de korunuyor: `execution_key` R1'in byte-identity kanıtıyla,
`bundle_hash` R2'nin byte-identity kanıtı **artı** R3'ün golden digest'iyle.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- **`domain/research_data/timing_provenance.py::TimingProvenance`** — `from_row()` +
  `as_manifest_revision()` + `as_bundle_member()`. Beşinci bir yüzey gerekirse **yeni bir
  projeksiyon metodu ekle**, satırı elle okuma.
- **`MANIFEST_REVISION_KEYS`** (public, `__all__`'da) ve testteki **`_CORE_HASHED_KEYS`** —
  hash'lenen şekli adlandıran sabitler.
- **`tests/unit/test_research_bundle_seal_rule.py`** — golden digest kapısı;
  `_seal_bundle`'ı session'sız çağırma deseni buradadır.
- **`tests/unit/test_research_timing_provenance.py` + `..._bundle_member_projection.py`** —
  "ekstraksiyon öncesi literal'i elle transkribe et, sonra transkripsiyonu kaynağa karşı
  programatik doğrula" deseni. Bir sonraki byte-identity refactor'ü bunu kopyalasın.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **Bir statik analiz bulgusunu savunmadan önce ölç.** CodeQL alert 256 haklıydı ve
   doğrulama **bulguyu değil benim gerekçemi** çürüttü (`MANIFEST_REVISION_KEYS` emsali
   yanlıştı: o public + `__all__`, silinen sabit private + ölü).
2. **Base'i `main` olmayan bir PR yeşile DÖNEMEZ.** Workflow'lar yalnız `main` hedefli
   PR'larda tetikleniyor; stacked PR'ın `total_count: 0` check'i vardı ve taslaktan çıkmak
   bunu değiştirmedi.
3. **Paylaşılan dalda push öncesi `git ls-remote --heads origin <dal>`.** Bu dalgada head
   **dört kez** altımdan değişti; her seferinde ölçüldü, körlemesine force-push yapılmadı.
4. **`guard-git.sh` ledger ratchet düşüşünde YANLIŞ POZİTİF verebilir.** Silinen `## ` başlığı
   `## Class B (75)` → `## Class B (74)` ise bu bir kayıt kaybı değil, meşru inişdir; birleşmiş
   dosyayı main'inkiyle `diff -q` ile karşılaştır. Çare **onay istemek değil**, CLAUDE.md'nin
   zaten yazdığı **merge yerine rebase**.
5. **Suite koşarken ikinci bir pytest başlatma.** İki sahte kırmızı bu yüzden çıktı; sebebi
   açıklanmadan geçiştirilseydi gerçek bir kusur gibi görünmeye devam ederdi.
6. **Hash uzayını yeniden bölen bir refactor, refactor değildir.** R2'nin tek kuralı buydu.

## Sıradaki tasarım işaretleri

Plan (`docs/implementation/final_closure_ordered_plan_2026-08-13.md`) açısından **PACKAGE R
BİTTİ**: R1 · R2 · R3 indi, **R4 zaten #730'da inmişti** (strict xfail 0 + üç-artefakt parity
testi — ölçüldü, yeni iş yok).

Açık kalanlar ve engelleri:

| Slice | Engel |
|---|---|
| `F2` — Max Single Position overflow | **G4 imzasız** (imza bloğu henüz yazılmamış) |
| `F3` — komisyon modeli + `execution_content.commission_model` | **G1 + G2 + G3 imzasız** (#552 *kapalı* ama karar *imzasız*) |
| `C2` → `C3` → `C4` | **G9 + G13 imzasız**, sonra importer-allowlist **insan incelemesi** |
| `A-08` | denetim; agent kapatamaz (#514 `human-only`) |

**P-E1 TAMAMLANMADI.** Blocker sayısı **1** (yalnız A-08), verdict **BLOCKED**.

## Çalışma yöntemi (bu slice'ta işe yarayan)

1. **Ön koşulu belgeden ölç, PR metninden değil.** G6'nın imzalı olduğu
   `closure_product_decisions_2026-08-13.md`'den okundu; bu ölçüm R2'nin **kapsamını
   değiştirdi** (şekil yarısı #730'da inmişti).
2. **Planın bir satırı ölçülmüş kısıt değildir.** R4 "açık" görünüyordu, ölçünce kapalıydı;
   R3'ün yarısı da öyle. Slice'a başlamadan önce **ağaca** bak.
3. **Byte-identity iddiası her zaman bir tanıkla kanıtlanır** — elle transkripsiyon + o
   transkripsiyonun kaynağa karşı programatik doğrulaması.
4. **Her assertion negatif kontrolden geçer.** İşaretlemek kapsamak değildir.

## Paste-ready resume prompt

```
Entropia — sıradaki closure slice.

Session START protokolünü uygula (CLAUDE.md): git fetch, origin/main'i oku, ardından
docs/ADIM74_LANDED_KICKOFF.md (bu belge), docs/STAGE2_HANDOFF.md §Next,
docs/implementation/final_closure_ordered_plan_2026-08-13.md.

DURUM: PACKAGE R BİTTİ (R1 #734, R2 #742, R3 #745; R4 zaten #730'da inmişti — ölçüldü).
Timing provenance dört yüzeyde de tek okumadan geliyor; iki hash uzayı (execution_key,
bundle_hash) byte-identity kanıtı + golden digest ile korunuyor.

SIRADAKİ İŞ İÇİN ÖNCE ÖLÇ — planın "açık" dediği kalem ağaçta kapalı olabilir (bu dalgada
iki kez oldu). Sonra engeli doğrula:
  F2 -> G4 imzasız · F3 -> G1+G2+G3 imzasız · C2/C3/C4 -> G9+G13 imzasız + allowlist insan
  kararı · A-08 -> agent kapatamaz.
İmzasız bir kapının arkasındaki slice'a BAŞLAMA; ürün kararı UYDURMA.

PAZARLIKSIZ:
- Paylaşılan dala push etmeden önce `git ls-remote --heads origin <dal>`; körlemesine
  force-push yok.
- Base'i main olmayan PR CI koşmaz — stacked açma.
- main'i içeri alırken MERGE DEĞİL REBASE; guard'ın ledger ratchet düşüşünde yanlış pozitif
  verdiğini bil (birleşmiş dosyayı main'inkiyle diff -q ile karşılaştır).
- Tam suite koşarken ikinci bir pytest başlatma (aynı DB).
- Ratchet/baseline DÜŞÜRME; golden'ı tek başına güncelleme (ya revert, ya sürüm bump +
  yeniden pin, aynı commit'te).
- Statik analiz bulgusunu savunmadan ÖNCE ölç. "CodeQL kırmızı" tek başına hiçbir şey
  demez: LOG'a bak — bulgu mu üretti (gerçek, kodla düzelt), yoksa init'te mi öldü
  ("No server is currently available" / "Debugging artifacts are unavailable" =
  GitHub kesintisi, çare rerun). Bu dalgada ikisi de yaşandı, aynı PR'da.
- Yeşil exit code kanıt DEĞİLDİR. Entegrasyon suite'i Postgres'e ulaşamazsa fail değil
  SKIP eder ve `exit 0` verir; çıktıda nokta mı `s` mi diye bak, gerekirse
  `pg_ctlcluster 16 main start`.
- strict:true bir MERDİVEN: paralel oturumlar main'e indikçe PR'ın yeşili bayatlar. ÖLÇÜLDÜ:
  R3'ün dalı ONBİR CI koşusu yedi (6 yeşil, 5 supersede), head on kez oynadı, PR ~14 saat
  açık kaldı - ürün kodu hiç değişmeden. Bir PR'ı "yeşile yetiştirmek" yarıştır; kazanan
  her zaman en son merge edendir.
  Rebase'in içerik-nötrlüğünü HER SEFERİNDE iki range'i diff'leyerek kanıtla; artefakt
  çakışmasını YENİDEN ÜRETEREK çöz (`--root ..` şart), sayıyı elle yazma.

Kapanışta CLAUDE.md §Session CLOSING ritüelinin 6 maddesi; ADIM numarasını yazmadan önce
`git fetch` + `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile doğrula (bu depoda numara
tekrar tekrar çakıştı).
```
