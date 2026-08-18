<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 81 LANDED — §2 kapı tablosu tazelendi (PR #769) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 81. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Kapanış yazılırken main **`1741b03`**. **Ürün kodu değişmedi**: migration yok, OpenAPI
  değişmedi, `ENGINE_VERSION` değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- Tek dosya, **+93/−30**: `docs/implementation/final_closure_ordered_plan_2026-08-13.md` §2
  (+ `F2` slice bloğu, mermaid kapı düğümleri, §6 envanteri, §7 md. 2).
- **Kapı sayımı artık ölçülmüş: 16 kayıtlı · 11 açık · 11 bloklayan.** Çözülmüş beş: **G5**,
  **G6**, **G7**, **G9**, **G13**. Açık: **G1 G2 G3 G4 G8 G10 G11 G12 G14 G15 G16**.
- **G4 · G12 · G15 → BRIEFED ama İMZASIZ** (PR #755 / #752 / #747). **G11 artık imzalanacak
  yeri olmayan TEK kapı** — ve PR **#771** açıkken tam olarak onu brifliyor, yani bu satır
  **yarın bayatlayabilir**: okumadan önce ölç.

> **PAZARLIKSIZ — brifingli ≠ imzalı.** Bir signature block yaratmak bir kapıyı **kapatmaz** ve
> sayımı **değiştirmez**. Bu belgenin (ve planın) en kolay yanlış okunan yeri budur. İmzasız bir
> kapının arkasındaki slice'a **BAŞLAMA**, ürün kararı **UYDURMA**.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam dosya/sembol adlarıyla)

- `docs/implementation/final_closure_ordered_plan_2026-08-13.md` **§2** — kapı tablosunun
  **tek** otoritesi. Üç sayı (kayıtlı / açık / bloklayan) artık **yan yana** duruyor: yazıldığı
  günkü değer ve `Re-measured 2026-08-18` sütunu. **Yeni bir kapı durumu ölçtüğünde eski
  sütunu SİLME** — belge `historical`dır ve düzeltmeler alıntılanarak yapılır.
- `docs/decisions/closure_g4_cap_overflow_2026-08-17.md` (**PR #755**) — G4'ün brifi.
  **Dört disposition** taşır (A blocker / B-i / B-ii cap policy / C canonical / **D
  gözlemlenebilir clamp**) ve §Karşılaştırma tablosu beş şekli karşılaştırır.
  **`F2`'nin plan hücreleri bu brifin ÖNCESİNDEN kalmadır** — seçenek kümesi için **brifi oku**.
- `docs/decisions/closure_g15_external_row_winner_2026-08-17.md` (**PR #747**) — G15'in brifi;
  imza kutusunun yanında **bir SAYI olan ön koşul kutusu** var (üretimdeki duplication count) ve
  o sayı **hâlâ alınmadı** (bu container'da `DATABASE_URL` tanımsız → alınamaz).
- `docs/decisions/closure_product_decisions_2026-08-13.md` §**Karar 6** (**PR #752**) — G12'nin
  bloğu. §**Karar 2** = G6 + G7, `[x] A1+A2`, imzalı **2026-08-14**.
- `docs/adr/0002-…md` §**13.2** — **G9** (APPROVED) ve **G13** (FOLD) imzalarının yaşadığı yer.
  **İmza karar belgesinin kutusunda DEĞİL, ADR'dedir**; #774 kutuları geriye dönük işaretledi
  ama **işaret otorite değildir**.
- `docs/decisions/closure_participant_importer_allowlist_2026-08-18.md` (**PR #761**) —
  `C3`'ün importer-allowlist kararının brifi. **Bu slice'ta yazılmadı, ama sıradaki işin
  önündeki kapı budur** (aşağı bak).

## Pazarlıksız — bu slice'ın öğrendikleri

1. **"Beş kapıyı ölçtüm" altıncıyı ölçtüğün anlamına gelmez.** İlk sürüm *"13 açık"* dedi çünkü
   G6/G7 bayat tablodan **ölçülmeden** taşındı. Bir tabloyu tazelerken **her satırı** ölç ya da
   hangilerini ölçmediğini **açıkça yaz**. Bunu bir kapı değil **bir insan** yakaladı — CI
   sayıların doğruluğunu okumaz.
2. **Tazelemeye başlamadan ÖNCE açık PR'lara bak.** #769 ve #772 aynı bölümü on dakika arayla
   bağımsız tazeledi (~60 satır çakışma). `mcp__github__list_pull_requests` bir aramadır, bir
   dalın çöpe gitmesi bir gündür. Çakışma çıkarsa **sıra değil ÖLÇÜM kazanır**: burada sonradan
   açılan dal daha doğruydu ve **taban o oldu**.
3. **Uzun açık kalan bir docs PR'ının iddiaları main ilerledikçe bayatlar.** *"Kutular hâlâ
   boş"* cümlesi #774 inince yanlış oldu. **Her push'tan önce kendi iddialarını yeniden oku** —
   özellikle *"hâlâ"*, *"henüz"*, *"şu an"* içeren cümleleri.
4. **Boş kutu, imzasız kapı DEMEK DEĞİLDİR** (imza başka belgede olabilir) ve **işaretli kutu
   da otorite değildir**. Otorite sırası md. 2.
5. **`cancelled` ≠ `failure`.** Job `playwright install` içinde asılıp öldürüldüyse **hiçbir
   test gövdesi koşmamıştır**. Çare rerun; test düzeltilmez, baseline indirilmez.
6. **auto-merge dalı KENDİ GÜNCELLEMEZ.** `auto=squash` açık bir PR `behind` durumunda bekler.
   `strict: true` altında main'in her ilerlemesi ~50 dk'lık yeni bir tur doğurur.
7. **`update_pull_request_branch` docs PR'ında KULLANILMAZ** (ADIM 61 emsali). Bu kez kayıp
   yapmadı ve bu **kanıt değildir** — main'i yerelde al, `'^-## '` ile doğrula.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **`C2` İNDİ (PR #759, `c78b15b`) ve kaydı YOK.** Bu kapanış onun anlatısını **yazmadı**
  (ADIM 69/70 dersi: bir kapanış başkasının slice'ının anlatısını uydurmaz). Ölçülen:
  `portfolio_engine.py::ItemParticipant.settle` ve `::finalize` **zorunlu** Protocol üyesi,
  `PHASE_ORDER` **dokuz faz** (`P10` dahil), `iter_portfolio` ve `PORTFOLIO_LOOP_VERSION`
  yayımlı.
- **Sıradaki mühendislik kalemi `C3`** — `execution/participant.py` adaptörü. Ölçüldü:
  `backend/src/entropia/domain/backtest/execution/` altında **`participant.py` YOK**.
  Önündeki kapı bir imza değil bir **insan incelemesidir**: containment gate'in importer
  kontrolü (`portfolio_engine.__all__` Protocol'ün tiplendiği altı tipin hiçbirini yeniden
  yayımlamıyor) → allowlist genişletmesi **bilinçli ve gözden geçirilmiş** olmalı. Brif
  **#761'de indi**; **imzasızdır**.
- **Kapı brifleri ile ilgilenen bir slice için:** `G11` tek imzasız-ve-briefsiz kapıydı, **PR
  #771 açık** ve onu brifliyor. **İkinci bir brif YAZMA** — önce `list_pull_requests`.
- **Kabul borcu hattı ayrı ilerliyor:** batch 08/09 **PR #768'de açık** (91 partial / B 60),
  main'de ADIM 80 sonrası taban **96 / B 65**. **Kabul defteri SERİ bir kaynaktır** — ikinci
  inen taraf rebase edip **yeniden dondurmalı**.

### Bugün main'e inen, PROJECT_HISTORY kaydı GÖRÜNMEYEN PR'lar (ölçüldü, anlatı YAZILMADI)

| PR | Konu | Kayıt |
|---|---|---|
| **#759** | **`C2` — `settle` + `finalize` + P10 faz döngüsüne eklendi (ÜRÜN KODU)** | **YOK** |
| #752 | G12 (Karar 6) signature block'u yaratıldı | YOK |
| #755 | G4 cap-overflow brifi | YOK (yalnız başka kayıtlarda anılıyor) |
| #747 | G15 external-row winner brifi | YOK (yalnız anılıyor) |
| #761 | `C3` importer-allowlist brifi | YOK |
| #770 | G9/G13 imzalarının NEREDE verildiğinin kaydı | YOK |
| #774 | Karar 4/5 kutuları işaretlendi | YOK |
| #773 | prompt paketi canlı kickoff'u adlandırmayı bıraktı | YOK |
| #750 · #753 | G9/G13 blokları + ADR §13.2 amendment'ı | ADIM 76 içinde **anılıyor**, kendi kaydı yok |

> **Bunların ADIM kayıtlarını YAZMA.** Kaydı **sahibinin** yazması gerekir; bir kapanış
> başkasının slice'ının anlatısını uyduramaz. Burada yalnız **işaret edilir**. En ağırı
> **#759**: bir **ürün kodu** slice'ı kayıtsız duruyor.

## Çalışma yöntemi (bu dalgada işe yarayan)

- **Durumu prompt'tan alma, ölç:** `git fetch --all --prune && git log --oneline origin/main -8`
  · `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -6`. Bu oturumun devir promptu tabanı
  `f905acc` sanıyordu; gerçek `1741b03`'tü.
- **Canlı kickoff'u ADIYLA arama, BULDUR** (#773'ün dersi):
  `for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do head -3 "$f" | grep -q 'doc-status: current' && echo "$f"; done`
  — `head -3` **zorunlu**, kapı yalnız ilk 3 satırı okur ve birçok belge gövdesinde bu dizgeyi
  **anlatır**.
- Push etmeden önce, exit code **ayrı** okunarak:
  `cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check`
  → *"documentation-truth gate OK"* + `exit=0` görmeden push etme ·
  `git diff --cached -- docs/ | grep '^-## '` → **boş** olmalı.
- Ürün kodu değişmiyorsa **suite koşma** — ama **koşmadığını açıkça yaz**.
- `gh` CLI bu container'da **kurulu değil**; GitHub için MCP araçları (`mcp__github__*`).
  **GraphQL 403** → draft'tan çıkarmayı ajan yapamaz. Actions log endpoint'i proxy'de 403 →
  `mcp__github__get_job_logs`.

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, sayıyı ya da kapı durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff'u BULDUR (adıyla arama):
    for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do
      head -3 "$f" | grep -q 'doc-status: current' && echo "$f"
    done

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA (ADIM 81'in (b) dersi):
  mcp__github__list_pull_requests(state=open) → dokunacağın dosyaya dokunan
  açık PR var mı? Varsa ONU oku; ikinci bir tazeleme/brif AÇMA.

KAPI DURUMU (ADIM 81'de ölçüldü — YENİDEN ÖLÇ):
  16 kayıtlı · 11 açık · 11 bloklayan. Çözülmüş: G5 G6 G7 G9 G13.
  G4/G12/G15 BRIEFED ama İMZASIZ. G11 için brif PR #771'de AÇIK olabilir.
  BRİFİNGLİ ≠ İMZALI. İmzasız kapının arkasındaki slice'a BAŞLAMA (F2 → G4,
  F3 → G1+G2+G3, C6 → G11+G12, C9 → G8+G14+G10, A-08 → ajan kapatamaz).

SIRADAKİ MÜHENDİSLİK KALEMİ: C3 — execution/participant.py adaptörü.
  C2 PR #759'da İNDİ (settle/finalize zorunlu Protocol üyesi, PHASE_ORDER 9 faz).
  C3'ün önündeki kapı bir imza değil INSAN İNCELEMESİDİR: containment gate'in
  importer allowlist'i. Brif docs/decisions/closure_participant_importer_
  allowlist_2026-08-18.md (PR #761) — İMZASIZ. Genişletmeyi sessizce yapma.

ALTERNATİF HAT — kabul borcu batch 11: sınıf-B'den TEK belge + TEK yüzey seç.
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report
  ZİNCİR: batch 08/09 PR #768'de açık (91 / B 60), main tabanı 96 / B 65.
  İkinci inen rebase edip YENİDEN DONDURMALI.

KAYITSIZ İNEN SLICE'LAR (yalnız işaret et, ANLATI UYDURMA): #759 (ÜRÜN KODU),
  #752 #755 #747 #761 #770 #774 #773. Kaydı sahibinin yazması gerekir.

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test,
OpenAPI drift, çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
