<!-- doc-status: current -->
# ADIM 48 KICKOFF — RC §6.5 (K-2..K-6): beş a11y gözlemi için ürün kararı promptları

> **Bu belge bir slice KAYDI DEĞİL — bir KARAR ÖNÜ belgesidir.** Hiçbir kod
> değişmedi, hiçbir karar VERİLMEDİ. Aşağıdaki dört prompt, PO karar verdikten
> **sonra** temiz bir oturuma yapıştırılmak üzere hazırlanmıştır; her biri hangi
> kararı varsaydığını kendi başlığında yazar.
>
> Kaynak otorite: `docs/audit/a11y_screen_reader_audit_results.md` §6 (K-1..K-7) +
> `docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` §6.5.
> Sayısal otorite bu belge DEĞİL → `docs/generated/repository_facts.md`.

## 0. Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** Bu belge bunu değiştirmez ve
değiştiremez. K-2..K-6'nın **hepsi** kapansa bile A-08 defteri boş kalır
(0/4 çıkış kriteri) ve verdict BLOCKED'dır. Beş kalemin hiçbiri A-08'in yerine
geçmez; ikisi (K-5, K-6a) **A-08'e bağımlıdır** ve bu belge onlar için bilerek
uygulama promptu vermez.

## 1. Üç ortak gerçek — beş kalemin hepsini etkiler (ölçüldü, 2026-08-12)

**(1) v18 mockup bir *başlık semantiği* otoritesi DEĞİL.**
`docs/spec/index_guncellenmis_duzeltilmis_v18.html` içinde `<h1>` **0**, `<h2>` **1**,
`<h3>` **0**, `<h4>` **14**; `footer` **0**, `skip-link` **0**. Sevk edilen uygulama
h1 + h3 kullanıyor → outline ekseninde mockup'tan **zaten** ayrışmış ve bu bilinçliydi.
Mockup'ın bağladığı şey **görünen stil**. Başlık seviyesi değişikliği, hesaplanmış stil
aynı kaldığı sürece v18 kuralını ihlal **etmez**; görünür bir footer eklemek ise **eder**.

**(2) axe bu beşini göremez — çünkü görmesi istenmedi.**
`frontend/e2e/specs/13-a11y-scan.spec.ts:96` yalnız `wcag2a / wcag2aa / wcag21a /
wcag21aa / wcag22aa` etiketlerini koşuyor. `heading-order` axe'ta **best-practice**
kuralıdır, bu etiketlerin hiçbirinde değildir → **K-5 ratchet'e görünmez**. `bypass`
(2.4.1) ise `<main>` landmark'ı yüzünden **geçer** → **K-2 de görünmez**.
**Yeşil axe bu beş kalem hakkında hiçbir şey söylemiyor.** Bu bir kusur değil, kapsam —
ama "axe yeşil" cümlesi bu kalemler için kanıt olarak kullanılamaz.

**(3) Başlık seviyesi neredeyse hiç test edilmemiş.**
Tüm e2e ağacında `level: <n>` assertion'ı **1 tane**
(`e2e/specs/17-page-coverage.spec.ts:107`, `level: 2`, `/user-manual`); vitest tarafında
**1 tane**. K-4/K-5'in maliyeti **test kırılmasında değil**, tag-scoped CSS
selector'larında ve görsel baseline'larda.

## 2. Karar tablosu

| # | Kapsam (precheck) | Öneri | A-08'e bağımlı mı | Prompt |
|---|---|---|---|---|
| **K-2** skip link | 23 / 23 — stable | **FIX** — 2 dosya, 0 baseline, 0 test | Hayır | **P-1** |
| **K-3** `contentinfo` | 23 / 23 — stable | **PO-APPROVE** — ürünü değil A-2 beklentisini hizala | Hayır | **P-2** |
| **K-4** `/user-manual` h1 | 1 — stable | **FIX** — 1 token, 2 test satırı, 0 baseline | Hayır | **P-1** |
| **K-5** h1→h3 | **21 / 23 ±1** — kararsız | **A-08 BEKLE** | **Evet** | **yok (P-4)** |
| **K-6a** halka görünüyor mu | probe: 1 | **A-08 BEKLE** | **Evet** | **yok (P-4)** |
| **K-6b** halka kontrastı | global | **bugün karar verilebilir** — ölçüldü **2.68 : 1 < 3 : 1** | Hayır | **P-3** |

**Sıra:** P-1 önce (K-4'ün K-5 sayısını 22'ye çıkardığını ölçmüş olursun) → P-2 ve P-3
bağımsız, herhangi bir sırayla → K-5 / K-6a A-08'e kadar **dokunulmaz**.

