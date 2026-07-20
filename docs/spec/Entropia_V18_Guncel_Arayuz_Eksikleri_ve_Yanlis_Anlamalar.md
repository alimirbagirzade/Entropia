# Entropia V18 — Güncel Arayüzde Kalan Yanlış Anlamalar ve Zorunlu Düzeltmeler

## Belgenin amacı

Bu belge, Entropia'nın güncel kodlanmış arayüzünü V18 prototipi, 22 sayfalık arayüz anlatımı, Master Technical Reference ve geliştirici düzeltme şartnamesiyle karşılaştırır.

Bu bir öneri listesi değildir. Aşağıdaki maddeler, belgelerde tanımlanan ürünün doğru kabul edilebilmesi için giderilmesi gereken arayüz ve kullanıcı akışı eksikleridir.

Önemli ayrım:

- Son güncellemelerle gerçek dosya yükleme, Strategy Details'in üç kolonlu yapısı, Market Data görünümü, Ready Check modalı, inline RUN/Result, Package Library, User Manual, Panel ayrımı ve birçok destek ekranı ciddi ölçüde düzeltilmiştir.
- Buna rağmen ürünün merkezî çalışma modeli hâlâ tam uygulanmamıştır.
- Bir bileşenin, route'un veya testin bulunması gereksinimin tamamlandığı anlamına gelmez.
- Kabul ölçütü, belgelerdeki kullanıcı yolunun aynı bağlam içinde gerçek verilerle tamamlanabilmesidir.

---

# 1. En büyük yanlış anlama şu: Entropia ayrı sayfalar koleksiyonu değildir; Mainboard merkezli tek bir çalışma alanıdır

Geliştirici, belgelerdeki ekranları büyük ölçüde ayrı route'lar ve ayrı workbench sayfaları olarak yorumlamıştır. Oysa V18 ürün modelinde Mainboard yalnızca nesnelerin listelendiği bir ana sayfa değildir. Mainboard, Strategy, Trading Signal ve Trade Log nesnelerinin eklendiği, yatay satırlarının açıldığı, düzenlendiği, doğrulandığı, kaydedildiği, Ready Check'in çalıştırıldığı, RUN'ın başlatıldığı ve sonucun görüldüğü ana çalışma alanıdır.

Mevcut uygulamada Strategy bu modele yaklaştırılmıştır; Trading Signal, Trade Log ve Package akışları ise hâlâ Mainboard'dan ayrılmaktadır.

## Mevcut yanlış davranış

- Strategy satırı açıldığında gerçek `StrategyDetailsPanel` satır içinde gösterilmektedir.
- Trading Signal ve Trade Log satırları açıldığında gerçek editör gösterilmemektedir.
- Kullanıcıya `Edit in Trading Signal` veya `Edit in Trade Log` bağlantısı sunulmakta ve ayrı route'a gönderilmektedir.
- Yeni Trading Signal/Trade Log draft satırları da editör yerine `Continue in ... workbench` bağlantısı göstermektedir.
- Add Package doğrudan `/packages/create` route'una gitmektedir.
- Üst menüdeki Add Strategy, Trading Signal, Trade Log ve Add Package seçenekleri de Mainboard eylemlerini çalıştırmak yerine ayrı route'lara gitmektedir.

Kod kanıtları:

- `frontend/src/pages/Mainboard.tsx:191`
- `frontend/src/pages/Mainboard.tsx:221`
- `frontend/src/pages/Mainboard.tsx:337`
- `frontend/src/pages/Mainboard.tsx:387`
- `frontend/src/pages/Mainboard.tsx:515`
- `frontend/src/pages/Mainboard.tsx:591`
- `frontend/src/app/nav.ts:28`
- `frontend/src/app/nav.ts:205`

## Olması gereken davranış

Mainboard aşağıdaki akışı route değiştirmeden tamamlamalıdır:

`Add → nesne türünü seç → yatay satırı oluştur → oku kullanarak aç → gerçek tür editöründe çalış → validate → save → satırı kapat → Ready Check → RUN → inline Result`

## Zorunlu düzeltme

1. Trading Signal ve Trade Log editörleri sayfa bileşeni olmaktan çıkarılmamalı, fakat reusable editor bileşenlerine ayrılmalıdır.
2. Bu editor bileşenleri hem Mainboard satırının içinde hem de gerekli olduğunda deep-link route'unda kullanılabilmelidir.
3. Primary workflow her zaman Mainboard içindeki bileşen olmalıdır.
4. Standalone route'lar yalnızca back-compatibility, geçmiş kayda deep-link veya teknik inceleme amacıyla kalmalıdır.
5. Üst menüdeki Add eylemleri route navigation yapmamalı; Mainboard'a gitmeli ve ilgili inline create eylemini açmalıdır.
6. Kullanıcı edit, validate, save ve cancel işlemleri sırasında Mainboard'dan ayrılmamalıdır.

