<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Ekran okuyucu denetimi — checklist (A-08)

> **Bu belge bir DENETİM DEĞİL, denetimin reçetesidir.** Denetim yapılmamıştır.
> `entropia_v18_remediation_status.md` A-08 satırı ve `v18_final_acceptance.md` §6
> AÇIK kalır; bu belgenin varlığı hiçbir satırı Complete yapmaz.
>
> **Takip issue'su GitHub #514 2026-08-12T11:08:58Z'de bir insan tarafından YENİDEN
> AÇILDI (`reopened`) — denetim yine de koşulmadı.** Ne kapatma ne yeniden açma,
> aşağıdaki reçetenin tek satırını bile karşılamaz; ikisi de issue'nun durumunu
> değiştirdi, defterin içeriğini değil. Takip durumunun kanonik kaydı:
> [`docs/audit/a11y_screen_reader_audit_results.md`](../audit/a11y_screen_reader_audit_results.md)
> §STATUS ▸ *Tracking-issue state*.

## Neden otomatikleştirilemez

axe-core, Playwright ve Lighthouse **DOM'u** denetler: rol var mı, isim var mı, kontrast
oranı kaç. Ekran okuyucu denetiminin sorduğu soru farklıdır: **kullanıcı duyduğu şeyle
görevi tamamlayabiliyor mu?** Bunun otomatik karşılığı yok, çünkü:

- Duyuru **sırası** ve **kesilme** davranışı ekran okuyucu + tarayıcı + işletim sistemi
  üçlüsüne göre değişir; DOM'dan türetilemez.
- `aria-live` bölgesinin gerçekten okunup okunmadığı yalnız dinlenerek anlaşılır — DOM'da
  doğru `aria-live="polite"` durup hiç duyurulmaması yaygın bir hatadır.
- "İsim var" ile "isim anlaşılır" farklıdır: `aria-label="btn-3"` axe'ı geçer, kullanıcıyı
  geçmez.
- Sanal imleç (virtual cursor) modu ile odak modu arasındaki geçişler, tablo/ızgara
  gezinimi ve modal içine hapsolma yalnız gerçek ürün üzerinde denenerek doğrulanır.

**Sonuç:** bu denetim bir **insana** düşer. Bir agent bunu yaptığını iddia edemez.

## Kime düşüyor