---

## 3. P-1 — K-2 + K-4 (FIX, tek slice)

> **Varsayılan karar:** *"K-2 skip link eklenecek, K-4 `/user-manual` başlığı `h1`'e
> çıkarılacak."* PO bunu vermediyse bu promptu yapıştırma.

```
ENTROPIA — ADIM 48: K-2 (skip link) + K-4 (/user-manual h1) — presentation-only FIX

CLAUDE.md §Session START protokolünü uygula, sonra bu slice'ı yaz. Bu bir
frontend/presentation slice'ıdır: route path, react-query key, OCC token
(If-Match / expected_*_version / X-*-Version), Idempotency-Key, hook, SSE
taksonomisi, lib/*.ts veri mantığı ve app/nav.ts NAV/ALL_NAV_ITEMS
DEĞİŞMEZ. Görsel referans zorunlu: docs/spec/index_guncellenmis_duzeltilmis_v18.html.

KARAR (PO, <TARİH>): K-2 ve K-4 FIX. K-3 kapsam dışı, K-5/K-6 A-08 bekliyor —
bu slice onlara DOKUNMAZ ve onları kapattığını İDDİA ETMEZ.

ÖNCEDEN ÖLÇÜLDÜ (yeniden türet, doğrula, sonra ilerle):
· K-2: her route'ta ilk tabbable öğe shell'in "Log out" butonu. 23/23 route,
  precheck'te STABLE sınıf. Hedef landmark: frontend/src/app/Layout.tsx:456
  <main className="workspace">.
· axe bunu görmüyor: 13-a11y-scan.spec.ts:96 yalnız wcag* etiketlerini koşuyor,
  `bypass` kuralı <main> yüzünden zaten geçiyor. Yeşil axe kanıt DEĞİL.
· WCAG 2.4.1 landmark'larla (ARIA11) karşılanabilir ve banner/navigation/main
  zaten var → bu bir UYGUNLUK İHLALİ DEĞİL, ergonomi boşluğudur. Kaydı böyle yaz.
· K-4: frontend/src/pages/UserManual.tsx:181 → <h2 className="page-title">.
  .page-title CLASS TABANLI (global.css:466 — margin/font-size/font-weight/color
  açıkça yazılı) → tag değişimi hesaplanmış stili DEĞİŞTİRMEZ.

YAP:
1. Skip link: Layout.tsx'e ilk tabbable öğe olarak in-page atlama linki, <main>'e
   id + tabIndex={-1}. Stil global.css'te; link YALNIZ :focus-visible'da görünür
   olmalı (sr-only/clip deseni), görünmezken LAYOUT KAYDIRMAMALI.
2. UserManual.tsx:181 → <h1 className="page-title">. Sınıf değişmez.
3. Hizalanacak testler (yalnız bunlar): e2e/specs/17-page-coverage.spec.ts:107
   (level: 2 → 1), e2e/utils/pageTruth.ts:15 sapma notu,
   e2e/specs/20-a11y-prechecks.spec.ts:211-218 gerekçe yorumu (artık yalnız
   outline gerekçesi kalır; "h1 yok" gerekçesi düşer).

DÜRÜSTLÜK KAPISI — bu slice'ın YAN ETKİSİ, gizlenmeyecek:
/user-manual bugün h2(:181) → h3(:259), yani ATLAMA İÇERMİYOR ve K-5'in 21'inin
DIŞINDA. h1'e çıkarınca outline h1 → h3 olur → K-5 21/23'ten 22/23'e ÇIKAR.
Bunu ÖLÇ (precheck ≥2 koşu; ilk koşu soğuktur ve EKSİK raporlar — K-5'i 18
gösterdiği ölçüldü), gerçek sayıyı docs/audit/a11y_screen_reader_audit_results.md
§6 K-5 satırına ve RC §6.5'e YAZ. Sayıyı düşürmeye çalışma, KAYDET.

DOĞRULAMA (hepsi, sırayla):
  cd frontend && npm run lint && npm run typecheck && npm test -- --no-file-parallelism
  cd frontend && npm run coverage        # kapı, rapor değil
  scripts/a11y-audit-stack.sh up
  cd frontend/e2e && npm run a11y        # EN AZ İKİ KEZ, ikinci sayıyı al
  cd frontend/e2e && npm run visual      # 23/23 baseline DEĞİŞMEMELİ
BEKLENEN: 0 baseline diff. Diff çıkarsa skip link kurulumu yanlıştır —
baseline'ı GÜNCELLEME, CSS'i düzelt.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin altısı da. RC §6.5'te K-2 ve K-4
satırları kapanır; K-3/K-5/K-6 AÇIK kalır. Blocker sayısı DEĞİŞMEZ (1 — yalnız
A-08), verdict BLOCKED. docs/ADIM48_KICKOFF.md'yi `doc-status: historical`'a
düşür (aşağıdaki §7'ye bak) ve yeni kickoff'u `current` yap.
```

