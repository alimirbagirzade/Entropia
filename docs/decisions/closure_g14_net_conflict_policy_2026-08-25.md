# `NET` cross-item conflict policy: **tanımla**, **kaldır**, yoksa **yalnız bildirimi düzelt**? (kapı **G14**)

> **BU BELGEDE HİÇBİR KARAR VERİLMEMİŞTİR.** Yazarın rolü **hazırlık**tır. §Karar'ın
> imza bloğu **boştur** ve onu yalnız ürün sahibi / maintainer doldurabilir.
> `closure_g11_deferred_fill_admission_2026-08-18.md` ile aynı disiplin.

- **Tarih:** 2026-08-25
- **Base:** `origin/main` @ `74db6ff5`
- **İzleme:** GH **#544** (`product-decision`, `blocks-adim-19`) — **2026-08-25'te yeniden
  AÇILDI**; 2026-08-18'de #559 ile **bir saniye arayla**, sıfır yorum / sıfır closing PR /
  sıfır kod değişikliğiyle kapatılmıştı (`final_closure_delta_audit_2026-08-25.md` §4 C-5).
- **Kapsam:** `CrossItemConflictPolicy.NET` — anlamı, sevk edilmiş iki davranışı ve
  kullanıcıya ne söylendiği.
- **Bloklar:** `C9` (containment lift) — ön koşul **20**.
- **BLOKLAMAZ:** `C2`, `C3`, `C4`, `C6`, `G11`, `G12`, A-08.
- **Neden şimdi:** #544 yazıldığından beri **dünya değişti** — Ölçüm 2. Kapı, issue kapalıyken
  *"sağlandı"* diye okunuyordu.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — İki yıl önceki tespit hâlâ **kelimesi kelimesine** geçerli

`e2fa521..74db6ff5` aralığında üç yüzeyin **hiçbiri** değişmedi (diff boş):

| yüzey | sevk edilen metin |
|---|---|
| `domain/allocation/rules.py` (`CONFLICT_POLICY_NET_V1` uyarısı) | *"the engine executes NET conservatively as BLOCK_OPPOSITE"* |
| `frontend/src/lib/allocation.ts` | `NET: "Net (V1: executed as Block opposite)"` |
| `domain/allocation/enums.py` (`CrossItemConflictPolicy` docstring) | aynı iddia |

`SHARED_ALLOCATION_STATUS = "future_dev"` olduğu için **hiçbir shared run admit edilmiyor**,
yani bu üç metin gerçekleşemeyen bir davranışı ilan ediyor. #544'ün *"safe to fix now,
independent of the decision"* dediği metin düzeltmesi **yapılmadı**.

## Ölçüm 2 — YENİ: artık **TEK değere karşılık İKİ sevk edilmiş davranış** var

#544 yazıldığında NET'in tek bir davranışı vardı (sıralı motorda downgrade). Bugün iki tane:

| yol | ne yapar | sembol |
|---|---|---|
| **sıralı motor** (bugün üretimde koşan) | NET'i **BLOCK_OPPOSITE'a downgrade eder** ve L4'te açıklar | `engine.py::conflict_downgraded_from_net` |
| **faz döngüsü** (`C4` ile bağlandı, contained) | NET'i **REDDEDER** — `UnsupportedConflictPolicyError` | `execution/arbitration.py::NET_SUPPORT_STATUS = "undefined_in_canon"` |

Faz döngüsünün gerekçesi kendi docstring'inde yazılı ve **doğrudur**:

> *"presenting a block as if it were netting would advertise a semantics canon has never
> defined … Refusing produces no Result at all, which is strictly safer than producing one
> whose policy label does not describe what ran."*

**Sonuç: bildirim artık DAHA yanlış, daha az değil.** Üretim *"conservatively as
BLOCK_OPPOSITE"* diye ilan ediyor; onu koşacak olan kod **reddediyor**. Üstelik beş açık
semantiğin kaynağı olan `NET_TRACKING_ISSUE` sabiti (2026-08-18 → 2026-08-25 arası) **kapalı**
bir issue'yu gösteriyordu.

## Ölçüm 3 — Beş tanımsız semantik **zaten kaynakta sayılı**

`execution/arbitration.py::NET_UNDEFINED_SEMANTICS`, tanımlama seçeneğinin cevaplaması
gereken listeyi birebir taşıyor — bu belge onu **yeniden yazmıyor**, adlandırıyor:

1. **netting price** — iki karşıt item pozisyonu hangi fiyattan offset olur
2. **position custody** — netlenen pozisyonu hangi item'ın defteri tutar, diğerinde ne kalır
3. **fee attribution** — offset bir komisyon mu, iki mi, sıfır mı öder
4. **realized PnL attribution** — netlenen sonuç iki item'a nasıl bölünür
5. **margin / collateral** — netlenmiş çift ne kadar sermaye bağlar (Master Ref §10.2 bunu
   **var olmayan** bir portföy risk modeline devrediyor)

Beşi de ürün kararıdır; biri tahmin edilirse kullanıcının kanona karşı denetleyemeyeceği
sayılar üretilir.

## Ölçüm 4 — KRİTİK: **kaldırmak metin değişikliği DEĞİL, migration**

`conflict_policy` kalıcı bir kolondur:

- tablo **`portfolio_allocation_plan`**, `0035_portfolio_rules` ile eklendi;
- tip `enum_column(CrossItemConflictPolicy, "allocation_conflict_policy")` →
  **VARCHAR + CHECK constraint** (`native_enum=False`, `validate_strings=True`);
- ORM tarafı `infrastructure/postgres/models/allocation.py`, nullable.

Yani enum'dan `NET`'i düşürmek **CHECK'i yeniden yazan bir alembic revision'ı gerektirir**,
ve **`'NET'` taşıyan mevcut satırlar yeni CHECK'i ihlal eder**. Migration onların ne olacağına
karar vermek zorundadır — ve bu seçeneğin asıl bedeli budur, kod satırı sayısı değil:

- `BLOCK_OPPOSITE`'a yeniden yazmak → **kullanıcının kaydettiği yapılandırmayı sessizce
  değiştirmek**; bu deponun *"silent fallback"* yasağının tam da kendisi;
- satırları olduğu gibi bırakıp okumayı gevşetmek → enum kaldırılmış **olmaz**;
- migration'ı `'NET'` satırı varsa **durdurmak** → dürüst, ama operatöre elle iş bırakır.

Ek yüzeyler: `frontend/src/lib/allocation.ts::CONFLICT_POLICIES` + label, `Portfolio.tsx`'in
açıklama metni, ve davranışı pinleyen **beş test dosyası** (`test_allocation_rules.py`,
`test_allocation_persistence.py`, `test_backtest_output.py`,
`test_backtest_cross_item_arbitration.py`, `test_oracle_portfolio_capital.py`).

---

## Karar 1 — NET'in geleceği

| # | Seçenek | Ölçülmüş sonucu | Bedeli |
|---|---|---|---|
| **A** | **TANIMLA** — Ölçüm 3'ün beş sorusunu cevapla | `arbitration.py` refüzü gerçek bir kurala dönüşür; `C9` sonrası NET **çalışır** | beş ürün kararı + netleme aritmetiği + golden fixture'lar; **açık ara en pahalı**, ve Master Ref §10.2 madde 5 için bir risk modeli **istiyor** |
| **B** | **KALDIR** — enum değerini düşür | değer artık kaydedilemez; iki yollu çelişki kökten biter | **migration + mevcut satır kararı** (Ölçüm 4) + frontend + beş test dosyası; **geri alması zor** |
| **C** | **DEĞERİ TUT, yalnız BİLDİRİMİ düzelt** — üç metin bugünkü gerçeği anlatsın | #544'ün kendi *"safe to fix now"* önerisi; kod davranışı değişmez; migration yok | **`G14`'ü KAPATMAZ** — bkz. aşağıdaki uyarı |

> **UYARI — C tek başına kapıyı kapatmaz, ve bu ölçüldü.** Ön koşul 20 NET'in *anlamının*
> kararını ister, bildiriminin doğruluğunu değil. `C` doğru ve ucuz bir düzeltmedir
> (bugün kullanıcıya yalan söylenmesini durdurur), ama `C9` öncesinde **A ya da B yine de
> gereklidir**. `C`'yi *"halloldu"* diye işaretlemek, bu belgenin var olma sebebi olan
> hatanın aynısı olur.
>
> **Kombinasyon serbesttir ve muhtemelen doğrusudur:** `C` **şimdi**, `A`/`B` `C9` öncesi.

