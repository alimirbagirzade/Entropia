<!-- doc-status: historical -->

# ADIM 130 — `G10` yeniden talep edildi ve ZORLANABİLİR kılındı · sıradaki kalem

**Taban:** `origin/main` @ `80f6cc7d` (ADIM 129, PR #866) · **Dal:**
`claude/entropia-c9-onkosul-17-c35ba6`

---

## Nerede duruyoruz

**Bu slice `backend/src` ve `frontend/src`'te sıfır satır değiştirdi.** Migration yok,
`ENGINE_VERSION` değişmedi, OpenAPI değişmedi, golden el değmedi, `capability.py` el
değmedi. Blocker DEĞİŞMEDİ (1 — yalnız A-08), **BLOCKED**.

`docs/audit/final_closure_delta_audit_2026-08-25.md` §10'un dokuz maddelik sırası ağaca
karşı ölçüldü. **`C9`-dışı ve insan-dışı tek açık kalem md. 7'ydi: `G10`'u talep etmek.**
Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 130.

---

## Bu slice'ın bıraktıkları (yeniden kullanım çapaları — TAM sembol adlarıyla)

| Çapa | Ne yapar |
|---|---|
| `test_oracle_portfolio_containment_gate.py::test_lifting_containment_requires_gate2_approval` | `SHARED_ALLOCATION_STATUS == "active_v1"` iken Gate 2 onaylı değilse **kırmızı** |
| `…::_gate2_is_approved` | `G10` karar belgesinin **ikinci talep** kutusunu ayrıştırır; **fail-closed** (bölüm yok / iki şık işaretli / şık eksik → `AssertionError`) |
| `…::_lift_without_gate2` | dört-köşeli predicate: `(status, document) -> bool` |
| `…::_request_box` | sentetik kutu üreteci (`_request_box("A")` = onaylı, `_request_box()` = ertelenmiş) |
| `…::_GATE2_DECISION` / `_GATE2_REQUEST_HEADING` | belgenin yolu ve **canlı** kutunun bölüm çapası |
| `closure_g10_…md` §*Yeniden talep — Gate 2, **İKİNCİ** istek* | **BOŞ** imza kutusu (`A`/`B`/`C`) + üç maddenin ölçüm tablosu |

---

## Sıradaki kalem — ve o bir KOD DEĞİL

**`G10` imzası (ADR §16 Gate 2).** Kutu `docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md`
§*Yeniden talep — Gate 2, **İKİNCİ** istek* bölümünde ve **BOŞTUR**. Ajan onu dolduramaz.

- **`A` işaretlenirse** → `C9` / ADIM 20 PR'ı açılabilir; kapı kendiliğinden susar,
  **testte değiştirilecek literal yoktur**.
- **`B` işaretlenirse** → gerekçe yazılır, kapı yerinde kalır.
- **`C` işaretlenirse** → `C9` programı durur, containment kalıcı olur.

**`A` verilirse `C9`'un pazarlıksız kalemleri** (hepsi ölçülmüş, hiçbiri hatırlanmıyor —
zorlanıyor):

1. **`ENGINE_VERSION`'ı TEKRAR bump et.** `C7`'nin bump'ı A16'nın *kayıt* değişikliği için
   harcandı ve A15'i **kapatmaz** →
   `test_lifting_containment_requires_a_second_engine_version_bump` zorlar.
2. **Ön koşul 17** — OD-2 mark policy: `MARK_STALENESS_POLICY` literali `execution_content`
   İÇİNDEDİR, çevirmek **her `execution_key`'i kaydırır**; o namespace kayması md. 1'in
   bump'ıyla **aynı** commit'e aittir. Politikayı yazmadan literali çevirme.
3. **Ön koşul 18** — `CONTENTION_SELECTION_STATUS`: yazılacak kod yok, ama **flip sonrası
   DEĞERİ hiçbir belge adlandırmıyor** ve `capability.py` #4 (*"symmetric"*) ile OD-3(a)
   `pin_order_admission` **çelişir**. Ürün sahibi 2026-08-28'de `C` dedi: çelişki `C9`'a
   **adıyla** devredildi.
4. **Ön koşul 22'nin kalanı** = md. 1 + **A22** (tam suite `--cov-fail-under=90`, tek
   çağrı, exit code ayrı okunur). A16 ✅ (ADIM 126), `build_portfolio_manifest` wiring ✅
   (ADIM 116).
5. Sıralı planın W8'i: **`C9` YALNIZ koşar — başka hiçbir PR açık olamaz.**