## Kabul ölçütü

- Strategy, Trading Signal ve Trade Log için ayrı ayrı gerçek browser testi yapılmalıdır.
- Kullanıcı Mainboard'dan ayrılmadan yeni satır oluşturabilmeli, dosya seçebilmeli, validate edebilmeli, kaydedebilmeli ve paneli kapatabilmelidir.
- Test URL'nin süreç boyunca `/` olarak kaldığını doğrulamalıdır.

---

# 2. Yanlış anlama şu: “Inline satır oluşturmak”, satırın içine başka sayfaya giden bağlantı koymak değildir

Mevcut uygulama Trading Signal ve Trade Log için yatay bir draft satırı üretmektedir. Ancak açılan alanda gerçek çalışma formu yoktur. Bu nedenle satır görünüşte inline, işlev olarak route launcher'dır.

Bu yaklaşım UI-03, UI-04 ve UI-05'in temel amacını karşılamaz.

## Zorunlu düzeltme

- Draft satırı açılır açılmaz iki kolonlu gerçek Trading Signal veya Trade Log editörü mount edilmelidir.
- Dosya seçme, upload progress, cancel upload, retry, column mapping, import request, import report, validation, save, cancel ve close aynı panel içinde bulunmalıdır.
- `Continue in workbench` ve `Edit in ...` bağlantıları primary action olmaktan çıkarılmalıdır.
- Kaydetme başarılı olduğunda transient draft satırı persisted Mainboard satırına dönüşmelidir; kullanıcı yeni bir sayfaya taşınmamalıdır.
- Draft kaldırma, kaydedilmiş nesneyi silme ve paneli kapatma birbirinden açıkça ayrılmalıdır.

---

# 3. Yanlış anlama şu: Trading Signal ve Trade Log'un iki kolonlu görünmesi yeterli değildir; bu görünüm Mainboard satırının içinde çalışmalıdır

Trading Signal ve Trade Log sayfalarının iki kolonlu görünümü, gerçek dosya seçicisi, format rehberi ve sticky toolbar'ı geliştirilmiştir. Bu ilerleme doğrudur. Fakat doğru bileşen yanlış bağlama yerleştirilmiştir.

Belgelerde istenen şey “iki kolonlu ayrı sayfa” değil, “Mainboard'daki yatay satır açılınca görünen iki kolonlu editör”dür.

## İlave eksikler

- Her iki editörde de oluşturma/kaydetme aşamasında 16 satırlık ham JSON payload textarea'sı primary form olarak kullanılmaktadır.
- Trading Signal'de kullanıcı `TradingSignalConfig payload` JSON'unu düzenlemek zorundadır.
- Trade Log'da kullanıcı `TradeLogConfig payload` JSON'unu düzenlemek zorundadır.
- Sticky toolbar'da belgede istenen Save, Cancel ve panel close eylemlerinin tamamı yoktur; temel olarak yalnızca Save bulunmaktadır.
- `Source asset id` normal kullanıcıya düzenlenebilir teknik alan olarak gösterilmektedir. Upload sonrası sistem tarafından üretilen bu kimlik kullanıcıdan istenmemeli ve elle değiştirilememelidir.
- Mevcut revision düzenleme akışları da ham JSON editörüne dayanmaktadır.

Kod kanıtları:

- `frontend/src/pages/TradingSignal.tsx:493`
- `frontend/src/pages/TradingSignal.tsx:508`
- `frontend/src/pages/TradeLog.tsx:496`
- `frontend/src/pages/TradeLog.tsx:511`

## Zorunlu düzeltme

1. Trading Signal ve Trade Log config payload'ları belgelerdeki alanlara karşılık gelen typed form kontrollerine çevrilmelidir.
2. Ham JSON yalnızca yetkili teknik kullanıcılar için kapalı bir Advanced disclosure olarak kalabilir.
3. Normal kullanıcı hiçbir root id, revision id, source asset id veya JSON nesnesi girmemelidir.
4. Toolbar en az `Validate`, `Save`, `Cancel` ve `Close panel` eylemlerini içermelidir.
5. Save başarısından sonra satır Mainboard'a bağlı ve açık/kapalı durumu korunmuş şekilde kalmalıdır.

---

# 4. Yanlış anlama şu: Add Package bir Create Package bağlantısı değildir

V18 prototipindeki `Add Package`, Mainboard üzerinde küçük ve bağlama bağlı bir seçim popover'ıdır. Mevcut kod, Add menüsünde doğrudan `/packages/create` bağlantısı göstermektedir.