☑ **Seçim:** **`C` şimdi + `B` (KALDIR) `C9` öncesi**   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **Gerekçe (imzanın parçasıdır):** `B`, `A`'ya tercih edildi çünkü NET'in kanonik tanımı
> **yoktur** ve onu tanımlamak (`A`) beş ayrı ürün kararı + netleme aritmetiği + golden
> fixture'lar açar; `B` çelişkiyi kökten bitirir. `C` **şimdi** imzalandı çünkü bugün
> kullanıcıya söylenen şey karşı-olgusaldır ve bunu durdurmak migration gerektirmez.
>
> **`C` BU KAPIYI KAPATMAZ — belgenin kendi uyarısı geçerlidir ve burada tekrarlanır.** Ön
> koşul 20 NET'in *anlamının* kararını ister, bildiriminin doğruluğunu değil. `C` inince
> `G14` **AÇIK KALIR**; kapanışı `B`'nin sevkine bağlıdır.
>
> **AÇIK, VE BİLEREK:** **Karar 2** (`'NET'` taşıyan mevcut satırlar — `B1`/`B2`/`B3`) `B`
> uygulanmadan **imzalanmalıdır**; bu imza onu kapsamaz. **Karar 3** (`C`'nin metni) `C`
> yazılırken imzalanacaktır. **#544, `B` sevk edilene kadar KAPATILMAZ.**
>
> **Bu imza 2026-08-26'da verildi; `C` ve `B` HENÜZ UYGULANMADI.** Kod tarafında sıfır satır
> değişti — imza ile sevkin arasındaki bu boşluk #720 emsalinin tersidir (orada sevk vardı,
> imza yoktu) ve kapanana kadar açıkça böyle okunmalıdır.

## Ölçüm 5 — YENİ (ADIM 122): Karar 2'nin sorduğu küme **DONMUŞ DEĞİL, BÜYÜYOR**

Karar 2 *"`'NET'` taşıyan **mevcut** satırlar"* diye soruyor. Bu soru sessizce bir şey
varsayıyor: kümenin **kapalı** olduğunu. **Ölçüldü — değil.**

| Ne | Ölçüm | Kanıt (taban `9bb14570`) |
|---|---|---|
| NET seçimi kaydı **bloklar mı** | **HAYIR** | `rules.py` NET için `Sev.WARNING` üretir — yanındaki `MAX_TOTAL_EXPOSURE_INVALID` ve `NO_ACTIVE_ENTRY` `Sev.BLOCKER`'dır, o **değil** |
| Kapı neyi sayar | **yalnız BLOCKER** | `rules.py::has_blockers` = `any(severity == Sev.BLOCKER)`; üç çağıranı `commands/allocation_plan.py` |
| Plan **geçerli** sayılır mı | **EVET** | `allocation_plan.py` → `valid = not has_blockers(issues)` → NET'li plan **`valid=True`** |
| Kullanıcı NET'i **seçebilir mi** | **EVET** | `frontend/src/lib/allocation.ts::CONFLICT_POLICIES` üç üyeli ve `NET` **canlı**; gövdenin `conflict_policy: "NET"` gittiği `portfolio.test.tsx`'te **pinli** |
| Kolon | **nullable** | `models/allocation.py::PortfolioAllocationPlan.conflict_policy`, `nullable=True` (B2'nin ucuz olmasının sebebi) |

**Sonuç, ve Karar 2'yi doğrudan etkiler:** `'NET'` satırları **bugün, sevk edilmiş build'de
oluşmaya devam ediyor**. Kullanıcı seçer → kayıt **başarılı olur** → satır kalıcılaşır →
koşuda `engine.py::conflict_downgraded_from_net` onu sessizce downgrade eder (ADIM 118'in
bildirimi bunu **anlatır**, **engellemez**).

Bu üç şeyi birden söyler:

1. **Karar 2 boş bir küme umuduna yaslanamaz.** *"Belki sıfırdır, o zaman ucuz"* okuması
   **kurulamaz**: sayı bugün sıfır olsa bile yarın olmayabilir.
2. **`G15` emsali burada TERSİNE işler.** `G15`'te sayı **alınabilirdi** ve alınmadığı için
   imza bekledi. Burada sayı **alınsa bile bayatlar**, çünkü yazma yolu açık — yani sayı bir
   **ön koşul** değil, bir **anlık görüntüdür**.
3. **B1/B2/B3'ün üçü de boş olmayan bir kümeyi varsaymak zorundadır**, ve `B3` (migration
   dursun) **koşan bir sisteme karşı** ayrıca kırılgandır: deploy anında sıfır olan sayı,
   bir sonraki deploy'da sıfır olmayabilir.

