# DST fold ve DST gap: sessizce çözülmeye devam mı, `TIME_POLICY_INVALID` blocker'ı mı? (kapı **G8**)

> **KARAR İMZALANDI — 2026-08-26: `A1 + B2 + C1`.** Belge hazırlık olarak doğdu; imzalar
> §Karar 1/2/3'te **doldurulmuş** hâlde durur. Özgün banner şunu diyordu ve artık tarihseldir:
> *"BU BELGEDE HİÇBİR KARAR VERİLMEMİŞTİR … imza bloğu boştur."*
>
> Yazarın rolü **hazırlıktı**; kararı ürün sahibi / maintainer verdi.
> `closure_g11_deferred_fill_admission_2026-08-18.md`, `closure_g4_cap_overflow_2026-08-17.md`
> ve `closure_g15_external_row_winner_2026-08-17.md` ile aynı disiplin.

- **Tarih:** 2026-08-25
- **Base:** `origin/main` @ `74db6ff5` (`docs(stage-109): kayıtsız inen #820'nin kapanış ritüeli (#824)`)
- **İzleme:** GH **#559** (`product-decision`, `blocks-mixed-zone-axis`) — **2026-08-25'te
  yeniden AÇILDI**; 2026-08-18'de sıfır yorum / sıfır closing PR / sıfır kod değişikliğiyle
  kapatılmıştı (`docs/audit/final_closure_delta_audit_2026-08-25.md` §4 C-4).
- **Kapsam:** yerel duvar saatinin bir instant'a **1:1 eşlenmediği** iki hâl — *fold*
  (yılda bir kez iki defa yaşanan saat) ve *gap* (hiç yaşanmamış saat). **Yalnız** bunlar.
- **Bloklar:** `C9` (containment lift) — `closure_w0_containment_lift_preconditions_2026-08-17.md`
  §2 ön koşul **21**.
- **BLOKLAMAZ:** `C2`, `C3`, `C4`, `C6`, `G11`, `G12`, A-08. Bugün kritik yolda değildir.
- **Neden şimdi:** kapı, issue kapalıyken *"sağlandı"* diye okunuyordu. Yeniden açıldı;
  imzalanacak bir yeri yoktu. Bu belge o yeri açar, kararı vermez.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — Mekanizma tek satır, ve **iki okuyucuda da aynı**

`domain/market_data/validation_rules.py::_localize` (ingest) ve
`domain/backtest/funding.py::parse_utc` (funding takvimi) naive bir değeri aynı şekilde
yerelleştirir:

```python
moment.replace(tzinfo=source_zone).astimezone(UTC)
```

`datetime.fold` **varsayılan 0**'dır. Sonuç, `e2fa521` tabanından bugüne **bayt bayt aynı**:

| hâl | kaynak hücre (`America/New_York`) | çözülür | işaretlenir mi |
|---|---|---|---|
| **fold** — 2024-11-03 01:30 **iki kez** yaşanır | `2024-11-03T01:30:00` | `05:30:00Z` (**ilk**, EDT) | **hayır** — `timezone_unresolved=False` |
| **gap** — 2024-03-10 02:30 **hiç** yaşanmadı | `2024-03-10T02:30:00` | `07:30:00Z` | **hayır** — kabul edilir |

İki okuyucunun **anlaşması** bir kusur değil, korunması gereken bir özelliktir ve
`test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case` ile pinlidir.
Hangi seçenek imzalanırsa imzalansın **ikisi birlikte** değişmelidir.

## Ölçüm 2 — Erişilebilirlik issue'nun ima ettiğinden **DAR**, ve bu seçenekleri ucuzlatır

Fold/gap yalnız **gerçek bir `source_zone` geçilen** yollarda erişilebilir. Ölçüldü:

| yüzey | `source_zone` | fold'a değer mi |
|---|---|---|
| `jobs/research_data.py` (ingest), `jobs/market_data.py` (ingest) | revision'ın deklare ettiği zone | **evet** |
| `validation_rules.py` cross-row, `research_data/quality_rules.py` | aynı | **evet** |
| `domain/backtest/funding.py` satır okuyucusu | aynı | **evet** |
| `engine.py` (×2), `execution/costs.py`, `execution/clock.py`, `execution/rules.py`, `execution/fills.py` | **`source_zone=None`** | **hayır** — naive değer `None` döner (fail-closed) |

Yani motorun sıcak yolu bu soruya **hiç dokunmuyor**; karar **ingest + funding** yüzeyinde
uygulanır. Ayrıca `exchange` modu IANA taşımaz → zaten fail-closed; `UTC` modunda DST yok.
**Etki alanı: yalnız `custom` mod + DST gözeten bir IANA zone.**

## Ölçüm 3 — Blocker seçeneği **yeni sözcük dağarcığı GEREKTİRMEZ**