Bu iki davranış aynı değildir:

- `Add Package`: erişilebilir ve kullanılabilir bir Strategy Package revision'ını seçip bundan yeni bir Strategy Draft üretme işlemidir.
- `Create Package`: yeni bir package üretmek için CP Agent workspace'ini açma işlemidir.

## Mevcut eksik

- Strategy Draft üretmekte kullanılabilecek eligible Strategy Package revision'larını listeleyen seçim popover'ı yoktur.
- Kullanıcı uygun package türü, revision, approval/validation durumu ve uyumluluk bilgisini görerek seçim yapamamaktadır.
- Mevcut Strategy Package revision'ından Strategy Draft üretmek ile yeni package oluşturmak aynı route bağlantısına indirgenmiştir.
- “Create new package” seçeneği, Add Package popover'ının ikincil seçeneği olarak sunulmamaktadır.

## Zorunlu düzeltme

- Mainboard içinde gerçek Add Package popover'ı oluşturulmalıdır.
- Production popover yalnızca seçilebilir, aktif/published/usable ve kullanıcının use izni bulunan Strategy Package revision'larını göstermelidir; Trading Signal ve Trade Log package türü gibi sunulmamalıdır.
- Arama, package adı, market/timeframe uyumluluğu, exact revision ve temel compatibility özeti sağlanmalıdır.
- `Add Strategy From Package` eylemi source package'ı mutate etmeden, seçilen exact root/revision ve dependency snapshot provenance'ıyla yeni bir Strategy Draft üretmelidir.
- Üretilen Strategy Draft Mainboard'da yatay Strategy satırı olarak görünmeli ve gerçek Strategy Details editörü inline açılmalıdır.
- Yeni package üretmek isteyen kullanıcı için popover içinde ikincil `Create new package` eylemi bulunmalıdır.

---

# 5. Yanlış anlama şu: Strategy Details'te JSON'u gizlemek, eksik formları tamamlamakla aynı şey değildir

Strategy Details üç kolona ve büyük ölçüde belgelenen bölüm sırasına taşınmıştır. Ancak structured form tarafından desteklenmeyen alanlar hâlâ ham payload editörüne bırakılmaktadır.

Kod bunu açıkça “fallback for advanced fields” olarak tanımlamaktadır.

Kod kanıtları:

- `frontend/src/components/StrategyDetailsPanel.tsx:272`
- `frontend/src/components/StrategyDetailsPanel.tsx:292`
- `frontend/src/components/StrategyGraphForm.tsx:607`
- `frontend/src/components/StrategyGraphForm.tsx:642`
- `frontend/src/components/StrategyGraphForm.tsx:971`
- `frontend/src/components/StrategyConfigForm.tsx:618`

## Mevcut eksikler

- `Advanced (raw payload)` tüm kullanıcılara görünmektedir; teknik role göre sınırlandırılmamıştır.
- Bazı gelişmiş block alanları structured formda bulunmamaktadır.
- Restriction/filter config değerleri type-specific form yerine JSON textarea ile girilmektedir.
- Formula parametrelerinin bir bölümü Advanced JSON içinde korunmaktadır.
- Kullanıcı geçerli bir stratejinin bütün ayarlarını yalnızca belgelenmiş form alanlarıyla kuramayabilir.
- Mainboard satırı açıldığında editorün altında pinned revision id, enable/disable, reorder ve label gibi composition yönetim alanları sürekli görünür durumdadır. Bunlar ana Strategy Details kompozisyonunu uzatmakta ve prototip hiyerarşisini zayıflatmaktadır.

## Zorunlu düzeltme

1. Her desteklenen restriction/filter türü için typed form oluşturulmalıdır.
2. Formula ve package parameter override alanları structured kontrollerle sunulmalıdır.
3. Reference chain ve dependency seçimleri kullanıcı dostu picker üzerinden yapılmalıdır.
4. Raw JSON normal kullanıcı akışından tamamen kaldırılmalıdır.
5. Advanced payload yalnızca açıkça yetkilendirilmiş teknik role gösterilmeli, şema doğrulamalı ve varsayılan olarak kapalı olmalıdır.
6. Composition controls küçük, ikincil ve kapalı bir disclosure/menu içine taşınmalıdır; Strategy Details'in görsel merkezini oluşturmamalıdır.
7. `/strategy` route'u üst menüde primary Add Strategy yolu olmaktan çıkarılmalıdır.

---

# 6. Yanlış anlama şu: Üst menüde doğru isimleri göstermek, doğru eylemi yapmak anlamına gelmez

