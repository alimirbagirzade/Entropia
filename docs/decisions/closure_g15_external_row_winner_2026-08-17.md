# Ready Check leg 3 — hangi external-import satırı kazanır? (G15)

> **Bu belge KARAR BEKLİYOR.** G15, `final_closure_ordered_plan_2026-08-13.md` §2'nin
> *"imzalanacak bir bloğu olmayan iki kapı"*sından biridir (diğeri G4). Bu belge o eksik
> bloğu **yaratır**; **hiçbir seçeneği seçmez**. `closure_product_decisions_2026-08-13.md`
> §Karar 1/2/3 ile aynı yapıdadır ve aynı disiplini uygular: seçenek elenmez, "önerilen"
> yazılmaz.

- **Tarih:** 2026-08-17
- **Base:** `origin/main` @ `6ca478c41a8da36efb126a11e5c34be40cade708`
  (`docs(closure-e5): record why the worker shared-path branch is not buildable yet (#738)`)
- **Branch:** `docs/closure-g15-external-row-winner-brief`
- **Kapsam:** Ready Check leg 3 — `_resolve_external`'ın okuduğu satırın **kimliği**
- **Yazarın rolü:** hazırlık. **Bu belgede hiçbir karar verilmemiştir.**
- **İlgili kapı:** G15 (ordered plan §2). **Bloklar:** bu plandaki hiçbir slice'ı — leg 3'ün
  **bilerek** slice'ı yoktur; bloklandığı şey leg 3'ün **kapanışı** ve `P3` bütçe satırının
  eğiminin düşmesidir.

---

## Taban notu (dürüstlük)

`closure_product_decisions_2026-08-13.md`'nin tabanı `0d8bf8f`, ORTAK SÖZLEŞME'nin beklediği
taban `31ed27d` idi. Bu belge **`6ca478c`** üzerinde yazıldı — ikisinden de ileride. Aradaki
fark bu belge için maddidir, çünkü G15'in ölçümleri kod yüzeyine bağlıdır. Bu yüzden
**aşağıdaki her ölçüm `6ca478c` üzerinde yeniden yapılmıştır**; hiçbiri ADIM 62'nin
(`#712`) kaydından kopyalanmamıştır. ADIM 62'nin tespiti **doğrulandı ve genişletildi** —
nerede genişlediği §"Ölçüm 1" ve §"Ölçüm 4"te açıkça yazılıdır.

Satır numarası **bilerek yazılmamıştır** (CLAUDE.md §Conventions: sembol adı yaz). Bu belgedeki
her kod göndermesi bir **sembol** adıdır.

## Bu belgede kanıt olarak kullanılmayan şeyler

- **Üretim veritabanı.** Bu oturumun üretim verisine erişimi **yoktur**. §"Duplikasyon sayımı"
  bunu bir tahminle doldurmaz; sayılamadığını ve **neden** sayılamadığını yazar.
- **Test adları.** Aşağıdaki hiçbir hüküm bir test adına dayanmaz; dayandığı yerlerde testin
  **ne assert ettiği** okunmuştur.
- **`work_object_revision_id`'nin "Set once at Save time" yorumu.** İki modelde de yazılıdır
  ve bir **niyet** beyanıdır; §"Ölçüm 4" onun bugün **tutmadığını** ölçer. Yorum kanıt
  değildir.

---

## Karar 4 — Ready Check leg 3'ün okuduğu satır (G15)

### Canonical ne diyor

Kanon *"birden çok satır eşleşirse hangisi kazanır"* sorusunu **hiç sormaz** — çünkü ilişkinin
**bire-bir** olduğunu varsayar. Söylediği dört şey var:

| # | Kaynak | Literal | Ne söyler |
|---|---|---|---|
| K1 | doc 05, Trade Log Revision tanımı | *"**Bir** source asset, mapping, canonical records ve validation evidence içeren immutable sürüm."* | Bir revision **bir** canonical record seti içerir. Çokluk kanonda **yok**. |
| K2 | doc 05, Derived Rule | *"Backtest manifest yalnız pinned Trade Log revisionını taşır; **'latest' revision sessizce kullanılamaz**."* | Kanon **"en yenisini sessizce al"** desenini **adıyla yasaklar**. Seçenek B'nin doğrudan hedefidir (§Seçenek B'nin riski). |
| K3 | doc 05, Pinned Revision | *"Yeni revision oluştuğunda **otomatik geçmez**; açık pin gerekir."* | Pin **kullanıcının** kararıdır, yazma yolunun yan etkisi değil. §"Ölçüm 4" bunun ihlal edildiğini ölçer. |
| K4 | doc 14 §5.1 / §9.2 | *"Normalized immutable import revision, mapping/validation/availability required."* · *"File-input presence alone is never sufficient."* | Ready Check **bir** normalized import revision'ı **çözmek** zorundadır. Hangisini çözeceğini söylemez. |

**Kanonun boşluğu tam olarak budur:** K1 bire-bir varsayar, ama bu varsayımı **hiçbir yere
zorlatmaz**; K4 bir satırın çözülmesini şart koşar, ama **hangisi** olduğunu söylemez. Karar
bu boşluğu kapatır.

### Kod şu an ne yapıyor (sembol)

**Okuma yolu (leg 3):**

```
application/commands/readiness_check.py::run_readiness_check
  -> ::_build_item_inputs            (enabled item'lar üzerinde DÖNGÜ)
     -> ::_resolve_external          (her external item için BİR kez -> N+1)
        -> infrastructure/postgres/repositories/readiness.py::resolve_trade_log_batch
        -> infrastructure/postgres/repositories/readiness.py::resolve_signal_revision
```

İki okuyucunun **ikisi de** şu şekildedir:

```
select(<Model>).where(<Model>.work_object_revision_id == revision_id)
... .scalars().first()
```

**`ORDER BY` YOK. `LIMIT` YOK. Tie-breaker YOK.**

