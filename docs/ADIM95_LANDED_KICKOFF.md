<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 95 LANDED — üretilmiş kabul artefaktlarının drift kapısı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 95. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`d47c5ba`** (en yüksek kayıt **ADIM 93**). Bu slice **95**.
- **Ürün kodu değişmedi** — `backend/src`'te sıfır satır; migration yok, OpenAPI değişmedi,
  `ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.
- **Tavanlar OYNAMADI:** 73 partial / 7 uncovered · A=1 B=41 C=6 D=32. Bu bir kabul partisi
  **değil**, bir **araç** slice'ı.
- **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

## Ne sevk edildi

`acceptance_semantic_scan.py` iki checked-in artefakt **üretiyor**. **İddia ölçümle
daraltıldı:** defter **zaten** kapılıydı — `tests/unit/test_acceptance_semantic_map.py::
test_the_debt_ledger_is_not_stale` onu her pytest koşusunda map ile karşılaştırıyor.
**Kapısız olan RAPORDU**, ve sürüklenen de tam olarak o oldu: **ADIM 60'tan (#719) beri yedi
kabul partisi** (`234 covered / 126 partial` ↔ ölçülen `276 / 84`), CI hep yeşildi.

| Sembol / yer | Ne |
|---|---|
| `acceptance_semantic_scan.py::check_generated` | rapor + defteri render edip diskle karşılaştırır; **hangisinin** bayat olduğunu ayrı söyler |
| `::_rendered_report` / `::_rendered_ledger` | **yazıcı ile kapı tek renderer'ı paylaşır** |
| `ci.yml` | `--report --check-generated --ratchet` (**yeni job DEĞİL**, mevcut adıma bayrak) |
| `tests/contract/test_acceptance_generated_drift_guard.py` | YENİ, 9 test, negatifleri kanıtlı |
| `tests/unit/…::test_the_ratchet_is_wired_into_ci` | ONARILDI: birebir literal → **bayrak** assert'i |

## Yöntem — bu slice'ın işe yarayan dört kuralı

1. **Kapıyı, kapatmayı iddia ettiği TARİHSEL kusurla sına.** En değerli negatif kontrol
   sentetik değildi: rapor `d012a63`'teki gerçek ADIM 60 sürümüne geri konuldu ve kapı kırmızı
   verdi — o yedi partilik sürüklenmeyi gerçekten yakalardı.
2. **Kapının kendi testini de negatif kontrolden geçir.** `ci.yml`'dan bayrağı düşürmek,
   `--ratchet`'i düşürmek ve yazıcıyı ortak renderer'dan koparmak — üçü de kırmızı verdi.
3. **Yazıcı ile kapı aynı fonksiyondan geçmeli.** Ayrışsalardı kapı **tatmin edilemez**
   olurdu ve davranışsal testle görülmezdi → **kaynak düzeyi** assertion.
4. **TAM SUITE KOŞ — odaklı koşu yalnız senin bildiğin kapıları koşar.** Odaklı testler
   yeşilken tam suite `test_the_ratchet_is_wired_into_ci`'yi kırdı, ve o dosyayı okumak
   **defterin zaten kapılı** olduğunu — yani bu slice'ın ilk gerekçesinin **yanlış**
   olduğunu — ortaya çıkardı. **Kapı eklerken o alanda hâlihazırda ne pinli, önce onu ara.**

## Sıradaki slice için — ölçülmüş adaylar

**(a) Kabul borcu batch 17:** `--report` ile ölç, sınıf-B'den **tek belge + tek yüzey** seç.
Tavan dosyadan okunur: `docs/audit/acceptance_coverage_baseline.json` `.ceilings`
(bu kapanışta **73 partial / B 41 / uncovered 7 / total 383**). **Ratchet yalnız aşağı iner.**
Doc 02, 05, 07, 12, 17, 18'in backend borcu bitti; yoğunluk artık **AT / RF / RD / MB / ESP**.

**(b) Üretilmiş belgelerin kapı taraması:** bu slice yalnız **iki** kabul artefaktını kapıladı.
`repository_facts.*` ve `openapi.json` kendi guard'larına sahip; **depoda başka kapısız
üretilmiş belge var mı taranmadı** — tarayıp listelemek ayrı, küçük bir slice.

**(c) Mühendislik hattı:** `C3` = ADIM 85, `C4` = ADIM 92 (#799) main'de. Sıradaki kalem için
`docs/implementation/final_closure_ordered_plan_2026-08-13.md` §PACKAGE C'ye bak; **imzasız
kapı varsa BAŞLAMA** (`grep -l 'karar veren' docs/decisions/*.md` yetmez, **kutulara bak**).

## Tuzaklar (bu slice'ta canlı yaşandı)

- **Bir script'i test içinde `importlib` ile yüklerken `sys.modules[spec.name]` ata** — script
  bir `@dataclass` tanımlıyorsa `dataclasses` annotation'ları `sys.modules[cls.__module__]`
  üzerinden çözer; aksi hâlde **collection** aşamasında
  `AttributeError: 'NoneType' object has no attribute '__dict__'`.
- **CI satırını birebir literal olarak pinleyen test yazma** — yanına ikinci bir kapı eklenince
  kırılır ve kıran kişi onu *gevşetmeye* çalışır. Bayrakları **ayrı ayrı** assert et.
- **`git checkout -q <dosya>` bir negatif kontrolü geri alırken yanındaki yamayı da siler** —
  negatif kontrolden sonra **her zaman `git status` + kapıyı yeniden koştur**.
- **Test ekleyen slice `repository_facts`'i TAZELEMELİ** (ADIM 60 emsali, yine yaşandı).
- **`cmd | tail` sonrası `$?` `tail`'indir** — çıktıyı dosyaya yaz, exit code'u ayrı oku.
- **Numara iki kez taşındı** (92 → 94): kapanış yazılırken main iki kayıt birden aldı.
  Rebase **sekiz belge çakışması** verdi (üretilmiş dosyalar dahil) → dal main'e **sıfırlandı**,
  yalnız **dört kod dosyası** yeniden uygulandı, defter belgeleri yeni tabana karşı **yeniden
  yazıldı**. Çakışma çözerek taşımaktan ucuzdu ve daha az hata riski taşıdı.

## NUMARA — merge'den önce iki kez doğrula

Bu kapanış yazılırken main'in en yükseği **ADIM 93**, dolayısıyla bu **95**. Merge'den hemen
önce `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -3` koş; alınmışsa hem kaydı, hem
`ADIM95_LANDED_KICKOFF.md` **dosya adını**, hem handoff başlığını, hem `CLAUDE.md` bloğunu,
hem de **demote hedefini** taşı.

---

## Paste-ready resume prompt (bir sonraki temiz oturuma yapıştır)

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE ÖLÇ — hiçbir SHA'yı, sayıyı, kapı durumunu bu prompttan alma:
  git fetch --all --prune && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff'u BULDUR:
    for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do
      head -3 "$f" | grep -q 'doc-status: current' && echo "$f"
    done

İLK İŞ — ÇAKIŞMA KONTROLÜ (bu depoda slice kaybettirdi, birden çok kez):
  mcp__github__list_pull_requests(state=open)
  Bir dala dokunmadan ÖNCE YORUMLARINI DA OKU — paralel oturumlar PR yorumlarıyla
  koordine oluyor ve "bu dala push etmeyin" talimatı yorumda gelebilir; check tabına
  bakmak yetmez.

SEÇENEKLER:
 (a) Kabul borcu batch 17:
     cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report
     Sınıf-B'den TEK belge + TEK yüzey. Tavan: acceptance_coverage_baseline.json .ceilings
     (ADIM 95'te 73 partial / B 41 / uncovered 7 / total 383). Ratchet YALNIZ AŞAĞI iner.
     SINIFI notes'tan OKUMA, ürün kodunu ÖLÇ — ve bir çağrılanı izlerken ÇAĞIRANLARINI da
     kontrol et (bir sınıf-D bulgusu tam bu yüzden yanlıştı).
 (b) Üretilmiş belgelerin kapı taraması (ADIM 94 yalnız iki kabul artefaktını kapıladı).

ORTAM — integration testleri koşacaksan Postgres kur, yoksa suite SKIP eder:
  su postgres -c "PATH=/usr/lib/postgresql/16/bin:$PATH initdb -D /var/lib/postgresql/<x> -U entropia --auth=trust"
  (root olarak koşmaz) + uv sync --all-extras
  + TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@127.0.0.1:5432/<db>
  "exit 0 + N skipped" KANIT DEĞİLDİR. `cmd | tail` sonrası $? tail'indir.
  TAM SUITE KOŞ: odaklı koşu yalnız senin bildiğin kapıları koşar.

KAPANIŞ RİTÜELİ (altı madde) ve NUMARA: main'de en yüksek '## ADIM' + 1, merge'den
  hemen önce yeniden doğrula. Test eklediysen repository_facts'i TAZELE.
  Guard tuzağı: force-push ile default branch adını AYNI Bash komut dizesine koyma
  (commit mesajını önce Write ile dosyaya yaz).

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test,
OpenAPI drift, çoklu alembic head, historical Result davranışı değişimi.
```