Üst menü prototipteki etiketleri büyük ölçüde taşımaktadır; fakat Mainboard altındaki menü eylemleri yanlış davranmaktadır.

## Mevcut yanlış davranış

- `Add Strategy` → `/strategy`
- `Trading Signal` → `/trading-signal`
- `Trade Log` → `/trade-log`
- `Add Package` → `/packages/create`

Bu davranış Mainboard'un kendi `+ Add` akışıyla çelişmektedir ve iki ayrı ürün modeli yaratmaktadır.

## Zorunlu düzeltme

- Üst menü Mainboard action dispatcher kullanmalıdır.
- Başka bir route'tayken Add Strategy seçilirse önce Mainboard açılmalı, ardından yeni Strategy satırı oluşturulup inline editor açılmalıdır.
- Trading Signal ve Trade Log için de aynı davranış uygulanmalıdır.
- Add Package seçildiğinde Mainboard'daki package popover'ı açılmalıdır.
- Kullanıcı aynı isimli iki menünün farklı sonuç üretmesiyle karşılaşmamalıdır.

---

# 7. Yanlış anlama şu: Teknik kimliği kullanıcıya açıklamak, kullanıcı dostu seçim arayüzü yapmak değildir

Arayüzün çeşitli yerlerinde normal kullanıcıdan altyapı kimliklerini elle girmesi veya kopyalaması beklenmektedir.

## Kesin örnekler

- Research Data setup, `Linked Market Data entity id` alanı istemektedir.
- Research revision formu `Re-link market entity id` ve `Base revision id` istemektedir.
- Trading Signal ve Trade Log formları düzenlenebilir `Source asset id` göstermektedir.
- Bazı lifecycle ve evidence formları revision/task/run kimliklerini serbest metin olarak almaktadır.
- Market Data revision formu `Instrument id` ve optional JSON payload istemektedir.

Kod kanıtları:

- `frontend/src/pages/ResearchData.tsx:329`
- `frontend/src/components/ResearchLifecycle.tsx:208`
- `frontend/src/components/ResearchLifecycle.tsx:220`
- `frontend/src/pages/TradingSignal.tsx:259`
- `frontend/src/pages/TradeLog.tsx:262`
- `frontend/src/pages/MarketData.tsx:1197`

## Zorunlu düzeltme

- Root/revision/entity/source asset/task/run kimlikleri normal kullanıcı girdisi olmamalıdır.
- İlgili kaynaklar isim, tür, durum, owner, revision ve uygunluk bilgileriyle picker üzerinden seçilmelidir.
- Seçimin arkasındaki immutable ID sistem tarafından taşınmalıdır.
- Teknik ID yalnızca read-only provenance/debug alanında ve gerekli role gösterilebilir.
- Manuel ID girişi gerekiyorsa bu yalnızca açıkça adlandırılmış Advanced/Admin aracı olmalıdır.

---

# 8. Yanlış anlama şu: Research Data alanına herhangi bir metin yazılması, Approved Market Data bağımlılığının sağlandığı anlamına gelmez

Research Data workflow strip ve dependency alert eklenmiştir. Fakat görsel kilit gerçek backend durumuna bağlı değildir.

Mevcut kodda:

`dependencyReady = marketEntityId.trim().length > 0`

Yani kullanıcı alana geçersiz herhangi bir metin yazdığında:

- dependency alert kaybolur,
- 4. ve 5. adımlar görsel olarak açılır,
- Create Dataset butonu etkinleşir.

Backend daha sonra isteği reddetse bile arayüz kullanıcıya bağımlılığın sağlandığını yanlış biçimde göstermiş olur.

Kod kanıtı:

- `frontend/src/pages/ResearchData.tsx:103`

## Zorunlu düzeltme

- Linked Market Data serbest metin alanı kaldırılmalıdır.
- Yalnızca ACTIVE + APPROVED ve kullanıcının erişebildiği Market Data revision'larını gösteren picker kullanılmalıdır.
- Workflow strip, alert ve Create butonu aynı server-truth dependency projection'ına bağlanmalıdır.
- Loading, invalid, deprecated, rejected, permission denied ve stale durumları ayrı gösterilmelidir.
- Kullanıcı yalnızca gerçekten uygun revision seçildiğinde ilerleyebilmelidir.

---

# 9. Yanlış anlama şu: JSON alanını “optional” yapmak, ürün alanlarını tasarlama yükümlülüğünü ortadan kaldırmaz

Ham JSON yalnızca Strategy Details'te bulunmamaktadır. Çeşitli operasyon ekranlarında hâlâ ürün alanlarının yerine JSON textarea kullanılmaktadır.

## Kesin örnekler