---

## 4. P-2 — K-3 (imzalı kayıt, kod yok)

> **Varyant A — önerilen. Varsayılan karar:** *"Footer eklemiyoruz; A-2'nin
> dört-landmark beklentisi bu ürün için üç."*

```
ENTROPIA — ADIM <n>: K-3 (contentinfo landmark) — imzalı sapma kaydı, KOD YOK

CLAUDE.md §Session START protokolünü uygula. Bu bir DOKÜMAN slice'ıdır:
frontend/ altında hiçbir dosya değişmez, hiçbir <footer> eklenmez.

KARAR (PO, <TARİH>, imzalayan: <AD>): Entropia bir footer sevk etmez. v18
mockup'ta footer yok (grep: 0 eşleşme). Checklist A-2'nin "dört landmark"
beklentisi bu ürün için ÜÇ'tür (banner / navigation / main).

GEREKÇE, kayda geçecek:
· Hiçbir WCAG başarı ölçütü contentinfo landmark'ı zorunlu KILMAZ; 1.3.1 VAR OLAN
  yapının programatik sunumunu ister, olmayan bir footer'ınkini değil.
· Görünür footer = v18 görsel referansının ihlali → 23 -linux baseline'ının 23'ü
  yeniden üretilir + Lighthouse CLS tabanı yeniden ölçülür.
· BOŞ/gizli <footer> AÇIKÇA REDDEDİLDİ: sayacı yeşile çevirir, rotor'la oraya
  atlayan kullanıcıya hiçbir şey vermez — ölçüyü ürüne değil ölçüme uydurmaktır.

YAP:
1. docs/implementation/v18_visual_deviations.md → D-10 BİÇİMİNDE yeni kayıt
   (adı verilmiş imzalayan + ISO tarih + açık kapsam). İmzalayan verilmemişse
   KAYIT YAZMA, DUR ve sor — imzasız sapma yazmak yasaktır.
2. docs/implementation/a11y_screen_reader_audit_checklist.md → A-2'nin beklentisi
   dört değil ÜÇ landmark; gerekçe bu kayda referansla.
3. docs/audit/a11y_screen_reader_audit_results.md §6 K-3 satırı → statü
   "Open — reported, not gated" yerine "PO-APPROVE (imzalı sapma <ID>)".
4. RC §6.5 tablosunda K-3 satırı kapanır.

YAPMA: precheck sondasının K-3 advisory'sini SUSTURMA. Advisory ölçümdür; karar
onu geçersizleştirmez, yalnız dispozisyonunu belirler. (Advisory metnine
"adjudicated <ID>" eklenebilir — sayı DÜŞÜRÜLEMEZ.)

DOĞRULAMA: cd frontend/e2e && npm run a11y   (≥2 koşu; advisory sayısı DEĞİŞMEMELİ)
KAPANIŞ: ritüelin altısı da. Blocker sayısı DEĞİŞMEZ (1), verdict BLOCKED.
```

> **Varyant B — gerçek footer içeriği (sürüm / ortam / yasal metin) isteniyorsa:**
> bu bir a11y kalemi **değil**, yeni bir **v18 sapmasıdır**. Yukarıdaki promptu
> kullanma; ayrı bir slice olarak planlanmalı ve maliyeti şudur: 23 `-linux`
> baseline'ının yeniden üretimi (sıra ZORUNLU: `down -v` → seed → `npm test` →
> `screenshots:update`) + Lighthouse tabanının yeniden ölçümü (CLS 1/23 rotada
> zaten donmuş kusur) + `v18_visual_deviations.md` kaydı.

---

## 5. P-3 — K-6b (odak halkasının kontrastı)

> **Varyant A. Varsayılan karar:** *"2.68 : 1 kabul edilemez, halka rengi değişecek."*