### Sayının kendisi ALINMADI — ve ikame edilmedi

Üretim DB'sine erişim yok; repo fixture'ları vekil **değildir** (`G15` §Ölçüm kuralı).
İmzacının koşturacağı sorgu:

```sql
SELECT count(*) FILTER (WHERE conflict_policy = 'NET') AS net_rows,
       count(*)                                        AS total_plans
FROM portfolio_allocation_plan;
```

**Bu sayı bir ön koşul kutusu DEĞİLDİR** (yukarıdaki md. 2) — Karar 2 onsuz da imzalanabilir;
sayı yalnız migration'ın karşılaşacağı işin **büyüklüğünü** söyler, **cinsini** değil.

### Ölçümün doğurduğu DÖRDÜNCÜ seçenek — bir ÖNERİ DEĞİL

Belgenin B1/B2/B3'ü kümeyi **kapalı** varsaydığı için, onu **kapatan** bir seçenek listede
yok. Ölçüm onu doğuruyor ve **karara bağlanmadan** kaydediliyor (`G15`'in dördüncü
seçeneğinin doğuşuyla aynı şekil):

> **B0 — ÖNCE YAZMA YOLUNU DONDUR.** `Sev.WARNING` → `Sev.BLOCKER` **ve**
> `CONFLICT_POLICIES`'ten `NET`'i düşür. Küme o an **donar**; migration sabit bir küme
> üzerinde çalışır ve B1/B2/B3 arasındaki seçim **ölçülebilir** hâle gelir.
> **Bedeli dürüstçe:** bu **kendi başına** bir davranış değişikliğidir — bugün `valid=True`
> alan bir yapılandırma yarın blocker alır, yani `C9`'dan **bağımsız** olarak kullanıcıya
> görünür. Yani B0 Karar 2'yi ucuzlatır ama **bedavaya değil**; ayrıca imzalanmalıdır.

**Bu bölüm 2026-08-27'ye kadar hiçbir kutu doldurmadı.** Was: *"Bu bölüm hiçbir kutu
doldurmaz. §Karar 2'nin imza bloğu boştur ve öyle bırakıldı."* — bu cümle ADIM 122'de
**doğruydu**; 2026-08-27'de ürün sahibi `B0`'ı **ve** `B3`'ü birlikte imzaladı, ve `B0`
kendi imza bloğunu **§Karar 4**'te aldı (bu bölüm hâlâ kutu taşımaz — ölçüm bölümüdür).
`B0`'ın burada **karara bağlanmadan** kaydedilmiş olması bir kusur değildi: ölçümün bir
seçenek doğurması ile o seçeneğin imzalanması ayrı düzlemlerdir.

---

## Karar 2 — YALNIZ `B` seçilirse: `'NET'` taşıyan mevcut satırlar

| # | Seçenek | Ölçülmüş sonucu |
|---|---|---|
| **B1** | `BLOCK_OPPOSITE`'a yeniden yaz | veri kaybı yok, ama **kullanıcı yapılandırması sessizce değişir** (silent-fallback yasağı) |
| **B2** | `NULL`'a çevir | kolon zaten nullable; *"seçim yapılmamış"* demek, yanlış bir seçim atfetmekten dürüsttür |
| **B3** | Satır varsa migration **DURSUN** | en dürüstü; operatöre elle karar bırakır, otomatik deploy'u bloklar |

☑ **Seçim:** **`B3`** — `'NET'` taşıyan satır varsa migration **DURSUN**   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-27