- Trading Signal config payload
- Trade Log config payload
- Strategy advanced payload
- Restriction/filter type-specific config
- Market Data revision payload
- Research Data revision payload
- Research feature definition
- Create Package baseline metadata
- Package manifest import

## Zorunlu düzeltme

- Belgelerde adı, türü ve anlamı tanımlanmış her alan için uygun form kontrolü oluşturulmalıdır.
- Enum değerleri select/radio, boolean değerleri checkbox/toggle, kaynak ilişkileri picker, listeler tekrarlanabilir row editor, tarih/saat alanları uygun date-time input ile verilmelidir.
- JSON yalnızca gerçekten şeması önceden bilinmeyen, teknik ve yetkili kullanım senaryolarında Advanced bölümde kalabilir.
- JSON parse hatası göstermek tek başına yeterli değildir; schema, type, required-field ve domain validation kullanıcı alanlarının yanında gösterilmelidir.

---

# 10. Yanlış anlama şu: Yetkisiz eylemi backend'den 403 ile reddetmek, doğru arayüz yetkilendirmesi değildir

Backend'in işlemi reddetmesi güvenlik açısından gereklidir; ancak arayüzün yetkisiz kullanıcıya kullanamayacağı Admin eylemlerini primary kontrol olarak göstermesi doğru kullanıcı deneyimi değildir.

Market Data ve Research lifecycle yorumlarında approve/deprecate/revoke kontrollerinin role göre önceden gizlenmediği, server denial'ın gösterildiği açıkça belirtilmektedir.

## Zorunlu düzeltme

- `/me` veya eşdeğer server-truth permission projection kullanılmalıdır.
- Admin-only eylemler yetkisiz kullanıcıya primary button olarak gösterilmemelidir.
- Gerekliyse read-only durum ve “Admin approval required” açıklaması gösterilmelidir.
- Client-side görünürlük hiçbir zaman backend authorization'ın yerine geçmemeli; ikisi birlikte uygulanmalıdır.
- Permission yüklenirken kontrol fail-closed davranmalıdır.

---

# 11. Yanlış anlama şu: Create Package ekranının iki kolonlu görünmesi, bütün package üretim deneyiminin tamamlandığını kanıtlamaz

Create Package iki kolonlu CP Agent workspace'e dönüştürülmüş, gerçek baseline CSV yükleme ve Pre-Check modalı eklenmiştir. Ancak bazı ürün alanları ve kabul yolculuğu hâlâ eksiktir.

## Mevcut eksikler

- Baseline metadata kullanıcıdan JSON olarak istenmektedir.
- Provider, symbol, timeframe, range ve benzeri bilinen metadata alanları structured form değildir.
- Mainboard Add Package davranışı bu workspace ile yanlış biçimde birleştirilmiştir.
- Gerçek browser E2E testi request oluşturma ve Pre-Check aşamasında durmaktadır.
- Candidate generation, draft üretimi, validation, revision, Admin approval ve publish aşamalarını tek başarılı yolculukta tamamlayan browser testi yoktur.

Kod ve test kanıtları:

- `frontend/src/pages/CreatePackage.tsx:860`
- `frontend/src/pages/CreatePackage.tsx:927`
- `frontend/e2e/specs/04-create-package-lifecycle.spec.ts:9`

## Zorunlu düzeltme

- Baseline metadata typed alanlara dönüştürülmelidir.
- CP Agent workspace içinde lifecycle'ın her aşaması bir önceki gerçek server state ile açılmalıdır.
- Hangi eylemin neden kilitli olduğu doğrudan ilgili kontrolün yanında gösterilmelidir.
- Tek bir gerçek Playwright testi, request'ten published package'a kadar bütün akışı tamamlamalıdır.
- Test “blocked veya error da kabul” yaklaşımını kullanmamalı; beklenen başarılı state'leri tek tek doğrulamalıdır.

---

# 12. Yanlış anlama şu: Bir testin herhangi bir yapılandırılmış cevap alması, kullanıcı yolunun çalıştığını göstermez

Mevcut Mainboard E2E testi gerçek, çalışabilir Strategy üretmemektedir. Test, Ready Check'in blocked dönmesini ve RUN butonunun kilitli kalmasını kabul edilen sonuç saymaktadır.

Bu nedenle testin geçmesi aşağıdaki kritik akışı kanıtlamaz:

`valid Strategy → attach → Ready PASS → RUN enabled → SUCCEEDED Result → inline result render`

Kod kanıtları:

- `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts:15`
- `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts:20`
- `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts:64`
- `frontend/e2e/README.md:63`

## Zorunlu düzeltme