**Şema (canlı `0043_i08_registry_strategy_fks` şemasına karşı ölçüldü, `pg_index`):**

| Tablo | Kolon | Index | `indisunique` |
|---|---|---|---|
| `canonical_trade_record_batch` | `work_object_revision_id` | `ix_canonical_trade_record_batch_work_object_revision_id` | **`f`** |
| `normalized_signal_event_revision` | `work_object_revision_id` | `ix_normalized_signal_event_revision_work_object_revision_id` | **`f`** |

`pg_constraint` üzerinde bu iki tabloda `contype IN ('u','p')` olan **tek** kayıt kendi
PK'larıdır; **hiçbir UNIQUE constraint yoktur**. 43 alembic revision'ının yalnız ikisi bu
tablolara dokunur (`0010_trading_signal`, `0011_trade_log`) ve ikisi de indexi **`unique=True`
olmadan** kurar. Kolon iki modelde de `nullable=True, index=True`.

**Yazma yolu — tam envanter.** `backend/src` genelinde `work_object_revision_id`'ye yazan
**tam olarak iki sembol** vardır:

| Yazan sembol | Çağrıldığı yer | Yazdığı değer |
|---|---|---|
| `repositories/trade_log.py::link_batch_to_revision` | `commands/trade_log.py::create_trade_log_and_attach` · `::create_trade_log_revision` | `revision.revision_id` |
| `repositories/trading_signal.py::link_normalized_to_revision` | `commands/trading_signal.py::create_trading_signal_and_attach` · `::create_trading_signal_revision` | `revision.revision_id` |

Dört çağrı yerinin **dördünde de** `revision`, aynı `_op()` içinde **yeni üretilmiş** bir
revision'dır (`mb_repo.create_work_object` veya `mb_repo.append_work_object_revision`). Satır
yaratılırken kolon `work_object_revision_id=None`'dır ve **sonradan** atanır.

### Çelişki tam olarak nerede

Üç ayrı çelişki var; ordered plan yalnız birincisini adlandırıyor.

**Ç1 — belirsizlik batch'lemenin GETİRDİĞİ bir risk değil; bugün ÜRETİMDE var.**
Ordered plan §3 leg 3'ü *"bugünkü per-item kazanan **tanımsız**, bir batch **muhtemelen
farklı** bir satır seçebilir"* diye çerçeveliyor. Bu çerçeve **eksiktir** ve bu belgenin
düzelttiği şeydir: `ORDER BY`'sız bir `.first()` yalnız *"tanımsız"* değil, **çağrıdan çağrıya
değişebilir**. Batch'leme belirsizliği **yaratmaz**; onu **görünür kılar**. Ölçüldü (§Ölçüm 1).

**Ç2 — modelin kendi yorumu bugün tutmuyor.** İki modelde de kolonun üstünde
*"Set once at Save time"* yazar. **"Once" ölçülmedi ve tutmuyor:** aynı batch, aynı komut
yoluyla **ikinci bir revision'a yeniden pinlenebilir** ve pin **taşınır** (§Ölçüm 4). Yorum bir
niyet beyanıdır; **hiçbir şey onu zorlamıyor.**

**Ç3 — K2 ile Seçenek B'nin doğal biçimi karşı karşıya.** Belirlenimli bir kazanan tanımlamanın
en doğal ifadesi `ORDER BY created_at DESC` — yani *"en yenisi kazanır"*. Kanon (K2) tam olarak
*"'latest' revision **sessizce** kullanılamaz"* diyor. İki cümle **birbirini kesmiyor** (K2
`work_object_revision`'dan, B ise ona bağlı `canonical_record_batch`'ten söz eder) ama **aynı
refleksi** hedefliyorlar. B imzalanacaksa bu ayrım imza metnine **açıkça** yazılmalıdır; aksi
halde bir sonraki okuyucu B'yi K2'nin ihlali sanır.

---

### ÖLÇÜM 1 — "Belirsizlik bugün üretimde var mı?" → **EVET, ölçüldü**

**Yöntem.** `6ca478c`'de yerel Postgres 16 üzerinde alembic `head`'e (`0043_...`) kadar gerçek
şema kuruldu. Aynı `work_object_revision_id`'yi paylaşan **iki** `canonical_trade_record_batch`
satırı yazıldı; sonra **sevk edilmiş** `readiness_repo::resolve_trade_log_batch` sembolü, **aynı
girdiyle**, aralarında **hiçbir yazma olmadan** üç kez çağrıldı. Aradaki tek değişiklik satırların
**fiziksel sırası** (bir `UPDATE` tuple'ı heap'in sonuna taşır) ve **planner seçimi**
(`enable_seqscan` / `enable_indexscan`).

**Sonuç:**

| Çağrı | Dönen satır | `succeeded` | `accepted_count` |
|---|---|---|---|
| 1 (varsayılan plan) | `..._a` | `True` | 2 |
| 2 (seq scan) | `..._b` | **`False`** | **0** |
| 3 (index scan) | `..._a` | `True` | 2 |

**Aynı girdi, aynı veri, iki farklı kazanan.** Ve iki kazanan **zıt** Ready Check girdileri
üretiyor: biri başarılı bir import (2 kabul edilmiş kayıt), diğeri başarısız bir import (0).

> **Hüküm (a):** leg 3'ün per-item okuması **bugün belirlenimsizdir**. Bu bir batch'leme riski
> değil, **sevk edilmiş bir davranıştır**. Ordered plan'ın *"batch farklı seçebilir"* çerçevesi
> bu ölçümle **daha ciddi** bir hâle gelir: per-item okuma da zaten **aynı sorunu taşır**.
> **Koşul:** bu yalnız duplikasyon **varsa** gerçekleşir (bkz. Ölçüm 2/3). Bir veya sıfır satırda
> `.first()` belirlenimlidir.