> **Gerekçe (imzanın parçasıdır).** `B1` bu deponun *silent-fallback* yasağının tam
> tanımıdır: kullanıcının kaydettiği yapılandırmayı ona sormadan başka bir değere çevirir.
> `B2` (`NULL`) daha dürüsttür ama yine de **bir kaybı sessizce** gerçekleştirir — plan
> *"seçim yapılmamış"* hâline döner ve operatör bunu ancak sonradan fark eder. `B3` işi
> **karar veremeyecek olan tarafa** (migration) değil, **verebilecek olana** (operatör)
> bırakır ve otomatik deploy'u bloklayarak kaybın sessiz olmasını yapısal olarak imkânsız
> kılar.
>
> **`B3`'ün ölçülmüş kırılganlığı KABUL EDİLDİ, ve `B0` tam da onu kapatır.** §Ölçüm 5
> md. 3: *"deploy anında sıfır olan sayı, bir sonraki deploy'da sıfır olmayabilir"* — `B3`
> koşan bir sisteme karşı tek başına kırılgandır. `B0` (§Karar 4) kümeyi dondurduğu için
> `B3`'ün beklediği *"sabit küme"* varsayımı **kurulabilir hâle gelir**. İkisi bu yüzden
> birlikte imzalandı ve **ayrı sürümlerde sevk edilir** (aşağıdaki sıra kısıdı).
>
> **SIRA KISIDI — İMZANIN PARÇASI, süsleme değil.** `B0` **önce**, `B`'nin migration'ı
> **sonraki** bir sürümde. İkisi aynı sürümde çıkarsa `B0`'ın drenaj penceresi **hiç
> oluşmaz**: migration, deploy anına kadar hâlâ büyüyen bir kümeye çarpar, `B3` **durur** ve
> deploy kırmızı olur. Yani ikisini tek slice'a koymak `B0`'ı işlevsiz bırakır.
>
> **`B3` `G14`'ü KAPATMAZ.** Bu imza yalnız `B` sevk edildiğinde mevcut satırların ne
> olacağını belirler; `B`'nin kendisi (enum'dan `NET`'in düşmesi + CHECK yeniden yazımı)
> Karar 1 uyarınca **`C9` öncesi** ayrı bir slice'tır ve **#544 o zamana kadar KAPATILMAZ**.

## Karar 3 — `C` seçilirse: bildirim ne DESİN

Metin, sevk edilmiş **iki** davranışı da doğru anlatmalıdır (Ölçüm 2), yoksa aynı kusurun
yeni sürümü yazılmış olur. Ölçülmüş doğru içerik:

- containment yürürlükteyken **hiçbir shared run admit edilmiyor** — downgrade *gerçekleşmiyor*;
- sıralı motorda değer **BLOCK_OPPOSITE olarak** koşar;
- faz döngüsü onu **reddeder**;
- NET'in kanonik tanımı **yok** ve beş semantiği `NET_UNDEFINED_SEMANTICS`'te sayılı.

