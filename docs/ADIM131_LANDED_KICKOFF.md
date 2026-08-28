<!-- doc-status: current -->

# ADIM 131 — `G10` İMZALANDI (`A`) · sıradaki kalem **`C9` / ADIM 20**

**Taban:** `origin/main` @ `a9f9edcc` (ADIM 130, PR #867) · **Dal:** `docs/stage-131-landed`

---

## Nerede duruyoruz

**ADR §16 Gate 2 (`G10`) ONAYLI** — `A` — ŞİMDİ ver, `alimirbagirzade`, 2026-08-28
(`docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md` §*Yeniden talep — Gate 2,
**İKİNCİ** istek*). `C9` / ADIM 20 PR'ının önündeki **karar** kapısı kalktı.

**Bu slice bir LIFT DEĞİLDİR.** `SHARED_ALLOCATION_STATUS` = `future_dev`, `capability.py`
el değmedi, `ENGINE_VERSION` bump edilmedi, golden el değmedi, migration yok;
`backend/src`, `backend/tests` ve `frontend/src`'te **sıfır satır**. Blocker DEĞİŞMEDİ
(1 — yalnız A-08), **BLOCKED**. Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 131.

**Ölçülmüş:** kapı (`test_lifting_containment_requires_gate2_approval`) **tek bir literal
değişmeden sustu** — 9 passed / exit 0, `git diff --stat` tek dosya (karar belgesi), test
dosyası byte olarak el değmedi. Ve **yeşil yeterli sayılmadı**: bayrak zaten aşağıda olduğu
için kapı onay okunmadan da yeşil kalırdı → onayın gerçekten okunduğu ayrıca ölçüldü
(`_gate2_is_approved(<gerçek belge>) -> True`, `_lift_without_gate2("active_v1", …) -> False`;
ADIM 130'da `True` idi).

---

## Sıradaki kalem — **`C9` / ADIM 20: the lift**

Sıralı planın W8'i: **`C9` YALNIZ koşar — başka hiçbir PR açık olamaz.**

**Pazarlıksız beş kalem (hiçbiri hatırlanmıyor; hepsi ya zorlanıyor ya ölçülmüş):**

1. **`ENGINE_VERSION`'ı TEKRAR bump et.** `C7`'nin bump'ı A16'nın *kayıt* değişikliği için
   harcandı ve A15'i **kapatmaz** →
   `test_lifting_containment_requires_a_second_engine_version_bump` (dört köşeli predicate)
   zorlar. Bump ile birlikte `engine_golden_digests.json` **ve**
   `docs/generated/repository_facts.md` **aynı commit'te** yeniden üretilir — golden dosyası
   `engine_version`'ı **kendi içinde** taşır, yani tazelemesiz bir bump *tasarım gereği*
   gürültülü patlar.
2. **Ön koşul 17 — OD-2 mark policy.** `MARK_STALENESS_POLICY` literali
   `execution_content` **İÇİNDEDİR** → çevirmek **her `execution_key`'i kaydırır**; o
   namespace kayması md. 1'in bump'ıyla **aynı** commit'e aittir. **Politikayı yazmadan
   literali çevirme** — `clock.py::ItemTickView.staleness_ms` boşluğu bugün **ÖLÇER, sınır
   UYGULAMAZ**. İki yazım var ve testle bağlı: `manifest.py::MARK_STALENESS_POLICY` +
   `execution/provenance.py::MARK_STALENESS_POLICY` (`test_a16_manifest_policy_parity.py`).
3. **Ön koşul 18 — `CONTENTION_SELECTION_STATUS`.** Yazılacak kod **yok** (onay ADR §13.1'de
   2026-08-05'te alınmış), ama **flip sonrası DEĞERİ hiçbir belge adlandırmıyor** ve
   `capability.py` REMOVAL CONDITION #4 (*"symmetric"*) ile OD-3(a) `pin_order_admission`
   (kıtlıkta düşük pin'i kayırır) **ÇELİŞİR**. Ürün sahibi 2026-08-28'de `C` dedi: çelişki
   **`C9`'a ADIYLA devredildi**. Etiketi çevirmek
   `test_the_od3_selection_rule_is_labelled_as_pending_approval`'ı kırmızıya çevirir —
   **kasıtlı**, lift'in bir parçasıdır.
4. **Ön koşul 22'nin kalanı = md. 1 + A22.** A16 ✅ (ADIM 126),
   `build_portfolio_manifest` wiring ✅ (ADIM 116), A19 etiket yarısı ✅. **A22** = tam
   backend suite `--cov-fail-under=90`'da yeşil, **tek çağrı**, **exit code AYRI okunur**.
5. **Lift pinleri kasıtlı olarak güncellenir:**
   `test_oracle_portfolio_containment_gate.py` içindeki `future_dev` pinleri
   (`test_the_containment_flag_and_engine_version_are_both_untouched` vd.) — bunlar
   **gevşetilmez, lift'in EYLEMİ olarak** değiştirilir. `G10` kapısı ise kendiliğinden
   sessizdir, ona dokunma.

**Ayrıca `C9`'un stop condition'ı hâlâ geçerli:** *"Any of the 22 preconditions unmet →
do not open this PR."* Gate 2 artık onaylı, ama **17/18/22 KIRMIZI** ve üçünü de `C9`'un
kendisi kapatır — yani `C9` PR'ı onları **içinde** kapatarak açılır, onlar açıkken değil.

**A-08 (#514) ayrı hattır ve AÇIK.** `C9` inse bile nihai RC verdict'i sonuçlanamaz; ajan o
issue'ya dokunmaz (`human-only`). **Blocker sayısı `C9` ile de DEĞİŞMEZ.**

---

## Tuzaklar

- **Yeşil bir kapı iki dünyanın ortak çıktısı olabilir.** Bu slice'ta kapı, onay okunmadan
  da yeşil kalırdı (bayrak aşağıda) → *sustu* ile *onayı gördü* ayrı ayrı ölçüldü.
- **`doc-status: historical` belgeler otorite değildir**; özellikle
  `docs/audit/unified_portfolio_oracle_acceptance.md`'nin **A16/A17/A21** satırları bugün
  karşı-olgusaldır (ADIM 130'da ölçüldü, **bilerek düzeltilmedi** — donmuş kayıt).
- **İmza kutusu BÖLÜM bazında okunur**; `G14`'ün dosyasında dört ayrı kutu var.
- **Alt küme koşarken `--no-cov`**; **wrapper subshell'in exit code'u pytest'in DEĞİLDİR**.
- **Uzun suite koşarken `docs/` düzenleme** — documentation-truth kapısı çalışma ağacını
  okur ve sahte kırmızı verir (ADIM 128'de yaşandı; ADIM 130 kapıyı nihai ağaçta ayrıca
  koşarak kaçındı).

---

## Paste-ready resume prompt

```
ENTROPIA — `C9` / ADIM 20: THE LIFT (Gate 2 ONAYLI)

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: ADIM 131'de ADR §16 Gate 2 (G10) İMZALANDI — `A` — ŞİMDİ ver, alimirbagirzade,
2026-08-28. C9'un önündeki KARAR kapısı kalktı. Kapı
test_oracle_portfolio_containment_gate.py::test_lifting_containment_requires_gate2_approval
artık sessiz (ölçüldü: _gate2_is_approved -> True). Ön koşul 17/18/22 KIRMIZI ve üçü de
C9'un kendi teslimatı. Otorite: docs/PROJECT_HISTORY.md §ADIM 131 +
docs/ADIM131_LANDED_KICKOFF.md.

GÖREV: C9 — SHARED_ALLOCATION_STATUS = "active_v1". YALNIZ koş, başka PR açık olmasın.
  ÖNCE ÖLÇ: 22 ön koşulu koda karşı yeniden say (defterler donmuştur, otorite değildir).
  Sonra kickoff §"Sıradaki kalem"in beş pazarlıksız maddesini SIRAYLA uygula:
    1) ENGINE_VERSION'ı TEKRAR bump et + golden ve repository_facts'i AYNI commit'te üret
    2) ön koşul 17 (OD-2 mark policy): politikayı YAZ, sonra literali çevir — iki yazım da
       (manifest.py + execution/provenance.py), parite testi bağlar
    3) ön koşul 18: CONTENTION_SELECTION_STATUS flip + capability.py #4 ↔ OD-3(a)
       çelişkisini ADIYLA çöz (2026-08-28'de C9'a devredildi)
    4) A22: tam suite --cov-fail-under=90, TEK çağrı, exit code AYRI oku
    5) lift pinlerini KASITLI güncelle (gevşetme değil, lift'in eylemi)

YASAKLAR: golden'ı "kırmızı olduğu için" yeniden üretme — her oynayan digest'in İMZALI
  sebeple oynadığını tek tek doğrula (#720 emsali). Ön koşulu ölçmeden yeşil sayma.
  A-08 (#514) ayrı hattır; o issue'ya DOKUNMA (human-only) ve RC verdict'ini
  "BLOCKED değil" diye yazma.

TUZAKLAR:
  - Yeşil bir kapı iki dünyanın ortak çıktısı olabilir; "sustu" ile "gördü" ayrı ölçülür.
  - doc-status: historical belgeler ölçtükleri anı dondurur; unified_portfolio_oracle_
    acceptance.md'nin A16/A17/A21 satırları bugün karşı-olgusaldır ve OTORİTE DEĞİLDİR.
  - Alt küme koşarken --no-cov. Wrapper subshell'in exit code'u pytest'in DEĞİLDİR.
  - Uzun suite koşarken docs/ düzenleme (documentation-truth kapısı sahte kırmızı verir).

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB.
  backend/.venv yoksa `uv sync --all-extras` (mutlak yol kullan).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