- Approved Market Data ve gerekli package revision'ları test fixture/seed sürecinde gerçek olarak hazırlanmalıdır.
- Mainboard'da Strategy inline oluşturulmalı, validate edilmeli, kaydedilmeli ve attach edilmelidir.
- Ready Check sonucunun açıkça `READY/PASS` olduğu doğrulanmalıdır.
- RUN butonunun disabled durumdan enabled duruma geçtiği doğrulanmalıdır.
- Gerçek run'ın `SUCCEEDED` olması beklenmelidir.
- Result'ın Mainboard altında açıldığı ve headline metrics/provenance gösterdiği doğrulanmalıdır.
- Blocked veya error sonucu bu golden-path testinde başarı sayılmamalıdır.

---

# 13. Yanlış anlama şu: Mainboard'daki teknik composition kontrolleri ürün editörünün görsel merkezinde olmamalıdır

Strategy satırı açıldığında gerçek editorün altında şu teknik/operasyonel kontroller sürekli görünmektedir:

- pinned revision id,
- enabled/disabled,
- move up/down,
- display label override,
- row-version/OCC kaynaklı yönetim davranışları,
- delete/soft-delete açıklamaları.

Bu kontrollerin bir bölümü gereklidir; fakat V18 Strategy Details panelinin ana görsel yapısını oluşturmamalıdır.

## Zorunlu düzeltme

- Kullanıcının sık kullandığı enable/disable ve delete eylemleri kompakt row action olarak kalabilir.
- Reorder mümkünse drag handle veya belgelenen kompakt hareket kontrolüyle yapılmalıdır.
- Revision provenance, pin yönetimi ve teknik ayrıntılar kapalı `Composition settings` disclosure/menu içine taşınmalıdır.
- Strategy Details'in altında ikinci bir uzun teknik yönetim formu oluşmamalıdır.
- Aynı ayrım Trading Signal ve Trade Log satırlarında da korunmalıdır.

---

# 14. Yanlış anlama şu: Uygulamanın backend beklerken sonsuza kadar “Loading” göstermesi kabul edilebilir bir hata durumu değildir

Yerel frontend açıldığında backend çalışmıyorsa Mainboard yalnızca `Loading Mainboard…` durumunda kalabilmektedir. Kullanıcı problemin kimlik doğrulama, bağlantı, API başlangıcı veya veri yükleme olduğunu anlayamamaktadır.

## Zorunlu düzeltme

- API çağrılarına görünür timeout ve bağlantı hatası davranışı eklenmelidir.
- Uygulama shell'i API health durumunu göstermelidir.
- Backend kapalıysa kullanıcıya `Backend unavailable`, kullanılan API adresi ve Retry eylemi verilmelidir.
- Authentication gerekli ise loading yerine gerçek `UNAUTHENTICATED` durumu ve Login eylemi gösterilmelidir.
- SSE bağlantısı, API readiness ve authentication birbirinden ayrı durumlar olarak sunulmalıdır.
- Sonsuz spinner hiçbir primary sayfanın son durumu olmamalıdır.

---

# 15. Yanlış anlama şu: Masaüstü sayfaları düzeltmek, responsive arayüzün tamamlandığı anlamına gelmez

Güncel remediation kaydı, 375 px genişlikte uygulama shell'inin yaklaşık 513 px minimum genişliğe taşarak yatay overflow ürettiğini kabul etmektedir.

Bu problem yalnızca Future Dev sayfasına ait değildir; ortak menu/app shell problemidir ve bütün sayfaları etkiler.

## Zorunlu düzeltme

- Üst menü dar genişlikte hamburger/disclosure veya kontrollü scroll modeli kullanmalıdır.
- Body/document seviyesinde yatay overflow bulunmamalıdır.
- İç tablolar kendi scroll container'ında kalmalı, sayfayı genişletmemelidir.
- Fixed Ready Check/RUN kabuğu mobil viewport'u kapatmamalıdır.
- Inline Strategy/Trading Signal/Trade Log panelleri 3/2 kolondan bilinçli tek kolon düzenine geçmelidir.
- 375, 768, 1280, 1440 ve 1920 px genişliklerinde görsel test yapılmalıdır.

---

# 16. Yanlış anlama şu: “Bileşen testleri geçti” demek, prototip görünümünün kabul edildiği anlamına gelmez

V18 düzeltme şartnamesi bütün 22 sayfa için 1280, 1440 ve 1920 px ekran görüntülerini; responsive doğrulamayı; prototiple yan yana karşılaştırmayı ve product-owner onayını zorunlu tutmaktadır.

Repository içinde bütün 22 sayfayı kapsayan final screenshot seti veya visual-regression baseline'ı bulunmamaktadır.

Şartname kanıtları:

- `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md:485`
- `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md:799`
- `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md:836`
- `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md:855`

## Zorunlu düzeltme

1. Full-stack seed ortamı oluşturulmalıdır.
2. Her sayfa boş, loading, normal-data, error ve permission-denied durumlarında görüntülenmelidir.
3. Bütün 22 hedef sayfanın 1280, 1440 ve 1920 px screenshot'ları üretilmelidir.
4. Mainboard ve inline editorler ayrıca 375 ve 768 px'te doğrulanmalıdır.
5. Screenshot'lar V18 prototype ile yan yana incelenmelidir.
6. Sapmalar issue olarak kaydedilmeli; product-owner yazılı onayı alınmadan UI maddeleri Complete yapılmamalıdır.
7. Kritik sayfalar için Playwright screenshot regression eklenmelidir.

---

# 17. Yanlış anlama şu: Dokümantasyonda “Complete” yazması, arayüzün gerçekten tamamlandığını göstermez

Remediation status bütün UI maddelerini Complete göstermektedir. Ancak aynı kod tabanında:

- Trading Signal ve Trade Log için inline editor yerine route linki bulunmaktadır.
- Add Package popover yerine route linki bulunmaktadır.
- TS/TL save akışı raw JSON istemektedir.
- Research dependency görsel kilidi yalnızca input'un boş olup olmamasına bağlıdır.
- Golden-path E2E testi başarılı Ready → RUN → Result akışını tamamlamamaktadır.
- 22 sayfalık final screenshot seti yoktur.
- Ortak mobil shell overflow'u bilinmektedir.

## Zorunlu düzeltme

- `Complete` yalnızca acceptance criteria gerçek browser ve gerçek backend ile geçtiğinde kullanılmalıdır.
- UI-01, UI-03, UI-04, UI-05, UI-06, UI-12 ve ilgili functional maddeler yeniden `In Progress` durumuna alınmalıdır.
- Her requirement satırında code evidence yanında gerçek E2E ve screenshot evidence bulunmalıdır.
- Bilinen eksiklerin “honest boundary” olarak yazılması onları tamamlanmış hâle getirmez; eksik V1 gereksinimiyse açıkça incomplete olmalıdır.

---

# 18. Sayfa bazında güncel değerlendirme

Bu bölüm eski rapordaki düzeltilmiş maddelerin yeniden hata olarak verilmesini önlemek için eklenmiştir.

## Hâlâ doğrudan düzeltme gereken sayfalar

### Mainboard

- Trading Signal ve Trade Log gerçek inline editor değildir.
- Add Package popover yoktur.
- Üst menü Mainboard action'larını bypass etmektedir.
- Composition controls görsel olarak gereğinden baskındır.
- Full golden-path browser acceptance yoktur.

### Strategy Details

- Structured formların kapsamadığı alanlar raw payload'a bırakılmıştır.
- Restriction/filter ve bazı formula parameter alanları JSON istemektedir.
- Advanced JSON role-gated değildir.
- Standalone `/strategy` hâlâ primary menü hedefidir.

### Add Outsource Signal

- Nested submenu vardır; fakat seçilen nesnenin gerçek editörü satır içinde açılmamaktadır.
- Transient satır yalnızca başka workbench'e devam bağlantısıdır.

### Trading Signal

- İki kolonlu görünüm vardır; fakat Mainboard içinde değildir.
- Create/revise işlemi raw JSON payload istemektedir.
- Cancel ve inline panel close akışı eksiktir.
- Teknik source asset id normal form alanıdır.

### Trade Log

- İki kolonlu görünüm vardır; fakat Mainboard içinde değildir.
- Create/revise işlemi raw JSON payload istemektedir.
- Cancel ve inline panel close akışı eksiktir.
- Teknik source asset id normal form alanıdır.

### Add Package / Create Package

- Mainboard Add Package seçim popover'ı yoktur.
- Existing Strategy Package revision'ından draft üretme ile new package creation ayrılmamıştır.
- Baseline metadata JSON formudur.
- Request → candidate → validation → revision → approval → publish golden-path E2E yoktur.

### Research Data

- Approved Market Data bağımlılığı gerçek server projection yerine non-empty text ile görsel olarak açılmaktadır.
- Market Data seçimi picker değil entity-id alanıdır.
- Revision ve feature lifecycle'ın çeşitli bölümleri ID/JSON girişi istemektedir.
- Yetkiye bağlı operasyon kontrolleri role-aware presentation ile tamamen ayrılmamıştır.

### Market Data

- Create/upload ana görünümü önemli ölçüde düzeltilmiştir.
- Revision lifecycle hâlâ optional JSON payload ve teknik instrument id göstermektedir.
- Admin lifecycle actions için role-aware presentation tamamlanmalıdır.