### ÖLÇÜM 2 — "Duplikasyon ULAŞILABİLİR mi?" → **Sevk edilmiş yazma yolunda ÜRETİCİSİ YOK; depo ise REDDETMİYOR**

Bu, brifingin ampirik çekirdeğidir ve cevabı **iki parçalıdır**. Karıştırılmamalıdır.

**(2a) Depo kabul ediyor mu? → EVET, ölçüldü.** Aynı revision id'yi taşıyan ikinci bir satırın
`INSERT`'ü **kabul edildi**; ne şema, ne model, ne de `link_batch_to_revision` reddetti.
Duplikasyon **fiziksel olarak mümkündür** ve bugün onu engelleyen **hiçbir şey yoktur**.

**(2b) Sevk edilmiş bir yol onu ÜRETİYOR mu? → Ölçülen dört çağrı yerinde HAYIR.**
Gerekçe ölçülmüştür, tahmin değildir: yazan **iki** sembolün **dört** çağrı yerinin de pin
hedefi, aynı transaction içinde **yeni üretilmiş** bir `revision.revision_id`'dir. Aynı revision
id'nin ikinci bir satıra yazılabilmesi için **var olan** bir revision id'nin pin hedefi olması
gerekir; ölçülen dört yolun hiçbiri bunu yapmaz. Değerlendirilen ve **elenen** alt yollar:

- **Yeniden import / yeniden parse** → yeni bir batch satırı üretir, ama o batch ancak **yeni bir
  Save** ile pinlenir; Save **yeni** bir revision üretir. Eski revision'a ikinci satır **eklenmez**.
- **`Idempotency-Key` replay** → `run_idempotent` `_op()`'u **yeniden koşturmaz**; saklanan zarfı
  döndürür. İkinci bir yazma yoktur.
- **Eşzamanlı iki Save New Revision** → ikisi de ayrı revision id üretir; ayrıca
  `session.refresh(root, with_for_update=True)` + `expected_head_revision_id` bunları sıraya sokar.
- **`Use This Revision` (pin_revision)** → Mainboard item'ının pinini değiştirir;
  `work_object_revision_id` kolonuna **dokunmaz**.
- **Migration backfill** → 43 revision içinde bu kolona **hiç** yazan yok.

> **Hüküm (b):** duplikasyonun bugün **bilinen bir üreticisi yoktur**, ama **zorlanmış bir
> değişmez de yoktur.** Bire-bir ilişki bugün bir **kaza** olarak doğrudur — yazma yolunun
> şeklinden **türeyen** bir sonuçtur, **beyan edilmiş** bir kısıt değil. Bunu değiştirmek için
> yeni bir yazıcı, bir veri düzeltme script'i, bir restore/import aracı ya da bir migration
> **yeterlidir** ve hiçbiri bir kapıya çarpmaz.
>
> **DÜRÜST SINIR:** (2b) **ölçülen dört çağrı yeri** hakkındadır. "Hiçbir zaman olamaz" demek
> değildir; "bugünkü `backend/src`'te üreteni yok" demektir. Bir kanıt değil, bir **envanterdir**.

### ÖLÇÜM 3 — DUPLİKASYON SAYIMI (üretim) → **SAYILAMADI**

**Üretimde bugün kaç satır aynı `work_object_revision_id`'yi paylaşıyor? — Bu oturum bunu
sayamadı.**

**Neden sayılamadı (tahmin edilmedi, gerekçesi yazıldı):**

1. Bu oturum **efemer bir container**'da koşuyor ve **üretim veritabanına erişimi yok** —
   ne bağlantı dizesi, ne ağ yolu, ne kimlik bilgisi mevcut.
2. Ölçümlerin koştuğu Postgres, bu oturumda `alembic upgrade head` ile **sıfırdan kurulmuş
   boş** bir şemadır. İçindeki tek veri **bu belgenin kendi probe satırlarıdır**. Oradan
   okunacak bir üretim sayısı **yoktur**.
3. Repoda bu sayıyı taşıyan **üretilmiş bir artefakt yok**: `docs/generated/repository_facts.md`
   şema/route/test **sayılarını** üretir, **satır** sayılarını değil.