```
ENTROPIA — ADIM <n>: K-6b — odak halkasının kontrastı (WCAG 1.4.11), tek CSS kuralı

CLAUDE.md §Session START protokolünü uygula. Presentation-only; v18 referansı
zorunlu. K-6a (halka GÖZLE görünüyor mu) bu slice'ın DIŞINDA ve A-08 bekliyor —
bu slice onu kapatmaz, kapattığını İDDİA ETMEZ.

ÖLÇÜLDÜ (yeniden hesapla, doğrula):
· frontend/src/styles/global.css:53 → :focus-visible { outline: 2px solid
  var(--accent); outline-offset: 2px; border-radius: 4px } ; --accent = #00a9e8.
· #00a9e8 ↔ beyaz kontrast = 2.68 : 1 ; #f5f5f5 zeminde 2.46 : 1.
  WCAG 1.4.11 Non-text Contrast (AA) odak göstergesi için 3 : 1 ister → DÜŞÜYOR.
· axe bunu KOŞMUYOR (odak halkası kontrastı axe kuralı değildir) ve repoda başka
  hiçbir yerde ölçülü değil. Yeşil ratchet kanıt DEĞİL.
· D-10 (45 accent-blue düğüm) 1.4.3 eksenidir; bu 1.4.11'dir — AYRI ölçüt, D-10
  bunu kapsamaz.

YAP: :focus-visible halkasının rengini 3:1'i geçen bir değere çevir (ör.
var(--text) #222 → 15.9:1). SADECE odak halkası. --accent DEĞİŞKENİNE DOKUNMA;
dolgu/kenarlık/link paletine DOKUNMA — mockup odak durumunu tarif ETMİYOR, bu
yüzden halka rengi bir v18 sapması DEĞİLDİR; palet değişimi OLURDU.
Hesaplanan yeni oranı yorumda değil, docs/audit/... §6 K-6 satırında yaz.

DOĞRULAMA:
  cd frontend && npm run lint && npm run typecheck && npm test -- --no-file-parallelism
  cd frontend/e2e && npm run visual     # odak yokken screenshot alınır → 0 diff BEKLENİR
  cd frontend/e2e && npm run a11y       # ≥2 koşu
Diff çıkarsa kuralın kapsamı çok geniştir (odak dışı öğeye sızmış) — baseline'ı
GÜNCELLEME, selector'ı daralt.

KAPANIŞ: ritüelin altısı da. K-6 satırı İKİYE ayrılır: K-6b KAPANDI (ölçülü),
K-6a AÇIK — A-08 bekliyor. Blocker sayısı DEĞİŞMEZ (1), verdict BLOCKED.
```

> **Varyant B — rengi koruyup kaydetmek:** P-2'nin gövdesini kullan; kaydın konusu
> *"odak halkası accent-blue kalır, 1.4.11 karşılanmıyor, kapsam: tüm
> `:focus-visible` göstergeleri"* olur ve **imzalayan adı zorunludur**. Kod değişmez.
> Üçüncü seçenek — **sessiz bırakmak** — bugünkü hâldir ve önerilmez: ölçüm var,
> ölçüt düşüyor, kayıt yok.

---

## 6. P-4 — K-5 + K-6a: uygulama promptu YOK, bilerek

Bu ikisi için "düzelt" promptu **yazılmadı**. Yazmak, brifingin kendi sonucunu
çiğnemek olurdu.

**K-5 — neden A-08 bekliyor.** Gerekçe "büyük iş" değil, **düzeltmenin yönünün
denetime bağlı olması**. Ölçülen maliyet:

| Tag | Occurrence / dosya |
|---|---|
| `<h1>` | 29 / 29 |
| `<h2>` | 8 / 7 |
| `<h3>` | **98 / 36** |
| `<h4>` | **76 / 23** |
| `<h5>` | 28 / 6 |
| `<h6>` | 2 / 1 |

Merdiveni bir basamak kaydırmak (h3→h2, h4→h3, …) **204 başlık / ~40 dosya**
demektir. Asıl tuzak CSS'te: başlık stilleri **tag-scoped descendant selector**'larla
yazılmış — `global.css:991` `.card h3`, `:992` `.card h4`, `:363`
`.ready-report-card h3`, `:447` `.state h3`, `:839` `.manual-drawer-header h3`.
Tag'i değiştirip selector'ı unutulan her yerde başlık **UA varsayılan boyutuna düşer**
→ v18 stili bozulur, görsel kapı kırmızıya döner. Alternatif ("görünmeyen bir h2
ekle") boş footer ile **aynı sınıftadır**: sayacı düşürür, rotor'a anlamsız düğüm ekler.
Üstüne, ölçümün kendisi **kararsız** (5 koşuda 18/21/20/21/21) — denetim öncesi
düzeltme, doğrulanmamış bir sayıya karşı 40 dosya değiştirmek olurdu.

**K-6a — neden A-08 bekliyor.** Sondanın çıktısı bu soruya dair **kanıt taşımıyor**:
`e2e/specs/20-a11y-prechecks.spec.ts:293-326` `el.focus()` ile **programatik** odak
veriyor, tarayıcılar ise `:focus-visible`'ı programatik odakta (son etkileşim klavye
değilse) **eşleştirmez**. Yani `before === after` sonucu **beklenen bir ölçüm
artefaktıdır**, "halka yok" demek değildir — `global.css:53`'te halka **yazılı**.
Geriye kalan soru ("göz görüyor mu") tam olarak otomasyonun karara bağlayamadığı sınıf.