**A-08 (#514) ayrı hattır** ve `A` verilse bile RC verdict'ini bloklar; ajan o issue'ya
dokunmaz (`human-only`).

---

## Tuzaklar (bu slice'ta ölçüldü)

- **İmza kutusunu BÖLÜM bazında oku** — `G14`'ün dosyasında dört ayrı kutu var; dosya
  düzeyinde `grep '☑'` hangi kararın imzalandığını söylemez (ADIM 119).
- **`and` kısa devre yapar.** Bir kapıyı `lifted and X` diye yazarsan, bayrak aşağıdayken
  `X` **hiç koşmaz** — ve `X` senin fail-closed yarınsa lift gününe kadar uyur. Ayrı ve
  koşulsuz ölç. (NC-1 bunu birinci elden gösterdi.)
- **`doc-status: historical` bir denetim BAYAT olabilir ama YANLIŞ değildir.** Dört denetim
  belgesi de öyle ölçüldü ve **el değmedi**. Özellikle
  `docs/audit/unified_portfolio_oracle_acceptance.md`'nin A16/A17/A21 satırları bugün
  karşı-olgusaldır — **otorite değildir**, `C9` ona güvenmesin.
- **`pytest … | tail` KULLANMA** ve wrapper subshell'in exit code'unu pytest'inki sanma.
- **Alt küme koşarken `--no-cov`** (tek dosyalık koşu paketi ~%4 ölçer, kapı sahte kırmızı
  verir).

---

## Paste-ready resume prompt

```
ENTROPIA — C9 öncesi: `G10` (ADR §16 Gate 2) İMZA BEKLİYOR

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: ADIM 130 §10'un sırasını ölçtü. `C9`-dışı ve insan-dışı tek açık kalem `G10`'du.
`B — ERTELE`'nin yeniden talep koşulunun ÜÇ maddesi de tahliye edildi (md. 2 = `G14`'ün
`B` yarısı + #544, 2026-08-27'de kapandı). Talep yazıldı, kutu BOŞ bırakıldı, ve
"G10 unsigned -> do not open this PR" stop condition'ı ARTIK ZORLANIYOR:
test_oracle_portfolio_containment_gate.py::test_lifting_containment_requires_gate2_approval
(fail-closed; belgeyi okur, onay verilince kendiliğinden susar).
Otorite: docs/PROJECT_HISTORY.md §ADIM 130 + docs/ADIM130_LANDED_KICKOFF.md.

GÖREV: ÖNCE imza kutusunu BÖLÜM bazında oku —
  docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md
  §"Yeniden talep — Gate 2, **İKİNCİ** istek"
- Kutu HÂLÂ BOŞSA: `C9` PR'ı AÇILAMAZ. İmza bir insan kararıdır; doldurma. Bunun yerine
  ön koşul 17/18/22'nin ÖLÇÜMÜNÜ tazele ya da A-08 dışı bir borç kalemi al.
- `A` işaretlenmişse: `C9` runnable. Kickoff §"Sıradaki kalem"in beş pazarlıksız
  maddesini uygula (ikinci ENGINE_VERSION bump → 17 → 18 → A22 → YALNIZ koş).
- `B`/`C` işaretlenmişse: gerekçeyi oku ve ona uy.

YASAKLAR: imza kutusu doldurma. capability.py'yi Gate 2 onaylanmadan ELLEME.
  ADR §13.1/§14 invariant tablosunu YENİDEN YAZMA. doc-status: historical belgeleri
  düzeltme (bayat olabilirler, yanlış değildirler).
  MARK_STALENESS_POLICY'yi politikayı yazmadan ÇEVİRME.

TUZAKLAR:
  - İmza kutusu BÖLÜM bazında okunur; dosya düzeyinde grep yanıltır (ADIM 119).
  - `and` kısa devre yapar: `lifted and X` yazarsan X bugün HİÇ koşmaz (ADIM 130 NC-1).
  - doc-status: historical bir denetim ölçtüğü anı dondurur; unified_portfolio_oracle_
    acceptance.md'nin A16/A17/A21 satırları bugün karşı-olgusaldır ve OTORİTE DEĞİLDİR.
  - Yeşil bir NC bir bulgudur; kırmızının HANGİ assertion'da olduğunu oku.
  - Alt küme koşarken --no-cov. Wrapper subshell'in exit code'u pytest'in DEĞİLDİR.

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB.
  backend/.venv yoksa `uv sync --all-extras` (mutlak yol kullan).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