**Sayının imzadan ÖNCE alınması gerekir.** Sorgu aşağıdadır ve **artık bir taslak değil,
doğrulanmış bir betiktir** (2026-08-18'de eklendi — §"Betiğin doğrulanması"). Salt-okuma:
yazma yok, DDL yok, düz bir `SELECT`'ten fazla kilit yok.

```sql
-- =====================================================================
-- G15 blast radius (ÖLÇÜM 3) — üretimdeki duplikasyon sayımı
-- SALT-OKUMA. Doğrulandı: alembic head 0043_i08_registry_strategy_fks.
-- Çalıştırma:  psql "$PROD_READONLY_URL" -f g15_blast_radius.sql
--
-- §İMZA SATIRI'nın BİRİNCİ kutusunu doldurur:
--   canonical_trade_record_batch: ___   normalized_signal_event_revision: ___
-- Seçenek A ve C bu sayı 0 çıkmadan imzalanamaz; B ve D bu sayıdan bağımsızdır.
-- =====================================================================

\echo '--- 1. SAYI (imza kutusunun istediği budur) ---'
SELECT 'canonical_trade_record_batch' AS table_name,
       count(*) AS revision_ids_with_duplicates,
       coalesce(sum(n), 0) AS total_rows_involved
FROM (
  SELECT work_object_revision_id, count(*) AS n
  FROM canonical_trade_record_batch
  WHERE work_object_revision_id IS NOT NULL
  GROUP BY work_object_revision_id HAVING count(*) > 1
) d
UNION ALL
SELECT 'normalized_signal_event_revision',
       count(*), coalesce(sum(n), 0)
FROM (
  SELECT work_object_revision_id, count(*) AS n
  FROM normalized_signal_event_revision
  WHERE work_object_revision_id IS NOT NULL
  GROUP BY work_object_revision_id HAVING count(*) > 1
) d;

\echo '--- 2. İHLAL EDEN SATIRLAR (yukarıdaki sayı 0 ise boş) ---'
SELECT 'canonical_trade_record_batch' AS table_name,
       work_object_revision_id, count(*) AS n
FROM canonical_trade_record_batch
WHERE work_object_revision_id IS NOT NULL
GROUP BY work_object_revision_id HAVING count(*) > 1
UNION ALL
SELECT 'normalized_signal_event_revision',
       work_object_revision_id, count(*)
FROM normalized_signal_event_revision
WHERE work_object_revision_id IS NOT NULL
GROUP BY work_object_revision_id HAVING count(*) > 1
ORDER BY 1, 3 DESC;

\echo '--- 3. BAĞLAM: kısıt hâlâ YOK mu? (Seçenek A ön koşulu) ---'
SELECT conrelid::regclass AS table_name, conname, contype
FROM pg_constraint
WHERE conrelid IN ('canonical_trade_record_batch'::regclass,
                   'normalized_signal_event_revision'::regclass)
  AND contype IN ('u','p')
ORDER BY 1;
```

**Üçüncü blok neden var:** Seçenek A'nın ön koşulu yalnız sayının 0 olması değil, kısıtın
**hâlâ yok** olmasıdır. Bu belge o yokluğu 2026-08-17'de ölçtü; sorgu koşulduğu gün onu
**yeniden** ölçer, çünkü aradan geçen sürede bir migration inmiş olabilir.

#### Betiğin doğrulanması (2026-08-18)

**Üretim sayısı HÂLÂ ALINMADI** — yukarıdaki üç gerekçe **aynen geçerlidir**. Doğrulanan şey
sayı değil, **betiğin kendisidir**: bir gün üretimde koşturulduğunda çıkacak sonucun bir sorgu
hatasından değil, veriden geleceği garanti edilmiştir.

**Yöntem.** Yerelde Postgres 16 kuruldu ve `alembic upgrade head` ile **gerçek şema**
(`0043_i08_registry_strategy_fks`) oluşturuldu. Betik bu şemaya karşı **iki yönde** koşturuldu:

| Kontrol | Ekilen veri | Beklenen | Ölçülen |
|---|---|---|---|
| **Pozitif** | aynı `work_object_revision_id`'yi paylaşan **2** satır + `1` tekil satır + `1` NULL satır | yalnız paylaşılan id, `n=2` | **`worev_SHARED, n=2`** — tekil satır ve NULL satır **doğru şekilde** raporlanmadı |
| **Negatif** | duplikasyon silindi | **0** | **0** |

> **Bunun önemi:** negatif kontrol olmadan üretimden dönecek bir **`0`** iki anlama gelebilirdi
> — *"duplikasyon yok"* ya da *"sorgu bozuk"*. İki kontrol birlikte koşturulduğu için üretimden
> dönecek `0` **gerçek bir 0**'dır. §İMZA SATIRI'nın birinci kutusu bir *"sayıldı ve 0"*
> işaretini ancak bu ayrım yapılabiliyorsa taşıyabilir.

**Doğrulama sırasında §Ölçüm 2a bağımsız olarak YENİDEN ÖLÇÜLDÜ ve DOĞRULANDI:** pozitif
kontrolün ekimi, aynı `work_object_revision_id`'yi taşıyan ikinci satırı **kabul etti** — ne
şema, ne kısıt, ne de bir trigger reddetti. Duplikasyon bu şemada bugün de **fiziksel olarak
mümkündür**.

**§Ölçüm 2b'nin üç şema iddiası da aynı koşuda yeniden ölçüldü** (`0043` üzerinde,
`information_schema` + `pg_index` + `pg_constraint`): kolon iki tabloda da var ve
`nullable`; üzerindeki index iki tabloda da **`indisunique = f`**; iki tabloda `contype IN
('u','p')` olan **tek** kayıt kendi PK'larıdır. **Üçü de değişmemiştir.**

**Bu doğrulama repoya bir dosya EKLEMEDİ** — betik bu belgenin içinde yaşar, `scripts/`
altında değil; kurulan Postgres **atılabilir** bir örnekti ve doğrulama bitince **silindi**.

**Bu sayı hangi seçeneği ucuzlatır/pahalılaştırır:**

- **Sonuç 0 satır ise:** Seçenek A'nın backfill maliyeti **sıfırdır** (yalnız migration kalır) ve
  Seçenek C'nin dayandığı varsayım **bugün için doğrulanmış** olur — ama yine de **zorlanmamış**
  kalır.
- **Sonuç > 0 satır ise:** (2b)'nin envanteri **eksiktir** — ölçülmemiş bir üretici vardır ve
  **önce o bulunmalıdır.** Bu durumda Seçenek C imzalanamaz (dayandığı varsayım ölçümle yanlışlanmış
  olur) ve Seçenek A bir **temizlik projesi** doğurur.

> **Bu yüzden §İMZA SATIRI'nın ilk kutusu bir seçenek değil, bu SAYIdır.** Sayı alınmadan A ve C
> imzalanamaz; B ve D sayıdan **bağımsız** imzalanabilir.

### ÖLÇÜM 4 — ölçülen ÜÇÜNCÜ eksen: pin **sabit değil** (bu G15'in sorusu DEĞİL)

Duplikasyon aranırken **ters yönde** ve **ulaşılabilir** bir kusur ölçüldü. Kaydedilir, **üzerine
gidilmez** — G15'in sorusu *"hangi satır kazanır"*dır; bu, *"satır neden hiç yok"* sorusudur.

**Ölçülen davranış.** `link_batch_to_revision` bir **atamadır**, koşulsuzdur. Aynı batch ikinci
kez pinlendiğinde pin **taşınır**:

| Adım | `worev_rev1` çözümü | `worev_rev2` çözümü |
|---|---|---|
| Save (revision 1) | `tlbatch_..._one` | — |
| Save New Revision, **aynı** `record_batch_revision_id` ile | **`None`** | `tlbatch_..._one` |

**Ulaşılabilirlik ölçüldü:** `commands/trade_log.py::create_trade_log_revision`,
`::_require_ready_import` ile config'in adlandırdığı batch'i çözer. `_require_ready_import`
**yalnız** status / `accepted_count` / timezone uyumunu kontrol eder — batch'in **zaten pinli
olup olmadığına bakmaz**. `backend/src` genelinde *"zaten pinli"* anlamına gelen **hiçbir guard
yoktur** (arandı, sıfır sonuç). Yani: bir kullanıcı import'u değiştirmeden bir config alanını
düzenleyip **Save New Revision** derse, revision N'in dayandığı satır **revision N+1'e taşınır**.

**Neden ciddi:** K3 gereği Mainboard item'ı **otomatik repin edilmez** — item hâlâ revision N'e
pinlidir. O item için `_resolve_external` artık `found=False` döner ve validator
**`EXTERNAL_IMPORT_UNRESOLVED` (BLOCKER)** üretir. **Bir an önce READY olan kompozisyon, hiçbir
import bozulmadan BLOCKED olur.**

**Neden bugüne kadar görülmedi (ölçüldü):** bu yolu koşan tek test ailesi
`tests/integration/test_external_object_run_provenance.py`'dir ve oradaki ikinci revision
**bilerek farklı bir source asset** kullanır (`_SECOND_CSV`). Yani suite **aynı batch'in yeniden
kullanıldığı** durumu **hiç koşmaz**. *(CLAUDE.md §ADIM 71'in dersi: geçen bir test, yolun
koşulduğunu göstermez.)*

> **G15 ile ilişkisi — dürüst çerçeve:** bu kusuru **hiçbir seçenek çözmez.** A'nın UNIQUE
> constraint'i çözmez (satır sayısı 2 değil, **0**'dır). B'nin `ORDER BY`'ı çözmez (sıralanacak
> satır yoktur). C ve D zaten dokunmaz. **Ayrı bir kalemdir**; bu belge onu **kaydeder**, karara
> bağlamaz ve bir issue açmaz (issue açmak insan kararıdır).

---

### ETKİ — hangi Ready Check cevapları oynayabilir? **(Bu bir performans kalemi DEĞİLDİR.)**

`ExternalImportState`'in **beş alanının beşi de** satır seçimine bağlıdır ve **hepsi** bir
validator besler. Yanlış satır → **yanlış bir READY/BLOCKED**.

| `ExternalImportState` alanı | Tüketen validator | Üretilen bulgu | Şiddet |
|---|---|---|---|
| `found` | RC-07 kolu | `EXTERNAL_IMPORT_UNRESOLVED` | **BLOCKER** |
| `succeeded` | RC-07 kolu | `EXTERNAL_IMPORT_UNRESOLVED` | **BLOCKER** |
| `accepted_count` | RC-07 kolu (`<= 0`) | `EXTERNAL_IMPORT_UNRESOLVED` | **BLOCKER** |
| `instrument_id` | cross-item instrument karşılaştırması | `INSTRUMENT_SCOPE_MISMATCH` | **BLOCKER** |
| `skipped_reason_codes` ⊃ `INSTRUMENT_MISMATCH` | TL-09 kolu | `MIXED_SYMBOL_SCOPE` | **BLOCKER** |
| `skipped_reason_codes` ⊃ `EXIT_BEFORE_ENTRY` | RC-08 kolu | `TRADE_LOG_CHRONOLOGY_INVALID` | WARNING |

**Ölçüm 1'in iki kazananı tam olarak bu ekseni oynatıyor:** `succeeded=True, accepted_count=2`
→ blocker **yok**; `succeeded=False, accepted_count=0` → `EXTERNAL_IMPORT_UNRESOLVED`
**BLOCKER**. Aynı kompozisyon, aynı an, **iki farklı verdict**.

`instrument_id` ayrıca **cross-item**'dır: yanlış satır yalnız kendi item'ını değil, **strateji
ile karşılaştırmayı** da bozar — yani bir item'daki yanlış seçim **başka bir item hakkında**
blocker üretebilir.

> **Bu belgenin en önemli cümlesi:** leg 3'ü batch'lemek bir **hız** işi değildir. Ready Check'in
> **cevabını** belirleyen bir okumayı değiştirmektir ve cevabın kendisi bugün belirlenimsizdir.
> Bu yüzden leg 3 `P1`/`P2` gibi bir perf slice'ı **değildir** ve öyle sevk edilemez.

### P3 ile ilişki — ölçüldü

> **BU BÖLÜM YENİDEN ÖLÇÜLDÜ (2026-08-17, inceleme sırasında).** Belgenin tabanı `6ca478c`
> `P3`'ü **açık** ölçmüştü; `P3` bu PR incelemedeyken **merge oldu** ve dal onun üstüne alındı.
> Aşağısı **yeni ölçümdür**; eski ölçüm silinmedi, **tarihiyle** bırakıldı — çünkü belgenin
> geri kalanı hâlâ `6ca478c` üzerinde okunmuştur ve **yeniden ölçülmemiştir**.

**İlk ölçüm (`6ca478c`, 2026-08-17): `P3` MERGE OLMAMIŞTI.** PR #741 açıktı;
`docs/performance/query_budgets.json` **sekiz** surface taşıyordu, hepsi `per_item: 0`, ve
`readiness_check.run_readiness_check` **yoktu**.

**Yeniden ölçüm (bu dalın tabanı): `P3` MERGE OLDU** — PR **#741** → `e865b96`. Satır artık
**var**:

| alan | ölçülen değer |
|---|---|
| `axis` | *external work object item (trade_log / trading_signal) in the composition* |
| `queries_small` / `queries_large` | **8** / **18** (`n_small=1`, `n_large=11`) |
| **`per_item`** | **1** — yani **0 DEĞİL**, tam da planın öngördüğü gibi |

Satırın kendi `note`'u leg 3'ü **adıyla** sebep gösteriyor: *"The slope is leg 3:
`_resolve_external` … it is live and UNREPAIRED deliberately — batching it changes which row wins
when two items pin the same `work_object_revision_id`, which is not UNIQUE, and that is an
undecided product question (**gate G15**). P3 measures, it does not repair."*

> **Yani bu belge, sevk edilmiş bir bütçe satırının `note`'unun işaret ettiği hedeftir.** `P3`
> sorunu **ölçtü ve adlandırdı**; kararı vermek G15'in — bu belgenin — işidir. `P1` ve `P2` hâlâ
> inmedi (tick-data ve mirror-deref satırları yok), dolayısıyla **`per_item: 1`'in tek artık
> kaynağı leg 3'tür**.

**Bağ:** satır **dürüstçe yüksek** doğdu ve sırasıyla `P1` → `P2` ile **aşağı ratchet'lenir**.
**G15 imzalanana kadar son artık leg 3'tür**; yani:

- `P3`'ün `note`'u G15'e bir **işaret** taşır ve bu belge o işaretin **hedefidir**.
- Bir imza **A** veya **B** yönünde gelirse leg 3 batch'lenebilir hâle gelir ve satır **0'a**
  iner. **C** gelirse leg 3 batch'lenebilir ama kazanan *"rastgele"* olarak imzalanmış olur.
  **D** gelirse satır **kalıcı olarak** 0'ın üstünde kalır ve `note` bunu **yazılı** hâle getirir.
- **RATCHET KURALI DEĞİŞMEZ:** `query_budgets.json` yalnız **aşağı** iner. Bu belge o dosyaya
  **dokunmadı**.

---

### Seçenekler

**Dört seçenek. Ordered plan yalnız *"hangi satır kazanır"*ı soruyordu; ölçüm (§Ölçüm 2)
dördüncüyü ve A'nın gerçek biçimini açtı. Hiçbiri seçilmemiştir.**

#### Seçenek A — UNIQUE kısıtı BEYAN ET

- **Tanım.** İlişki gerçekten bire-bir ise bunu **söyle**: `work_object_revision_id` üzerinde
  (NULL'lar hariç) **partial UNIQUE index**. Belirsizlik **çözülmez — ORTADAN KALKAR**; iki
  satır artık var **olamaz**, `.first()` en fazla bir satır görür ve batch'leme **kendiliğinden**
  güvenli hâle gelir.
- **Dokunulacak semboller.** Yeni bir alembic revision (`0044_*`) — iki tabloda partial unique
  index. `models/trade_log.py::CanonicalTradeRecordBatch` ve
  `models/trading_signal.py::NormalizedSignalEventRevision` kolon bildirimleri (migration↔model
  parity kapısı gereği). **Okuyucular değişmez**; `resolve_trade_log_batch` /
  `resolve_signal_revision` bayt bayt aynı kalır.
- **Migration var mı?** **EVET** — bu belgedeki **tek** migration gerektiren seçenek.
- **Ready Check CEVABI değişir mi?** **Duplikasyon yoksa hayır** (bugünkü tek satır aynen
  kazanır). **Duplikasyon varsa migration'ın kendisi DÜŞER** — ve bu bir kusur değil, kapının
  **çalışmasıdır**: bugün sessiz olan bir bozukluk `alembic upgrade`'i durdurur.
- **Önkoşul.** §Ölçüm 3'ün sayısı. **0 değilse önce backfill/temizlik gerekir** ve o temizlik
  *"hangi satır kalsın"* sorusunu **operasyonel olarak** sorar — yani B'nin sorusunu bir kez,
  elle cevaplamak gerekir.
- **Geri alma.** `downgrade()` indexi düşürür; veri **kaybolmaz**, hiçbir satır silinmez.
  Temiz.
- **Risk.** (i) Sayı alınmadan sevk edilirse **üretimde migration hatası**; (ii) bire-bir
  varsayımı ileride ürün olarak yanlışlanırsa (bir revision'ın **iki** import'u olması istenirse)
  kısıt bir **duvar** olur — ama bu duvar **görünürdür**, bugünkü sessiz rastgelelikten farklı
  olarak.

#### Seçenek B — BELİRLENİMLİ KAZANAN TANIMLA

- **Tanım.** Belirsizliği **kaldırma**, **karara bağla**: her iki okuyucuya **toplam** bir sıra
  ver — `ORDER BY created_at DESC, <pk> DESC LIMIT 1`. (`created_at` iki modelde de var,
  `server_default=func.now()`; pk'lar `record_batch_id` / `normalized_revision_id` — yani sıra
  **ifade edilebilir** ve **toplamdır**: `created_at` eşitliğinde pk ayırır.) Duplikasyon
  **kalır**, ama kazanan **tanımlıdır**.
- **Emsal.** **Leg 1 tam olarak budur.** P-C2 §D.1: tick okuması `ORDER BY created_at DESC,
  revision_id DESC LIMIT 1` — bir **toplam** sıra — kullandığı için batch formu
  (`DISTINCT ON ... ORDER BY ...`) **birebir aynı** satırı döndürüyor ve *"adjudicate edilecek bir
  sıralama belirsizliği yok"*. B, leg 3'ü **leg 1 ile aynı sınıfa** taşır.
- **Dokunulacak semboller.** `repositories/readiness.py::resolve_trade_log_batch` ·
  `::resolve_signal_revision` — her birine bir `.order_by(...).limit(1)`. Başka hiçbir yer.
- **Migration var mı?** **HAYIR.**
- **Ready Check CEVABI değişir mi?** **Duplikasyon yoksa hayır.** Varsa **evet ve bilerek**:
  bugünkü rastgele cevap **belirlenimli** bir cevaba döner — bu, bir cevabın *düzelmesi* olabilir
  ama *değişmesidir* ve öyle duyurulmalıdır.
- **Ek kazanç.** Bu seçenek **iki işi birden** yapar: bugünkü okumayı belirlenimli yapar **ve**
  leg 3'ün batch'lenmesini açar (`DISTINCT ON (work_object_revision_id)` ile aynı sıra).
- **Geri alma.** Tek commit revert; veri **hiç** dokunulmaz. Bu belgedeki **en ucuz** geri alma.
- **Risk.** (i) **K2 gerilimi** (§Ç3): *"en yenisi kazanır"* kanonun adıyla yasakladığı refleksin
  **komşusudur**; imza metni ayrımı yazmalıdır. (ii) Belirsizliği **çözer ama kaldırmaz** —
  duplikasyon oluşmaya devam edebilir ve artık **sessizce tolere edilir**; bir sonraki okuyucu
  bunu bir kısıt sanabilir. (iii) *"En yeni"* **doğru** kazanan mıdır — bu bir **ürün**
  sorusudur; kanon cevaplamıyor.

#### Seçenek C — MEVCUT DAVRANIŞI KANONİK İLAN ET (imzalı sapma)

- **Tanım.** *"`work_object_revision_id` bire-birdir; duplikasyon oluşamaz; bu yüzden sırasız
  `.first()` yeterlidir."* Varsayım **yazıya geçer** ve imzalanır. Kod değişmez, leg 3
  batch'lenebilir hâle gelir (kazananın kimliği ürün olarak **önemsiz** ilan edildiği için).
- **Dokunulacak semboller.** **Sıfır üretim sembolü.** Yalnız docstring'ler
  (`resolve_trade_log_batch`, `resolve_signal_revision` ve iki model kolonu) + bu belgede imza.
- **Migration var mı?** **HAYIR.**
- **Ready Check CEVABI değişir mi?** **Hayır** — bugünkü davranış aynen korunur.
- **Geri alma.** Yok (değişiklik yok).
- **Risk — DÜRÜST OL.** **Bu, ZORLANMAYAN bir değişmezliğe güvenmektir.** §Ölçüm 2 tam olarak
  bunu ölçtü: bire-bir bugün **doğru**, ama **kaza eseri** doğru — yazma yolunun şeklinden
  türüyor, beyan edilmiş bir kısıt değil. Bir yazıcı eklenirse, bir düzeltme script'i koşarsa ya
  da bir restore aracı satır kopyalarsa, **hiçbir kapı ötmez** ve Ready Check **sessizce
  rastgele** cevap vermeye başlar. Ayrıca C, ORTAK SÖZLEŞME'nin *"'zaten böyle yapılmış' diye
  mevcut davranışı canonical ilan etme"* yasağının **tam hedefidir** (Karar 3/Seçenek B ile aynı
  konum): meşrudur, ama **yalnız bilinçli bir imzayla**; varsayılan olarak seçilemez.
  **Ön koşul:** §Ölçüm 3'ün sayısı **0** çıkmadan C imzalanamaz — sayı > 0 ise C'nin dayandığı
  cümle **ölçümle yanlışlanmış** olur.