**A-08 denetçisine verilecek iki ek talimat** (runbook'a eklenebilir):

> · **K-5 / A-3:** şu **ikili** soruyla koş — *"h1'den h3'e sıçrama sana bir bölümü
>   kaçırdığını düşündürdü mü, geri döndün mü?"* Evet/hayır. *"Fark ettim ama devam
>   ettim"* = **hayır**.
> · **K-6a:** odak halkasının **görünüp görünmediğini** rapor et. Precheck'in
>   `outline: none` çıktısı **kanıt değildir** (yukarıdaki ölçüm artefaktı).

Denetimin kendisi için prompt yazılamaz: yığın hazır (`scripts/a11y-audit-stack.sh`,
güncel main'de 9/9), runbook yazılı, defter boş. Eksik olan tek şey **NVDA/Firefox/
Windows ve VoiceOver/Safari/macOS önünde oturan bir insan**. `#514`'ün durumunu
bir agent değiştiremez.

---

## 7. Operasyonel notlar

**`doc-status` kapısı.** `scripts/generate_repository_facts.py::check_classification`
`docs/*KICKOFF*.md`'yi sınıflandırır ve **aynı anda yalnız BİR belge `current`
olabilir**. Bu belge `current` yapıldığı için `docs/ADIM47_LANDED_KICKOFF.md`
`historical`'a düşürüldü. Sıradaki kickoff'u yazan oturum **bu belgeyi de** düşürmek
zorundadır, yoksa kapı kırmızıya döner:
```
cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

**Ölçüm tuzakları (bu repoda gerçekten yaşandı).**
· Precheck sayısını TEK KOŞUYLA tazeleme — ilk koşu soğuktur ve **eksik** raporlar
  (K-5'i 18 gösterdi, doğrusu 21). En az iki kez koş, **ikinci** sayıyı al.
· `/analysis-lab`, `/backtest/history`, `/backtest/metrics` ısınmadan sonra da
  oynuyor → "21 / 23" = *"21, ±1, ve ±1'in hangi üç rotada yaşadığını biliyorsun."*
· vitest: `--no-file-parallelism` ZORUNLU; worktree'de `node_modules` yoksa önce `npm ci`.
· Görsel baseline üretim SIRASI: `down -v` → seed → `npm test` → `screenshots:update`.
· docs PR'ı öncesi: `git diff origin/main -- docs/ | grep '^-## '` → **BOŞ olmalı**.

**Taviz verilemez (her dört prompt için).** OCC token'ları (If-Match /
`expected_*_version` / `X-*-Version`), Idempotency-Key, route YOLLARI, react-query
key'leri, `ENGINE_VERSION` DEĞİŞMEZ. A-08 / `#514` durumunu bir agent DEĞİŞTİREMEZ.
Kapı kırılıyorsa yeşile zorlama yok — **BLOCKED yaz**.

## 8. Bu belgenin dürüst sınırları

1. **Stack koşulmadı.** K-2'nin *"0 baseline diff"* iddiası ve K-4'ün *"K-5'i 22 yapar"*
   türevi **kaynaktan çıkarıldı** (`UserManual.tsx:181` + `:259`), sondayla ölçülmedi.
   İlk uygulamada **ölçülmeli**.
2. **2.68 : 1 bu oturumda hesaplandı** (sRGB relative luminance, `#00a9e8` ↔ `#ffffff`).
   Repoda ölçülü değil, axe koşmuyor. Uygulayan oturum **yeniden hesaplasın**.
3. **Hiçbir karar verilmedi.** Dört promptun dördü de bir PO kararını *varsayar*;
   `<TARİH>` / `<AD>` alanları doldurulmadan imzalı kayıt yazılamaz.
4. **Bu belge blocker sayısını değiştirmez.** 1 (yalnız A-08), verdict **BLOCKED**.
