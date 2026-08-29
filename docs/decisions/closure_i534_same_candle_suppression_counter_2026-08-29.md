<!-- doc-status: current -->
# Same-candle suppressions: kendi sayacını hak ediyor mu (GH #534 md. 3)

> **BU BELGEDE HİÇBİR ÜRÜN SEMANTİĞİ KARARA BAĞLANMAMIŞTIR.** Yazarın rolü **ölçüm ve
> hazırlık**tır. §Karar'ın imza bloklarını yalnız ürün sahibi / maintainer doldurur.
> `closure_i854_external_import_pin_stability_2026-08-28.md` ve
> `closure_od2_mark_production_binding_2026-08-28.md` ile aynı disiplin.

- **Tarih:** 2026-08-29
- **Base:** `origin/main` @ `de3d8816` (`fix(stage-136): GH #532 — entry_exit_collision
  taksonomiye kaydedildi (#874)`). Ölçüm sırasında açık PR **yoktu** — anlık görüntüdür,
  garanti değil (ADIM 100).
- **İzleme:** GitHub issue **#534** (açık). ADIM 137 issue'nun md. 1, 2 ve 4'ünü **sevk
  etti**; md. 3 bu belgeye devredildi. **İssue KAPATILMADI** ve kapatmak **insan kararıdır**.
- **Bloklar:** RC verdict'ini **bloklamaz**; tek blocker **A-08 (#514)** ve bu karar o hatta
  dokunmaz.
- **Neden ayrı belge:** md. 1/2/4 birer **yayımlama** kararıdır (yeni anahtar, sevk edilmiş
  hiçbir değeri oynatmaz). md. 3'ün bir okuması **sevk edilmiş bir sayacın değerini
  değiştirir** — o bir adjudication'dır, test slice'ının kararı değil (ADIM 42 kuralı).

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — `suppressed_entries` **üç** yolu birden sayıyor

| # | Yol | Nerede | Ne demek |
|---|---|---|---|
| A | §5.9 same-candle çakışması | `engine.py`, `entry_exit_collision` yayımının hemen ardından | FLAT'ken aynı barda entry + exit close-confirmed; politika `exit_first` değilse entry bastırılır |
| B | Yön yanlılığı — plan yolu | `engine.py`, `_LedgerEffect(counter="suppressed_entries")` | `long_and_short` değilken ters yönlü indikatör sinyali |
| C | Yön yanlılığı — breakout proxy | `engine.py`, aynı `_LedgerEffect` biçimi | aynı ret, breakout yolunda |

Üçü de **tek** alanı artırır (`state.py::_Ledger.suppressed_entries`, `output.py`
`"suppressed_entries"` olarak yayımlar). **Sonuç:** sıfır olmayan bir değer üç ayrı sebebin
hangisine ait olduğunu söylemez, yani §5.9 politikasının **etkisi** ölçülemez.

ADIM 137 bu boşluğun **politika** yarısını kapattı (`same_candle_entry_exit` artık her
koşuda yayımlanıyor), **sayaç** yarısını **kapatmadı**.

## Ölçüm 2 — İki okuma, ve yalnız biri bedelsiz

Issue'nun cümlesi (*"a dedicated counter … **rather than** folding them into the shared
`suppressed_entries`"*) iki farklı şeye okunabilir ve **bedelleri ayrışır**:

| Okuma | Ne yapar | Bedel |
|---|---|---|
| **(a) EKLE** | Yeni `same_candle_suppressions` sayacı; A yolu **hem** yeni sayacı **hem** `suppressed_entries`'i artırmaya devam eder | Toplamsal. Sevk edilmiş hiçbir değer oynamaz. Bedeli: iki sayaç **örtüşür**, okur `suppressed_entries`'i bir toplam sanabilir — ki öyledir, ama bunu söyleyen bir şey yok |
| **(b) TAŞI** | Yeni sayaç; A yolu **artık** `suppressed_entries`'i artırmaz | **Sevk edilmiş bir sayının değeri değişir.** Aynı stratejinin dünkü ve bugünkü Result'ı aynı barlarda farklı `suppressed_entries` raporlar; golden digest'ler oynar |

**Ölçülmüş, varsayılmadı:** (b) bir **davranış** değişikliği değil bir **rapor** değişikliğidir
— hiçbir işlem, fill ya da equity noktası oynamaz. Ama `suppressed_entries` sevk edilmiş bir
artefakt alanıdır ve ADIM 136'nın imzalı ekseni (*"artefaktın baytları oynuyor mu"*) (b) için
**oynuyor** der.

## Ölçüm 3 — Üçüncü bir seçenek var ve ucuz

| Okuma | Ne yapar | Bedel |
|---|---|---|
| **(c) HİÇBİRİ** | Sayacı olduğu gibi bırak | Sıfır. §5.9'un etkisi `entry_exit_collision` **olaylarını** sayarak da elde edilebilir — olay ADIM 136'dan beri taksonomide **kayıtlı** ve `detail["resolution"]` `ambiguous_entry_suppressed` / `flat_exit_noop_then_entry` ayrımını **zaten** taşıyor |

**Bu, md. 3'ün yazıldığı gündeki dünyada mevcut DEĞİLDİ.** #534 açıldığında olay
taksonomiye kayıtlı değildi (#532 — ADIM 136'da kapandı). Yani md. 3'ün öncülü
(*"tek aggregate sinyal `suppressed_entries`"*) **bugün bayat**: ikinci bir aggregate yol var
ve o, üç yolu karıştırmıyor.

**Karşı-argüman, dürüstlük için:** olaylar **ayrı bir artefakttır** (`signal_events`
journal'ı), diagnostics değil — yalnız diagnostics bloğunu okuyan bir tüketici onları hiç
görmez, ve saymak O(1) bir tamsayı okuması değil journal üzerinde O(n) bir taramadır.
**Ölçülmemiş olan, bilerek yazılmıyor:** journal'a bir üst sınır / budama uygulanıp
uygulanmadığı bu slice'ta **aranmadı ve bulunmadı** — `output.py`'de bir cap yok, ama
üretim yolunun tamamı taranmadı, o yüzden *"budanmaz"* diye bir iddia burada YAPILMIYOR.

---

## Karar

> Aşağıdaki kutulardan **birini** işaretleyin. İşaretlemek **ürün sahibinin** işidir; ajan
> boş bırakır. İmzasız kutu = karar verilmedi, ve `#534` **açık kalır**.

- [ ] **(a) EKLE** — `same_candle_suppressions` eklensin, `suppressed_entries` **el
      değmesin** (örtüşme kabul, `ENGINE_VERSION` bump'ı gerekir çünkü yeni anahtar 45+
      golden digest'i oynatır)
- [ ] **(b) TAŞI** — yeni sayaç eklensin ve A yolu `suppressed_entries`'ten **çıkarılsın**
      (sevk edilmiş bir sayının değeri değişir; bump gerekir)
- [ ] **(c) HİÇBİRİ** — sayaç olduğu gibi kalsın; §5.9'un etkisi `entry_exit_collision`
      olaylarından okunur (kod yok, `#534` md. 3 *"karar verildi: gerekmiyor"* olarak kapanır)
- [ ] **Başka:** ______________________________________________

**İmza:** ______________________  **Tarih:** ____________