#### Seçenek D — KAPSAM KAPISI (leg 3 batch'lenmez)

- **Tanım.** *"Hangi satır kazanır"* sorusuna **cevap verilmez**; bunun yerine bugünkü hâl
  **yazılı** hâle gelir: leg 3 batch'lenmez, `query_budgets.json`'daki whole-operation satırının
  eğimi **leg 3'ü sebep göstererek** yüksek kalır ve `note` bunu G15'e bağlar.
- **Dokunulacak semboller.** **Sıfır üretim sembolü.** `P3` indiğinde
  `docs/performance/query_budgets.json` → `readiness_check.run_readiness_check`'in `note`'u
  (**ratchet'e dokunmadan** — satır zaten ölçülmüş eğimiyle doğar).
- **Migration var mı?** **HAYIR.**
- **Ready Check CEVABI değişir mi?** **Hayır** — ve bu D'nin **tek** gücüdür: hiçbir cevabı
  oynatmaz.
- **Geri alma.** Yok (değişiklik yok).
- **Risk.** **D bir çözüm değil, bir ertelemedir** — Karar 3/Seçenek D ile aynı yapı. Tek başına
  imzalanırsa **G15 AÇIK KALIR** ve §Ölçüm 1'in ölçtüğü belirsizlik **üretimde durmaya devam
  eder** — yalnız artık **bilinerek** durur. D'nin dürüst okunuşu şudur: *"belirsizliği kabul
  ediyoruz, hızı feda ediyoruz, kararı erteliyoruz."* Bu üçünün ilki bir **doğruluk** bedelidir
  ve imza metninde öyle yazılmalıdır.

### Karşılaştırma

| | Belirsizliği ne yapar | Migration | RC cevabı değişir mi | Üretim sembolü | Geri alma | G15 kapanır mı |
|---|---|---|---|---|---|---|
| **A** | **ORTADAN KALDIRIR** | **EVET** | dup yoksa hayır; dup varsa **migration düşer** | 0 (yalnız şema+model) | index drop | **evet** |
| **B** | **KARARA BAĞLAR** | hayır | dup yoksa hayır; dup varsa **evet, bilerek** | 2 okuyucu | tek commit revert | **evet** |
| **C** | **YOK SAYAR (imzalı)** | hayır | hayır | 0 | — | **evet** (sapma olarak) |
| **D** | **SÜRDÜRÜR (yazılı)** | hayır | hayır | 0 | — | **hayır — açık kalır** |

**A ve B birbirini dışlamaz** (UNIQUE + toplam sıra birlikte imzalanabilir: kısıt duplikasyonu
imkânsız kılar, sıra ise okumayı savunmacı olarak belirlenimli bırakır). **C ve D bir arada
imzalanamaz** — C *"sorun yok"*, D *"sorun var ama erteliyoruz"* der. Bu yüzden imza satırında
kombinasyonlar **açıkça** listelenmiştir.

### Bu belgenin ÖNERMEDİĞİ şey

Karar 1/2/3'ün aksine burada **"Önerilen seçenek" başlığı YOKTUR ve bu bilinçlidir.** Ordered
plan G15'i *"kimsenin sahiplenmediği"* iki kapıdan biri olarak kaydediyor ve *"hiçbiri bir
agent'ın muhakemesiyle ikame edilemez"* diyor. Ölçüm dört seçeneği **eşit ölçüde belgelenmiş**
hâle getirdi; aralarındaki seçim bir **doğruluk/hız/borç** takasıdır ve **ürün sahibinindir**.

---

### İMZA SATIRI

**ÖN KOŞUL — önce bu sayı alınmalı (§Ölçüm 3):**

Üretimde aynı `work_object_revision_id`'yi paylaşan satır sayısı:
`canonical_trade_record_batch`: ______   `normalized_signal_event_revision`: ______
`[ ] sayıldı ve 0`   `[ ] sayıldı ve > 0 (önce üretici bulunmalı)`   `[ ] sayılamadı`

> **A ve C bu sayı alınmadan imzalanamaz.** B ve D sayıdan bağımsız imzalanabilir.

**Karar 4 — Ready Check leg 3'ün okuduğu satır:**

`[ ] A (UNIQUE kısıtı beyan et — migration)`  `[ ] B (belirlenimli kazanan: ORDER BY created_at DESC, <pk> DESC)`
`[ ] C (mevcut davranış kanonik — imzalı sapma)`  `[ ] D (kapsam kapısı — G15 AÇIK kalır)`
`[ ] A + B`  `[ ] B, sonra A`

Alt-karar — **B imzalanırsa** kazanan: `[ ] en yeni (created_at DESC)` `[ ] en eski (created_at ASC)`
> *En yeni* seçilirse imza metni doc 05'in *"'latest' revision sessizce kullanılamaz"* kuralıyla
> **neden çelişmediğini** yazmalıdır (§Ç3): oradaki kural `work_object_revision`'ın **pinine**
> dairdir, buradaki sıra ona **bağlı** record batch'ine.

Alt-karar — **A imzalanırsa** kapsam: `[ ] yalnız yeni satırlar (partial unique index)` `[ ] var olan duplikasyon önce temizlenir`

**Hüküm onayı (a)** — bu belgenin ölçtüğü hüküm kabul ediliyor mu (*leg 3'ün per-item okuması
**bugün üretimde belirlenimsizdir**; bu bir batch'leme riski değil, sevk edilmiş bir davranıştır*)?
`[ ] evet` `[ ] hayır (gerekçe: ______)`

**Hüküm onayı (b)** — *duplikasyonun bugün **bilinen bir üreticisi yoktur, ama zorlanmış
bir değişmezi de yoktur*** tespiti kabul ediliyor mu? `[ ] evet` `[ ] hayır (gerekçe: ______)`

**Ayrı kalem onayı** — §Ölçüm 4'ün pin-taşıma kusuru (*aynı batch yeniden pinlendiğinde eski
revision `found=False` çözer → `EXTERNAL_IMPORT_UNRESOLVED`*) **ayrı bir kalem** olarak mı
izlensin? `[ ] evet, issue açılsın` `[ ] hayır, G15 ile birlikte ele alınsın` `[ ] kusur değil (gerekçe: ______)`

karar veren: ________________  tarih: ____________

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Hiçbir karar verilmedi.** Dört seçeneğin hiçbiri seçilmedi, elenmedi, "önerilen" işaretlenmedi.
- **Hiçbir kod değiştirilmedi.** `backend/src`, `frontend/src`, migration ve test ağacına
  **dokunulmadı**. `_resolve_external` **batch'lenmedi**; Seçenek A bir migration **önerir**,
  yazmaz.
- **`docs/performance/query_budgets.json` değişmedi.** Ratchet'e dokunulmadı.
- **Hiçbir issue açılmadı, kapatılmadı, etiketlenmedi.** §Ölçüm 4'ün kusuru için de issue
  açılmadı — imza satırında **ayrı bir kutu** olarak soruldu (issue açmak insan kararıdır).
- **Suite koşulmadı.** Ürün kodu değişmediği için `pytest` **çalıştırılmadı**; bu belgenin
  ölçümleri suite'ten değil, **doğrudan** sevk edilmiş sembollere karşı yazılmış tek seferlik bir
  probe'tan gelir. O probe **repoya girmedi** (test ağacında yeni dosya yok).
- **Üretim duplikasyon sayısı ölçülmedi** ve tahmin edilmedi (§Ölçüm 3, gerekçesiyle).
- **§Ölçüm 4'ün kusuru ölçüldü, kaydedildi, ÜZERİNE GİDİLMEDİ.**
- **`P3` (#741) bu belge yazıldıktan SONRA merge oldu** (`e865b96`); §"P3 ile ilişki"
  bölümü **yalnız o bölüm** yeniden ölçülerek güncellendi. Belgenin geri kalanı hâlâ
  `6ca478c` üzerinde okunmuştur ve **yeniden ölçülmemiştir**. `P3` ürün kodu değiştirmedi,
  dolayısıyla buradaki diğer ölçümler bu taban üzerinde de geçerlidir (doğrulandı).
- **A-08 bu belgeden etkilenmez.** Blocker sayısı **1** (yalnız A-08), verdict **BLOCKED**.
- **Kabul borcu ratchet'i değişmedi** — hiçbir kriter kapanmadı, hiçbir sınıf taşınmadı.