### Ortak uygulama shell'i

- Backend yokluğunda açıklayıcı bağlantı durumu yerine sonsuz loading oluşabilmektedir.
- Mobil yatay overflow tamamen çözülmemiştir.
- Mainboard üst menüsü ve Mainboard iç Add menüsü farklı davranmaktadır.

## Kod düzeyinde önceki temel yapısal eksikleri giderilmiş görünen, fakat görsel kabul kanıtı hâlâ bulunmayan sayfalar

Aşağıdaki sayfalarda önceki rapordaki ana yapısal problemler için remediation kodu bulunmaktadır. Bunlar yeniden “eski hâliyle eksik” olarak raporlanmamalıdır. Ancak 22 sayfalık screenshot/product-owner acceptance tamamlanmadan görsel olarak kesin kabul edilmemelidir:

- Pre-Check
- Package Library
- Embedded System Packages
- Rationale Families
- Portfolio / Equity Allocation
- Backtest Ready Check
- RUN & Backtest Results
- Results History
- Arrange Metrics
- Analysis Lab
- Panel / Management
- Panel / Logs
- Trash
- User Manual
- Future Dev alt sayfaları

Bu sayfalarda yapılması gereken son iş “yeniden tasarlamak” değil; gerçek full-stack veriyle görsel karşılaştırma, responsive kontrol, permission-state kontrolü ve product-owner kabulüdür.

---

# 19. Uygulama sırası

## P0 — Önce düzeltilmesi gerekenler

1. Trading Signal ve Trade Log'u gerçek reusable inline editor bileşenlerine ayır.
2. Bu editorleri Mainboard draft ve persisted satırlarına mount et.
3. Mainboard ve üst menü Add davranışlarını tek action modelinde birleştir.
4. Add Package seçim popover'ını ve existing Strategy Package → derived Strategy Draft akışını yap.
5. TS/TL primary JSON payload editörlerini typed formlarla değiştir.
6. Strategy Details'te kalan JSON bağımlılıklarını kaldır.
7. Research Data dependency picker ve server-truth state bağını kur.
8. Başarılı Mainboard → Ready → RUN → inline Result E2E testini oluştur.

## P1 — Ürün kullanılabilirliği

9. Bütün normal-user teknik ID girişlerini picker/read-only provenance modeline çevir.
10. Admin-only kontrolleri role-aware presentation ile ayır.
11. Backend unavailable/auth/session-expired durumlarını açık hata ekranlarına dönüştür.
12. Mobil app-shell overflow'unu gider.
13. Create Package'ın tam başarılı lifecycle E2E testini tamamla.

## P2 — Görsel kabul ve kapanış

14. 22 sayfanın gerçek veriyle screenshot matrisini üret.
15. V18 prototype ile side-by-side karşılaştır.
16. Responsive ve accessibility kontrollerini tamamla.
17. Product-owner onayı al.
18. Ancak bundan sonra remediation status maddelerini Complete olarak kapat.

---

# 20. Nihai kabul tanımı

Arayüz aşağıdaki koşulların tamamı sağlanmadan V18'e uygun veya tamamlanmış kabul edilmemelidir:

- Mainboard'daki Strategy, Trading Signal ve Trade Log satırlarının üçü de gerçek editorünü inline açıyor.
- Kullanıcı bu nesneleri route değiştirmeden oluşturuyor, düzenliyor, validate ediyor, kaydediyor ve kapatıyor.
- Add Package gerçek seçim popover'ı üzerinden çalışıyor.
- Normal kullanıcı raw JSON veya altyapı ID'si girmiyor.
- Research dependency ve bütün workflow kilitleri server-truth state'e bağlı.
- Ready Check gerçekten PASS oluyor ve RUN otomatik açılıyor.
- Gerçek RUN başarılı bitiyor ve Result Mainboard altında görüntüleniyor.
- Create Package süreci request'ten publish'e kadar browser üzerinden tamamlanıyor.
- Backend/auth/permission/error/loading durumları kullanıcıya doğru ve açıklayıcı gösteriliyor.
- Mobil ve masaüstü genişliklerinde yatay sayfa taşması bulunmuyor.
- 22 sayfanın final screenshot seti V18 prototipiyle karşılaştırılmış ve product owner tarafından onaylanmış.

Temel düzeltme ilkesi şudur:

> V18 belgelerinde tarif edilen görünüm, yalnızca benzer renkler ve kartlarla yeniden çizilmemelidir. Aynı nesne hiyerarşisi, aynı çalışma bağlamı, aynı açılma/kapanma davranışı ve aynı kullanıcı yoluyla uygulanmalıdır.