☑ **Onaylanan metin:** `rules.py::_net_policy_warning` (gerekçe aşağıda)   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **METİN SABİT DEĞİL, TÜRETİLMİŞTİR — ve bu imzanın parçasıdır.** Dört maddenin **birincisi**
> yalnız containment yürürlükteyken doğrudur; onu sabit yazmak `C9` lift'inin **ertesi günü**
> yeni bir karşı-olgusal cümle bırakırdı — yani bu belgenin var olma sebebi olan hatanın
> tekrarı olurdu. Metin bu yüzden ikiye ayrıldı:
>
> - **gövde** (`_NET_POLICY_BODY`) — 2., 3. ve 4. maddeler; bayrağın **her iki** değerinde doğru;
> - **ön ek** (`_NET_POLICY_NOT_EXECUTABLE_PREFIX`) — 1. madde; yalnız
>   `shared_allocation_is_executable()` **False** iken eklenir.
>
> **AMPİRİK OLARAK ÖLÇÜLDÜ, varsayılmadı:** `validate_allocation` `config.enabled` değilse
> `([], None)` döner → NET uyarısı **yalnız enabled** planda fire eder; ve enabled bir plan bu
> build'de **her zaman** `SHARED_MODE_NOT_IN_BUILD` blocker'ını da taşır. İkisi de
> `test_the_net_notice_is_worded_against_the_world_that_applies` içinde **assert edilir**
> (elle iddia edilmez), ve bayrak `validate_allocation` içinde **tek kez** okunur — kapı ile
> bildirim tek bir doğrulama turunda iki ayrı dünyayı anlatamaz.
>
> **DÖRDÜNCÜ BİR YÜZEY BULUNDU; BU BELGE ONU ADLANDIRMIYORDU.** `enums.py`'de
> `AllocationIssueCode.CONFLICT_POLICY_NET_V1` **üyesinin yorumu** da aynı iddiayı taşıyordu
> (*"the engine executes it conservatively as BLOCK_OPPOSITE"*). Ölçülüp düzeltildi — md. 2'nin
> *"biri unutulursa çelişki devam eder"* uyarısı, tam da o maddenin saymadığı bir yüzeyden
> gerçekleşecekti. Wire token'ın `_V1` yazımı **DEĞİŞMEDİ**: sevk edilmiş bir makine kodudur ve
> bir yazım uğruna yeniden adlandırmak tüm çağıranları kırardı (O-31 emsali).
>
> **BEŞ SEMANTİK ADIYLA GÖSTERİLDİ, İMPORT EDİLMEDİ — bu bir KISIT, tercih değil.**
> `NET_UNDEFINED_SEMANTICS` `execution/arbitration.py`'de yaşar; o modülün importer allowlist'i
> **imzalıdır** (`closure_participant_importer_allowlist_2026-08-18.md`) ve kapı
> `execution.arbitration import` dizesini **metin olarak** tarar. Ölçüldü (NC-4): import eklemek
> hem yeni testi hem `test_the_phase_loop_exists_but_no_production_path_reaches_it`'i kırmızıya
> çeviriyor → beş dizeyi yeniden yazmamak için **imzalı bir listeyi imzasız bir modülle**
> genişletmek gerekirdi; `C4`/E5'in reddettiği takasın aynısı.
>
> **BOŞLUK ÖLÇÜLDÜ (NC-3):** sevk edilen eski metin geri konduğunda iki yeni eksen de kırmızı
> verdi ama `test_allocation_rules.py`'nin **18 testinin 18'i de yeşil kaldı** — mevcut suite
> mesajın **kodunu ve severity'sini** pinliyordu, **metnini hiç** okumuyordu. İki yıl boyunca
> karşı-olgusal kalabilmesinin sebebi budur.
>
> **`C` BU KAPIYI KAPATMAZ.** Karar 1'in uyarısı burada da geçerlidir: `G14` **AÇIK KALIR**,
> **#544 KAPATILMAZ**, ön koşul 20 **kırmızı** — kapanış `B`'nin sevkine bağlıdır ve
> **Karar 2 hâlâ imzasızdır**.

---

## Karar 4 — `B0`: yazma yolunu dondur (§Ölçüm 5'in doğurduğu dördüncü seçenek)

§Ölçüm 5 `B0`'ı **karara bağlamadan** kaydetmişti ve *"ayrıca imzalanmalıdır"* demişti.

☑ **Seçim:** **`B0`** — yazma yolu **şimdi** dondurulur   ☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-27

> **Bedeli, §Ölçüm 5'in yazdığı gibi, kabul edildi:** bu **kendi başına** bir davranış
> değişikliğidir — bugün `valid=True` alan bir yapılandırma yarın blocker alır ve bu
> `C9`'dan **bağımsız** olarak kullanıcıya görünür.

### ÖLÇÜM 6 — İMZALANAN MEKANİZMA, İMZALANAN SONUCU ÜRETMİYOR (uygulama sırasında bulundu)

§Ölçüm 5 `B0`'ı iki mekanizmayla tanımlıyor — `Sev.WARNING` → `Sev.BLOCKER` **ve**
`CONFLICT_POLICIES`'ten `NET`'i düşürmek — ve *"küme o an **donar**"* diye **sonucu** iddia
ediyor. **Sonuç doğru, mekanizma eksik.** Uygulama sırasında `ast` ile ölçüldü (grep değil),
taban `98498d99`:

| Fonksiyon | `plan.conflict_policy` **yazar** | `has_blockers` **çağırır** |
|---|---|---|
| `upsert_allocation_draft` (`:74–223`) | **EVET** | **HAYIR** |
| `validate_allocation_draft` (`:231–311`) | hayır | evet |
| `create_allocation_revision` (`:319–421`) | hayır | evet |
| `_readiness_state` (`:734–741`) | hayır | evet |