Sevk edilmiş kodlar hazır: `MARKET_DATA_TIMEZONE_UNRESOLVED`,
`RESEARCH_DATA_TIMEZONE_UNRESOLVED` (`shared/errors.py`, `quality_rules.py`) ve readiness
tarafında `TIME_POLICY_INVALID` (`readiness/enums.py`). `TimestampParse` zaten
`timezone_unresolved` bayrağını taşıyor ve K-01 dalı onu **fail-closed** kullanıyor —
blocker, var olan dalın **üçüncü bir sebebi** olur, yeni bir mekanizma değil.

## Ölçüm 4 — Geriye dönük denetimin **emsali var ve şekli belli**

`application/queries/timezone_audit.py` (K-01) **READ-ONLY**dir, hiçbir şeyi mutate etmez ve
gerekçesini kendi docstring'inde yazar:

> *"Whether a given revision is actually wrong depends on the RAW bytes, not the database …
> These queries report revisions that are AT RISK and must be re-analyzed to be trusted.
> They deliberately do not guess."*

Aynı gerekçe burada da geçerli: hangi revision'ın **gerçekten** bir folded/gap hücresi
taşıdığı object storage'daki baytlarda yaşar, veritabanında değil. Yani md. 3 (aşağıda)
imzalanırsa çıktısı bir **migration değil, bir rapordur** — `CONSUMABLE_*_STATES` süzgeci
ve `_UTC_EQUIVALENT_IANA` muafiyeti dahil, o dosyanın deseni kopyalanabilir.

## Ölçüm 5 — ASIL NOKTA: **hiçbir seçenek ikinci occurrence'ı geri getirmez**

Offset'siz bir kaynak dizesi `fold=1`'i **ifade edemez**. Bu bir uygulama tercihi değil,
biçimin sınırıdır. Dolayısıyla:

- **A** (ilk occurrence'ı onayla) → yılda bir saatlik veri sessizce erken instant'a çöker;
- **B** (blokla) → aynı saat yine adreslenemez, ama **kullanıcıya söylenir** ve revision
  onaya giremez.

Seçenekler *"veriyi kurtarmak"* ekseninde ayrışmıyor; **kullanıcının bilgilendirilip
bilgilendirilmediği** ekseninde ayrışıyor. Veriyi gerçekten kurtarmanın tek yolu kaynağın
offset taşımasıdır ve bu ürünün kontrolünde değildir.

---

## Karar 1 — **FOLD**: iki kez yaşanan saat

| # | Seçenek | Ölçülmüş sonucu | Bedeli |
|---|---|---|---|
| **A1** | **Bugünkü davranışı ONAYLA** — ilk (geçiş öncesi) occurrence kuraldır | kod değişmez; üç characterization testi *"karara bağlanmış davranış"*a terfi eder | yılda bir saat sessizce çöker; doc 12 §5.2'nin *"conversion failure blocks"* cümlesiyle gerilim yazılı kalır |
| **A2** | **BLOKLA** — belirsiz hücre `RESEARCH_DATA_TIMEZONE_UNRESOLVED` / `MARKET_DATA_TIMEZONE_UNRESOLVED` üretir | `_localize`'a `fold` belirsizliği tespiti + iki okuyucuda simetrik değişiklik | **DST gözeten `custom` kaynakların bir kısmı artık onaya giremez**; bugün geçen veri yarın reddedilir |
| **A3** | **UYAR, bloklamA** — çözüm sürer ama bir quality-rule uyarısı yazılır | orta yol; `quality_rules.py` zaten uyarı üretebiliyor | uyarı okunmazsa A1 ile aynı sonuç |

☑ **Seçim:** **A1 — bugünkü davranışı ONAYLA** (ilk/EDT occurrence kuraldır)   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **Gerekçe (imzanın parçasıdır):** fold'un savunulabilir bir cevabı **vardır** — saat gerçekten
> iki kez yaşandı ve ikisinden birini seçmek gerçek bir soruya verilen gerçek bir cevaptır.
> İkinci occurrence **hiçbir seçenekte** kurtarılamaz (offset'siz dize `fold=1`'i ifade edemez;
> Ölçüm 5 — biçimin sınırı, uygulama tercihi değil), o yüzden seçim yalnız *savunulabilir bir
> instant'ı kabul etmek* ile *gerçek bir saati reddetmek* arasındaydı. **Kod değişmedi**; üç
> characterization testi "karara bağlanmış davranış"a terfi etti.

## Karar 2 — **GAP**: hiç yaşanmamış saat

| # | Seçenek | Ölçülmüş sonucu | Bedeli |
|---|---|---|---|
| **B1** | **Bugünkü davranışı ONAYLA** — normalize etmeye devam | kod değişmez | var olmayan bir instant kanonik kabul edilir; §5.2'ye göre bu *tanımı gereği* bir conversion failure sayılabilir |
| **B2** | **BLOKLA** — gap hücresi conversion failure'dır | A2 ile aynı mekanizma, ayrı tespit | aynı geriye dönük sertleşme |

> **Not (asimetri, ölçülmüş):** fold'un savunulabilir bir cevabı **vardır** (iki gerçek
> instant'tan birini seçmek), gap'in **yoktur** (seçilecek instant yok). Bu yüzden
> `A1 + B2` tutarlı bir kombinasyondur ve tek bir *"ikisi de bloklasın"* kararından daha
> ucuzdur. `A2 + B1` ise ölçülen tek **tutarsız** kombinasyondur: daha savunulabilir hâli
> bloklayıp daha savunulamaz hâli geçirir.

☑ **Seçim:** **B2 — BLOKLA** (gap hücresi conversion failure'dır)   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **Gerekçe (imzanın parçasıdır):** gap'in savunulabilir bir cevabı **yoktur** — seçilecek
> instant yok, o yüzden normalize etmek var olmayan bir an'ı **icat eder**. Yukarıdaki §Not'un
> ölçtüğü asimetri budur ve `A1 + B2` onun doğrudan sonucudur.
>
> **Uygulandı (2026-08-26):** kural TEK yerde — `shared/dst.py::is_nonexistent_local_time`
> (PEP 495 round-trip: fold kendine döner, gap dönmez) — ve **iki okuyucu birlikte** çağırır
> (`validation_rules.py::_localize`, `funding.py::parse_utc`), Ölçüm 1'in şart koştuğu gibi.
> Yeni sözcük dağarcığı **gerekmedi** (Ölçüm 3): sevk edilmiş `timezone_unresolved` bayrağının
> **üçüncü sebebi** oldu. **İki negatif kontrol koşuldu**, ikisi de simetrik kırmızı verdi: tek
> bir okuyucuyu geri almak hem gap testini **hem de** iki okuyucunun anlaşma testini kırıyor —
> yani "ikisi birlikte değişmelidir" kuralı **canlı olarak** korunuyor.

## Karar 3 — KAPSAM (yalnız A2 ya da B2 seçilirse anlamlı)

| # | Seçenek | Ölçülmüş sonucu |
|---|---|---|
| **C1** | Yalnız **ingest/approval** — yeni revision'lar | mevcut APPROVED revision'lar dokunulmadan kalır; pinlenmiş manifest'ler bozulmaz |
| **C2** | **+ geriye dönük denetim** — `timezone_audit.py` desenli **READ-ONLY** rapor | K-01 emsali; hiçbir satır mutate edilmez, *"at risk"* listesi üretilir |
| **C3** | **+ geriye dönük geçersiz kılma** | **ÖLÇÜLDÜ, ÖNERİLMİYOR:** onaylı revision'lar tamamlanmış run manifest'lerine pinlidir (doc 15 §15, INF-04/INF-05); onları geçersiz kılmak sevk edilmiş Result'ların girdisini değiştirir |

☑ **Seçim:** **C1 — yalnız ingest/approval** (yeni revision'lar)   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **Gerekçe (imzanın parçasıdır):** onaylı revision'lar tamamlanmış run manifest'lerine
> **pinlidir**; onlara dokunmak sevk edilmiş, **değiştirilemez** Result'ların *girdisini*
> değiştirirdi. Migration yok, backfill yok, hiçbir saklanan satır değişmiyor.
>
> **C2 REDDEDİLMEDİ, ERTELENDİ.** Read-only denetim raporu (`timezone_audit.py` deseni, K-01
> emsali) istendiği anda **ayrı bir slice** olarak eklenebilir ve bu imza onu engellemez —
> hangi revision'ın gerçekten bir gap hücresi taşıdığı object storage'daki **baytlarda** yaşar,
> veritabanında değil (Ölçüm 4), o yüzden çıktısı bir migration değil bir **rapordur**.
>
> **DÜRÜST SINIR:** `C1` geriye dönük hiçbir şey düzeltmez. Bugün APPROVED olan ve bir gap
> hücresi taşıyan bir revision **varsa**, o hücre hâlâ icat edilmiş instant'ıyla pinlidir ve bu
> imza onu bulmaz. Bunu bilmenin tek yolu `C2`'dir.

---

## İmzadan SONRA yapılacaklar (uygulayıcı için)

1. Kararı bu belgeye yaz; `A1+B1+—` seçilirse **kod değişmez**, yalnız üç characterization
   testinin docstring'i *"karara bağlanmış"* olarak güncellenir.
2. `A2` / `B2` seçilirse **iki okuyucu birlikte** değişir (`_localize` ve `parse_utc`),
   yoksa Ölçüm 1'in anlaşma testi kırmızı verir — ve o test **gevşetilmez**.
3. `arbitration.py`'nin `NET_TRACKING_ISSUE` emsali gibi, kaynakta #559'a işaret eden bir
   yorum varsa kararın adına çevrilir.
4. #559 **ancak bu belge imzalandıktan sonra** kapatılır; kapanış yorumu seçilen şıkkı ve
   bu dosyayı adlandırır (#558 / Karar 2 emsali).
5. `closure_w0_containment_lift_preconditions_2026-08-17.md` §2 ön koşul **21** ve
   `final_closure_delta_audit_2026-08-25.md` §8 satır 21 güncellenir.
