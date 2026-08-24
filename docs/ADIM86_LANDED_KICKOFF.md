<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM92_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).
# ADIM 86 LANDED — kayıtsız inen P1-proof (#765) + P2 (#766) kaydedildi · sıradaki slice için kickoff

> Ölçüm anı: **2026-08-19**, taban main **`a5bc27f`** (ADIM 83 = #781 dahil). Bu belgedeki her sayı o commit'e karşı
> ölçülmüştür ve **present-tense okunmamalıdır** — `git fetch` ile yeniden ölç.

## Neredeyiz

Bu slice **ürün kodu yazmadı**; kayıtsız inmiş **iki** PR'ın kapanış ritüelini koştu:

| PR | Merge | Ne |
|---|---|---|
| **#765** | `650a66a` | test-only — `test_tick_revision_batch_parity.py` (+118), P1'in batch tick okuyucusunun substitutability kanıtı |
| **#766** | `c2c966e` | 19 satır ürün kodu — `_build_item_inputs`'un mirror deref'i batch'e bağlandı + `strategy_mirror_leg` bütçe satırı |

**Ölçülmüş durum:** alembic head **`0043_i08_registry_strategy_fks`** (migration yok) ·
`ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
**`future_dev`** · **blocker 1 (yalnız A-08), verdict BLOCKED**.

**P-C2 §D.1 — Ready Check'in üç N+1 bacağı, bugünkü hâli:**

| Leg | Bütçe satırı | Durum |
|---|---|---|
| 1 — tick-data availability | `readiness_check.tick_data_leg` | **FLAT** (1/1, `per_item: 0`) — P1 = #751, kanıtı #765 |
| 2 — Strategy mirror deref | `readiness_check.strategy_mirror_leg` | **FLAT** (2/2, `per_item: 0`) — #766 |
| 3 — external import state | `readiness_check.run_readiness_check` | **AÇIK, bilerek** (8 → 18, `per_item: 1`) — **G15, imzasız** |

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- `backend/src/entropia/application/commands/readiness_check.py::_build_item_inputs` — batch
  deseninin **kanonik örneği**: pinler `_mirror_ref` (`:375`) ile toplanır, **döngüden ÖNCE**
  tek `get_strategy_revisions` çağrısı yapılır, döngü map'ten okur.
- `backend/src/entropia/application/commands/readiness_check.py::_resolve_strategy_payload`
  (`:387`) — mirror semantiğinin **TEK tanımı**. Opsiyonel `mirrors` map'i verilirse okuma
  yerine lookup yapar; **verilmezse eski davranış bayt bayt aynıdır**. Yeni bir çağıran
  eklerken kendi deref'ini yazma, buradan geçir.
- `backend/src/entropia/infrastructure/postgres/repositories/strategy.py::get_strategy_revisions`
  (`:196`) — çoğul PK okuyucu; ağaçta **tek tanım** (ölçüldü). `get_work_object_revisions`'ın
  aynası. **Üçüncü bir idiom icat etme.**
- `backend/src/entropia/infrastructure/postgres/repositories/market_data.py::find_approved_tick_revisions_for_instruments`
  (`:398`) — `DISTINCT ON` batch'i; `get_dataset_roots`'un alan-alan aynası, beş guard'ı da
  **SQL'de**. Per-item karşılığı `find_approved_tick_revision_for_instrument` **KALDI** (ikinci
  çağıranı var ve parity testinin referans implementasyonudur — silme).
- `backend/tests/integration/test_tick_revision_batch_parity.py` — batch'i sevk edilmiş
  per-item probe'a karşı **aynı DB üzerinde** sürer; beş SQL guard'ı, kazanan kuralını,
  duplicate collapse'ı, boş short-circuit'i ve erişilemez `NULL instrument_id` satırını ayrı
  ayrı ayırt eder. Yeni bir batch okuyucu yazarken **bu dosyanın şeklini kopyala**.
- `backend/tests/integration/test_query_budgets.py::test_ready_check_strategy_mirror_leg` —
  fixture **her item'a KENDİ mirror revizyonunu** verir. Pin paylaşan bir fixture tek lookup'a
  çöker ve per-item deref geri gelse bile **yeşil kalır**.

## Pazarlıksız — bu slice'ın öğrendikleri

- **Bir ratchet satırının SINIRINI ölç, yalnız slope'unu değil.** `strategy_mirror_leg` bu
  oturumda **iki yönde** sürüldü: batch **kaldırılınca** `assert 12 <= 2` ile kırmızı verdi
  (satır işini yapıyor), ama batch yerinde bırakılıp yalnız `mirrors` argümanı düşürülünce
  **yeşil kaldı** — ısınmış identity map yüzünden `session.get` hiç SQL üretmez. **Satır
  KALDIRILMIŞ batch'i yakalar, gereksiz okumayı değil**, ve notu bunu açıkça yazar. Sınırı
  yazılmayan bir slope-0 satırı bir **güvenlik yanılsamasıdır**.
- **Negatif kontrolün NEDEN kırmızıya döndüğüne bak.** Parity mutasyonu (`DESC` → `ASC`)
  **tam olarak bir** testi düşürdü; yalnız kendi testini düşürmesi o assertion'ın diğerlerine
  binmediğinin kanıtıdır. Hepsini birden düşüren bir mutasyon hiçbir şey ayırt etmez.
- **Sevk edilmiş bir seam'in çağıranı yoksa seam iş yapmaz.** #754 `mirrors` parametresini
  ekledi, `_build_item_inputs` onu geçmedi → leg 2 aylarca per-item kaldı ve **hiçbir kapı
  görmedi** (bütçe satırı da yoktu). Yeni bir opsiyonel prefetch parametresi eklerken **aynı
  PR'da bir çağıranı bağla**, yoksa ölü koddur.
- **SLICE'A BAŞLAMADAN ÖNCE AÇIK PR'LARI TARA** (`list_pull_requests`), sadece ağacı değil.
  Bu dalgada **iki** slice paralel yazıldı: P1 sıfırdan yazıldı (#751 zaten uçuyordu → #764
  kapatıldı), P2 rakip bir mekanizmayla yazıldı (#754 farklı tasarımla önce indi → dal
  yeniden kuruldu, mekanizma düşürüldü). ADIM 81'in (b) dersinin **ikinci** örneği.
- **Bayt bayt aynı yaz.** `get_strategy_revisions` #754'ünkiyle özdeş yazıldığı için rebase
  onu **çoğaltmadan** birleştirdi. Rakip bir imza yazsaydı iki tanım kalırdı.
- **Yeşil exit code kanıt DEĞİL.** Entegrasyon suite'i Postgres yoksa `exit 0` + skip verir.
  `pg_ctlcluster 16 main start` → rol/DB'yi kur → sonra **nokta mı `s` mi** diye BAK.
  Bu oturumda `18 passed`, **sıfır skip** (bakıldı).
- **Mutation harness'ı:** pristine kopyayı **mutlak yolla** al, geri yüklemeyi **mutlak yolla**
  yap, **md5 ile doğrula**, sonra `git diff --quiet`. (`cd` alt kabukta göreli yolu kırar.)
- **`guard-git.sh` komut dizesinin TAMAMINDA desen arar** — `pg_ctlcluster …` ile aynı komutta
  force-push metni yazma.
- **Ratchet / baseline / golden / coverage eşiğini İNDİRME.** `run_readiness_check`'in
  `per_item: 1`'i bir borç değil bir **sınırdır**; indirmek G15'i sessizce karara bağlamak olur.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **`C3` İNDİ (PR #777 = §ADIM 85, `2cda24f`), sıradaki mühendislik kalemi `C4`.** Bu
  kickoff'un ilk yazımı *"`C3`'ün açık bir PR'ı var"* diyordu; bu kayıt 85'ten SONRA indiği
  için o satır daha yazılırken çürüdü. Sevk edilen:
  `domain/backtest/participant.py::_EngineParticipant` — bilerek `execution/` **DIŞINDA**
  (içeride containment gate'in importer taraması kör olurdu), beş allowlist tek adlandırılmış
  modülle genişledi (#761, Seçenek A, negatif kontrol kalıcı teste dönüştü), **üretimde
  çağıranı YOK** ve 50 golden digest **bayt bayt aynı**. `C4` o çağıranı bağlar ve containment
  tripwire'ının *"hiçbir şey çağırmıyor"* assertion'ını **daraltır** (silmez ya da gevşetmez).
  **`C4` de containment'ı AÇMAZ.** Belgeyi **kendin oku**, bu satırı otorite sayma.
- **Leg 3'e (`_resolve_external`) DOKUNMA.** Bir performans işi değil: `work_object_revision_id`
  **UNIQUE değil**, bugünkü kazanan **tanımsız**, batch başka bir satır seçebilir → readiness
  cevapları sessizce değişir. **`G15` imzasız** ve ön koşulu **bir SAYI** (blast radius),
  script `#762` ile indi. Önce ölçüm, sonra imza, sonra kod.
- **Bir performans slice'ı arıyorsan: kolay bacak KALMADI.** P-C2 §D.1'in üç bacağının ikisi
  flat, üçüncüsü karar bekliyor. Yeni bir N+1 iddia etmeden **önce ölç** —
  `docs/performance/query_budgets.json` bugün **12 satır** taşıyor ve `_comment` bütçe
  sayacının kör noktasını beş şekliyle yazar.
- **Kabul borcu hattı ayrı ilerliyor.** Sayıyı buradan **okuma**: tek otorite
  `docs/audit/acceptance_coverage_baseline.json` `ceilings`, ölçüm
  `acceptance_semantic_scan.py --root .. --report --ratchet`. **Ratchet yalnız aşağı iner.**
- **İmzasız kapılar** (bu oturumda G9/G13 için ölçüldü): **G9 ve G13 İMZALI** — ADR-0002
  **§13.2** (`9fc5580`, PR #753, 2026-08-17; G9 `APPROVED as stated`, G13 `FOLD`). İmzayı
  `closure_product_decisions` içinde arayıp bulamamak *"imzasız"* demek **değildir** — kaydı
  ADR'de. **Hâlâ imzasız:** Karar 1 (#552), Karar 3 (#559), `G12`, `G15`, `G4`, `G8`, `G14`;
  `G10` (Gate 2 / containment lift) **hiç talep edilmedi**. **BRİFİNGLİ ≠ İMZALI.**

### Main'e inmiş, `PROJECT_HISTORY` kaydı GÖRÜNMEYEN PR'lar (ölçüldü, anlatı YAZILMADI)

| PR | Konu | Kayıt |
|---|---|---|
| ~~#765 · #766~~ | P1 parity kanıtı + P2 wiring | **ARTIK VAR — §ADIM 86 (bu slice)** |
| #752 | G12 (Karar 6) signature block'u | YOK |
| #755 | G4 cap-overflow brifi | YOK |
| #747 | G15 external-row winner brifi | YOK |
| #761 | `C3` importer-allowlist brifi (**imzalandı**, Seçenek A) | YOK |
| #762 | G15 blast-radius sorgu script'i | YOK |
| #770 | G9/G13 imzalarının nerede verildiğinin kaydı | YOK |
| #774 | Karar 4/5 kutuları işaretlendi | YOK |
| #773 | prompt paketi canlı kickoff'u adlandırmayı bıraktı | YOK |

> **Bunların ADIM kayıtlarını YAZMA** — kaydı **sahibinin** yazması gerekir; bir kapanış
> başkasının slice'ının anlatısını uyduramaz. Burada yalnız **işaret edilir**.
> **Bu tablo iki kez çürüdü ve iki kez doğru yönde:** ADIM 81 #759'u listeledi → #778 onu
> §ADIM 82 olarak yazdı; ADIM 81 #765'i listeledi → **bu slice** onu ve #766'yı yazdı.
> *"İşaret et, uydurma"* çalışıyor. **Kalan satırları present-tense okuma — ölç.**

## Çalışma yöntemi (bu dalgada işe yarayan)

- **Durumu prompt'tan alma, ölç:** `git fetch --all --prune && git log --oneline origin/main -8`
  · `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -6` · **`list_pull_requests` (açık PR'lar)**.
- **NUMARAYI AÇILIŞTA ÖLÇMEK YETMEZ — her check-in'de yeniden ölç.** Bu slice açılışta ölçtü
  (rakip yoktu) ve **yine çakıştı**: `PR #781` on dört dakika SONRA açıldı ve aynı `## ADIM 83`
  başlığını, aynı `## Stage 83` satırını ve **aynı kickoff dosya yolunu** yazdı → bu slice
  **84**'e taşındı. **`check_classification` bunu YAKALAYAMAZ** (iki dal da tek `current` taşır;
  çakışma ancak ikinci merge'de conflict olarak görünür). Rakip aramanın doğru komutu:
  `list_pull_requests` + her açık PR'ın **commit başlığındaki `stage-<n>`**'ine bak.
- **Canlı kickoff'u ADIYLA arama, BULDUR** (#773'ün dersi):
  `for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do head -3 "$f" | grep -q 'doc-status: current' && echo "$f"; done`
  — `head -3` **zorunlu**, kapı yalnız ilk 3 satırı okur.
- **Bir slice'ın kayıtlı olup olmadığı `grep -c '#<pr>' docs/PROJECT_HISTORY.md` ile ölçülür**,
  hatırlanmaz.
- Test koşmadan önce: `pg_ctlcluster 16 main start`, `entropia`/`entropia` rol+DB, sonra
  `cd backend && uv sync --all-extras`. Alt küme koşarken **`--no-cov` ZORUNLU**.
- Push etmeden önce, exit code **ayrı** okunarak:
  `cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check`
  → *"documentation-truth gate OK"* + `exit=0` · `git diff --cached -- docs/ | grep '^-## '`
  → **boş** olmalı.
- Ürün kodu değişmiyorsa tam suite koşma — ama **koşmadığını açıkça yaz**.
- `gh` CLI bu container'da **kurulu değil**; GitHub için `mcp__github__*`. Draft'tan çıkarmayı
  ajan yapamaz (GraphQL 403).
- **`strict: true` altında auto-merge kullan.** Elle beklemek koşu bandını kapatmıyor; bu
  dalgada iki PR **beş kez** rebase edildi.

## Paste-ready resume prompt

```
Entropia — sıradaki slice. Ölçüm anı: 2026-08-19, main = güncel `origin/main`, son kayıt ADIM 86.

## Önce doğrula (özet BAYAT-VARSAYILAN)

git fetch --all --prune
git log --oneline origin/main -8
grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -4
# NUMARA: açılışta ölçmek YETMEZ — rakip PR sonradan açılabilir (ADIM 86'nın dersi).
# list_pull_requests ile her açık PR'ın commit başlığındaki stage-<n>'ine BAK.
# canlı kickoff'u ADIYLA arama, buldur:
for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do head -3 "$f" | grep -q 'doc-status: current' && echo "$f"; done
# ve MUTLAKA: açık PR'ları tara (list_pull_requests) — sadece ağacı değil.

## Durum

Blocker **1 (yalnız A-08)**, verdict **BLOCKED**. alembic head `0043_i08_registry_strategy_fks`,
`ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.
ADIM 86 kayıtsız inen #765 (P1 parity kanıtı) + #766 (P2 wiring) kaydetti.

**P-C2 §D.1 artık 3'te 2:** leg 1 flat (`tick_data_leg` 1/1), leg 2 flat
(`strategy_mirror_leg` 2/2), **leg 3 açık ve bilerek** (`run_readiness_check` `per_item: 1`,
8 → 18) — batch'lemek **hangi satırın kazandığı** sorusudur = **G15, İMZASIZ**. DOKUNMA.

## Sıradaki iş — ÖNCE ÖLÇ, sonra seç

- **`C3` İNDİ (#777 = §ADIM 85). Sıradaki mühendislik kalemi `C4`** — adaptörün üretim
  çağıranı + tick-adımlı iptal kontrol noktası + tripwire'ın DARALTILMASI (silinmesi DEĞİL).
  `C3`'ün `C4`'e devrettiği iki ölçülmüş kalem `docs/ADIM85_LANDED_KICKOFF.md`'de.
- **Kolay performans bacağı KALMADI** — yeni bir N+1 iddia etmeden önce ölç.
- Kabul borcu sayıları: tek otorite `docs/audit/acceptance_coverage_baseline.json` `ceilings`.
- **İmzalı:** G9 (`APPROVED as stated`) + G13 (`FOLD`) — **ADR-0002 §13.2**, PR #753.
  `closure_product_decisions`'ta bulamamak "imzasız" demek değildir.
  **İmzasız:** Karar 1 (#552) · Karar 3 (#559) · G12 · G15 · G4 · G8 · G14. G10 talep edilmedi.
  **BRİFİNGLİ ≠ İMZALI — imzasız bir kapının arkasındaki slice'a BAŞLAMA.**

## PAZARLIKSIZ

- **Yeşil exit code kanıt DEĞİL.** Postgres yoksa entegrasyon suite'i `exit 0` + skip verir.
  `pg_ctlcluster 16 main start` → `entropia`/`entropia` rol+DB → sonra **nokta mı `s` mi** BAK.
- **Alt küme koşarken `--no-cov`** (tek dosyalık koşu paketi ~%4 ölçer, kapı sahte kırmızı verir).
- **Negatif kontrolün NEDEN kırmızıya döndüğünü oku**, ve bir ratchet satırının **SINIRINI**
  da ölç: `strategy_mirror_leg` batch kaldırılınca kırmızı, batch yerindeyken per-item geri
  konunca **yeşil kalır** (ısınmış identity map). Sınırı yazılmayan slope-0 bir yanılsamadır.
- **Mutation harness'ı:** pristine kopya + geri yükleme **mutlak yolla**, **md5 ile doğrula**,
  sonra `git diff --quiet`.
- **`guard-git.sh` komut dizesinin TAMAMINDA arar** — force-push metnini başka komutla
  aynı çağrıya koyma.
- **Artefakt çakışmasını yeniden ÜRETEREK çöz:**
  `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..` (`--root ..` şart).
- **Ratchet / baseline / golden / coverage eşiğini İNDİRME.**
- Kapanışta ritüelin 1–6. maddesi (CLAUDE.md §Session CLOSING): PROJECT_HISTORY → handoff
  (`## Next:` başlığını SİLME, gövdeye ekle) → yeni kickoff `current` + öncekini `historical`
  → CLAUDE.md ince özet → memory checkpoint → codemap (gerekmiyorsa YAZILI belirt) → PR.
```