| Rol | Sorumluluk | Not |
|---|---|---|
| **Denetimi yapan** | Ekran okuyucuyu düzenli kullanan bir denetçi (tercihen görme engelli kullanıcı ya da sertifikalı a11y denetçisi — **tercih, şart değil**; §0'ın *"Screen-reader user?"* alanı `neither` yazmayı kaldırır ve sınırı kayda geçirir) | **ATANMADI** — ama artık **izleniyor**: #514 2026-08-12'de yeniden açıldı ve atamayı açıkça *"the remaining human step"* olarak adlandırıyor. |
| **Ortam** | Seeded Compose stack (E2E ile aynı fixture: `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1`), Admin oturumu | Aynı fixture, aksi halde boş sayfalar denetimi eksik gösterir |
| **Bulguların kaydı** | Her bulgu → `v18_visual_deviations.md` biçiminde FIX / PO-APPROVE statüsü | Bu belgeye değil |

## Zorunlu kombinasyonlar

`~/.claude/rules/accessibility.md` **en az iki** ekran okuyucu ister:

| # | Ekran okuyucu | Tarayıcı | Platform | Durum |
|---|---|---|---|---|
| SR-1 | **NVDA** (son kararlı) | Firefox | Windows | ☐ yapılmadı |
| SR-2 | **VoiceOver** | Safari | macOS | ☐ yapılmadı |
| SR-3 (opsiyonel) | JAWS | Chrome | Windows | ☐ kapsam dışı |

---

## A. Her sayfada koşulacak temel geçiş (22 sayfa × 2 SR)

Sayfa listesi = `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` (axe taramasıyla
**aynı** matris; iki denetim aynı yüzeyi konuşsun diye).

| # | Kontrol | Beklenen | Kaynak |
|---|---|---|---|
| A-1 | Sayfa yüklendiğinde başlık duyurusu | Sayfa adı duyulur; `<h1>` sayfa başına **bir** tane | rules §Semantic HTML |
| A-2 | Landmark gezinimi (NVDA `D` / VO rotor) | **ÜÇ** landmark ayrı ayrı bulunur: `banner`, `navigation`, `main`. **`contentinfo` BEKLENMEZ** — Entropia footer sevk etmez; imzalı karar **D-11** (2026-08-13), bkz. `a11y_ci_ratchet_and_adjudication.md` §4b | rules §Semantic HTML + D-11 |
| A-3 | Başlık gezinimi (NVDA `H` / VO rotor) | `h1→h2→h3` sırası atlamasız | rules §Semantic HTML |
| A-4 | Tüm etkileşimli öğeler sanal imleçle bulunabiliyor | Buton/link/alan listesi eksiksiz | rules §Keyboard |
| A-5 | Buton mu link mi doğru duyuruluyor | Aksiyon = "button", gezinme = "link"; `div onClick` YOK | rules §Semantic HTML |
| A-6 | Görsel etiketsiz kontrollerin erişilebilir adı anlamlı | "btn-3" / "düğme" değil, görevi anlatan ad | rules §ARIA |
| A-7 | Tablolar `<th scope>` ile okunuyor | Hücre okunurken kolon başlığı duyulur | rules §Semantic HTML |
| A-8 | Dekoratif görsel `alt=""`, anlamlı görsel `alt` dolu | Boş `alt` sessiz geçer | rules §Media |

## B. Entropia'ya özgü akışlar (bu ürünün kritik yüzeyleri)

| # | Akış | Kontrol | Neden kritik |
|---|---|---|---|
| B-1 | **Add menüsü** (Mainboard `+ Add`) | `aria-expanded` durum değişimi duyuruluyor; ok tuşlarıyla gezinilir; Escape kapatır ve **odak tetikleyiciye döner** | `useEscapeToClose` A11Y-FIX-01 ile eklendi — davranış görsel doğrulandı, **duyuru doğrulanmadı** |
| B-2 | **Add Package popover** | Aynı; ayrıca popover açıkken arkaplan okunmuyor | Aynı hook |
| B-3 | **Ready Check sonucu** (Passed/Failed/Warnings) | Sonuç `aria-live` ile duyuruluyor; blocker listesi başlıklı bölge | Sonuç yalnız renkle ayrışmamalı — rules §Visual |
| B-4 | **Backtest RUN ilerleme + SSE olayları** | Durum değişimi (queued→running→completed/failed) duyuruluyor, ama **her tick'te değil** | `aria-live="polite"`; agresif duyuru kullanılamaz hâle getirir |
| B-5 | **Hata zarfı** (`ErrorBody`: code/message/remediation) | Hata duyuruluyor; `remediation` insan metni okunuyor; `field_path` ilgili alana bağlı (`aria-describedby`) | Hata sözleşmesi zaten `remediation` taşıyor — SR'ye ulaşıp ulaşmadığı denenmedi |
| B-6 | **OCC çakışması (409)** | Çakışma duyuruluyor ve kullanıcı ne yapacağını duyuyor | Sessiz 409 = veri kaybı algısı |
| B-7 | **Dosya yükleme** (Market Data / Trade Log / Trading Signal / Research Data) | Dosya seçimi, ilerleme ve `UNSUPPORTED_SOURCE_FILE_TYPE` reddi duyuruluyor | Fail-closed kapı K-07 |
| B-8 | **Trash restore/purge onayı** | Yıkıcı eylem onayı modal olarak duyuruluyor; odak modal içinde hapis; Escape iptal | rules §Keyboard (focus trap) |
| B-9 | **Uzun tablolar** (Package Library, Results History) | Satır sayısı ve sayfalama durumu duyuruluyor; genişletme `aria-expanded` | Superset yüzeyler |
| B-10 | **Login** | Alan etiketleri, hata mesajı ve otomatik odak duyuruluyor | Otomatik odak "doğru davranış" olarak kabul edilmişti — SR'de doğrulanmadı |

## C. Bilinen riskler — denetim bunları özellikle sınasın

| # | Risk | Nereden biliyoruz |
|---|---|---|
| C-1 | **45 accent-mavi düğüm düşük kontrast** (A11Y-01 Sınıf A) | Az gören (low-vision) kullanıcı ekran büyütücüyle çalışır; kontrast onu doğrudan etkiler — SR denetimi bunu **kapsamaz**, ayrı eksendir |
| C-2 | `.rd-step[data-locked]` **opaklık 0.7** | Kilitli durum yalnız görsel; SR'ye "locked" olarak duyuruluyor mu? (`aria-disabled`/metin) |
| C-3 | Ham `mbi_…` / `btres_…` ULID render'ları | SR bunları harf harf okur — F-07 §4.4'te 4 yüzey açık |
| C-4 | Makine değeri etiketler (`ohlcv`, `translate_existing_code`) | D-2 FIX(R3) kapsamında; SR bunları okur |
| C-5 | Yalnız renkle ayrışan durumlar (yeşil/kırmızı rozetler) | rules §Visual "renk tek başına bilgi taşımaz" |

---

## Bulgu kayıt şablonu

```
SR-BULGU-nn
Ekran okuyucu / tarayıcı : NVDA 2026.x / Firefox
Sayfa                    : /backtest/ready-check
Adım                     : Ready Check sonucu döndüğünde
Beklenen                 : Sonuç ve blocker sayısı duyurulur
Gözlenen                 : Hiçbir şey duyurulmadı; sonuç yalnız görsel
WCAG                     : 4.1.3 Status Messages (AA)
Statü                    : FIX / PO-APPROVE
```

## Çıkış kriteri

Denetim **tamamlandı** sayılabilmesi için:

1. SR-1 ve SR-2 kombinasyonlarının **ikisi de** koşulmuş,
2. A bölümü 22 sayfanın hepsinde, B bölümü 10 akışın hepsinde işaretlenmiş,
3. Her bulgu FIX / PO-APPROVE statüsüyle kaydedilmiş,
4. FIX bulguları landed **ya da** PO tarafından imzalı sapmaya çevrilmiş olmalı.

Bu dört madde sağlanana kadar A-08 **AÇIK**tır ve hiçbir belge onu Complete gösteremez.

**Takip issue'sunun durumu bu dördünden hiçbirini karşılamaz — iki yönde de.** #514
bugüne kadar **iki kez** (2026-07-30, 2026-08-07) tek bir kayıtlı sonuç olmadan
kapatıldı ve **ikisi de geri alındı** (2026-08-03, 2026-08-12). Bugün **AÇIK**, ama
açık olması da bir sonuç değildir. Kapı bu dört maddedir, issue'nun durumu değil.