**İki küme AYRIK.** `'NET'` satırını `portfolio_allocation_plan`'a yazan tek yol
`upsert_allocation_draft`'tır ve o yol `has_blockers`'a **hiç bakmaz** — bakmaması da
doğrudur: taslak, tanımı gereği geçersiz olabilir. Dolayısıyla **severity flip'i tek başına
hiçbir satırı engellemez**; `SHARED_ALLOCATION_STATUS` bugünkü değerinde bu daha da
görünmezdir, çünkü enabled bir plan zaten `SHARED_MODE_NOT_IN_BUILD` blocker'ını taşır ve
`has_blockers` **zaten** `True` döner.

**Bu yüzden `B0` ÜÇ yüzeyle uygulandı, ikiyle değil.** İmzalanan iki mekanizma korundu ve
üçüncüsü **sonucu** üretmek için eklendi:

1. `rules.py` — `Sev.WARNING` → `Sev.BLOCKER` *(imzalı; drenaj **sinyali**: saklanan NET
   planlar `READY_WITH_WARNINGS` → **`NOT_READY`** okunur)*;
2. `lib/allocation.ts::CONFLICT_POLICIES` — `NET` düşer *(imzalı; UI'da **seçilemez**)*;
3. **YENİ** — `upsert_allocation_draft` gelen `NET` **token**'ını yazma sınırında reddeder
   *(`CROSS_ITEM_CONFLICT_POLICY_NOT_SELECTABLE`, O-02 zarfı)*. **Asıl freeze budur**; onsuz
   md. 2 yalnız kozmetiktir ve herhangi bir API istemcisi `NET` yazmaya devam eder.

**REDDİN YERİ ÖLÇÜLEREK SEÇİLDİ — iki yanlış yerleşim elendi:**

- **`config.py::_norm_conflict` (paylaşılan Pydantic modeli) OLMAZ.**
  `_plan_to_config` (`:566`) **saklanan satırı** aynı modelle `model_validate` eder →
  orada reddetmek **mevcut NET planların OKUNMASINI** 500'e çevirirdi. `B0` yazmayı
  dondurur, **okumayı değil**.
- **`upsert_allocation_draft`'te tüm blocker'ları reddetmek OLMAZ.** Enabled her plan
  containment blocker'ı taşır → her taslak kaydı reddedilir, yani paylaşımlı tahsis
  **tamamen kaydedilemez** hâle gelirdi. Red bu yüzden **yalnız `NET` token'ına** dairdir.

**KULLANICIYA GÖRÜNEN SONUÇ, AÇIKÇA:** saklanan `NET` bir planı açıp **başka** bir alanı
değiştirerek kaydetmek de reddedilir — çünkü gövde `conflict_policy: "NET"`'i geri gönderir.
Bu bir yan etki **değil**, `B3`'ün ihtiyaç duyduğu **drenaj baskısının kendisidir**: baskı
olmazsa küme hiç boşalmaz ve `B3` sonsuza dek durur. Kullanıcı sessizce başka bir değere
**çevrilmez** (bu `B1` olurdu, reddedildi) — kendisi seçmek zorundadır.

---

## İmzadan SONRA yapılacaklar (uygulayıcı için)

1. Kararı bu belgeye yaz.
2. `C`: üç yüzey (`rules.py` uyarısı, `enums.py` docstring'i, `lib/allocation.ts` label'ı)
   **birlikte** güncellenir — biri unutulursa çelişki devam eder. `Portfolio.tsx`'in
   açıklama cümlesi de aynı partide.
3. `B`: alembic revision + Karar 2'nin şıkkı + frontend + beş test dosyası; migration
   **up/down/up** ile doğrulanır (CLAUDE.md §Local verify).
4. `A`: beş semantik ADR-0002'ye amendment olarak girer; `NET_SUPPORT_STATUS` ve
   `NET_UNDEFINED_SEMANTICS` kararın adına çevrilir; golden digest'ler **bump** ister.
5. Her hâlde `arbitration.py::NET_TRACKING_ISSUE` bu dosyayı ya da kararın adını
   göstermelidir — **kapalı bir issue'yu göstermemelidir** (2026-08-18'de öyle olmuştu).
6. #544 **ancak bu belge imzalandıktan sonra** kapatılır; kapanış yorumu seçilen şıkkı ve bu
   dosyayı adlandırır (#558 / Karar 2 emsali).
7. `closure_w0_containment_lift_preconditions_2026-08-17.md` §2 ön koşul **20** ve
   `final_closure_delta_audit_2026-08-25.md` §8 satır 20 güncellenir.
