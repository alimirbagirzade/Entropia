<!-- doc-status: current -->
# YAZILMAMIŞ MEMORY CHECKPOINT'LERİ — ADIM 47 + ADIM 48

> **Bu belge kendini tüketir.** İçindeki iki checkpoint `ecc` ve `claude-mem`'e
> yazıldığında **bu dosya SİLİNİR**. Silinmemişse borç hâlâ duruyor demektir.

## Neden var — ve neden "bir dahaki sefere" demek yetmedi

CLAUDE.md §Session CLOSING ritüelinin **4. maddesi** her kapanışta `ecc` knowledge
graph'ına bir entity ve `claude-mem`'e bir checkpoint yazılmasını ister. **ADIM 47 ve
ADIM 48 kapanışlarının ikisinde de yazılamadı.** Her iki oturumun kaydı da *"bir sonraki
oturumda yazılmalı"* dedi; ikincisi geldiğinde koşul değişmemişti, çünkü sorun oturuma
özel değil **ortama yapısaldır**:

**Bu iş Claude Code on the web (remote container) üzerinde yürüyor ve o ortamda `ecc` /
`claude-mem` / `codebase-memory-mcp` MCP sunucuları KAYITLI DEĞİL.** 2026-08-12'de ölçüldü:

- `/root/.claude.json` → `projects./home/user/Entropia.mcpServers` = **`[]`** (boş).
- Repoda `.mcp.json` **yok**.
- Araç aramasında `ecc` **hiç eşleşme vermiyor**, `mem` yalnız alakasız bir GitHub
  aracına düşüyor.
- Bağlı olanlar: `github`, `Figma`, `Google_Drive`, `Claude_Code_Remote`
  (+ yetkilendirilmemiş `Gmail`, `Notion`). **Hiçbiri knowledge graph değil.**

Sonuç: **bu borç remote oturumdan kapatılamaz.** Bu sunucuların yapılandırıldığı bir
**yerel** oturum ister. Aynı ortamda açılan ADIM 49 da aynı şekilde başarısız olur —
o yüzden aşağıdaki içerik **hazır** bırakıldı: yeniden türetmek değil, yapıştırmak yeterli.

---

## 1. ecc knowledge graph

İki entity + ilişkiler. Adlandırma ritüelin istediği biçimde
(`Entropia Stage <x> — <title>`).

### Entity A

- **name:** `Entropia Stage ADIM 47 — RC §6.7'nin iki PO kararı`
- **entityType:** `slice`
- **observations:**
  - PR #682, `main` üzerinde `7dd1dfe` olarak merge edildi (2026-08-12).
  - Migration yok; `ENGINE_VERSION` değişmedi; OCC / Idempotency / route yolları /
    react-query key'leri değişmedi.
  - **OpenAPI bilerek değişti:** iki operation `200 → 202`, iki component eklendi;
    path/operation **sayısı** aynı kaldı.
  - (A) §6.7.9 / P8-B2: `POST /create-package/requests/{id}/validate` ve
    `../baseline-parse` **200 → 202**. Otorite **PO kararıdır (2026-08-12)**, kanonik
    bu iki uç için hâlâ status vermiyor.
  - Yeni tipli gövdeler: `apps/api/routes/create_package.py::ValidationRunAcceptedResponse`
    ve `::BaselineParseAcceptedResponse` (8'er alan). Yeni admission ucunun şablonu budur;
    `dict[str, Any]` dönüşü sözleşmeyi şemadan gizler (O-30).
  - İki komut kod yazılmadan **yeniden ölçüldü**: ikisi de `enqueue_job`'a ulaşıp iş
    bitmeden dönüyor → 202 doğru. Senkron çıksalardı slice duracaktı.
  - (B) §6.7.5 / P10-B2: 9 kelepçeli `limit` **200 KALIR**, 422'ye çevrilmez (PO kararı).
    **Kod davranışı değişmedi**; kapanan şey gerekçenin yazılı olmamasıydı.
    19 ENFORCING / 9 CLAMPING ayrımı bilinçlidir.
  - `tests/contract/test_p8b2_admission_status.py::_EXPECTED` 13 admission ucunu
    sınıflandırır; küme `enqueue_job` transitive closure'ından **türetilir**, elle
    yazılmaz. Etiketler ayrıdır: `ALIGNED` (kanonik kodu adlandırdı) ≠ `PO <tarih>`
    (kanonik sessiz, insan seçti). **Birleştirme** — birleştiren okuyucu kararı atıf sanar.
  - `apps/api/pagination.py::clamped_limit_query` kelepçeli `limit`'in TEK declarator'ı.
  - **KAPANMADI:** `POST /library/{id}/validation-runs` **201'de kaldı** — PO kararı onu
    kapsamadı; aynı validation run'ı saran iki uç hâlâ iki farklı status döndürüyor.
  - Kickoff'un *"§6.7'nin on iki kalemi kapanır"* iddiası **yanlıştı ve sayıldı**: alt
    bölümlerde 12'de 11 kapalı (§6.7.10 / P1-Gate3 açık), tabloda **24 satırda 10 AÇIK**.
  - Blocker sayısı **değişmedi (1 — yalnız A-08)**, verdict **BLOCKED**.
  - Dürüst sınır: tam suite yerelde koşmadı (container'da Postgres yok); otorite CI.
- **relations:** `unblocks` → `Entropia Stage ADIM 48 — K-6b odak halkası kontrastı`

### Entity B

- **name:** `Entropia Stage ADIM 48 — K-6b odak halkası kontrastı (WCAG 1.4.11)`
- **entityType:** `slice`
- **observations:**
  - PR #688, `main` üzerinde `04c6a9c` olarak merge edildi (2026-08-12). Base `7dd1dfe`,
    araya kullanıcının `main` merge'ü girdi (`b45f342`).
  - **Ürün değişikliği TEK deklarasyondur:** `frontend/src/styles/global.css`
    `:focus-visible` → `outline: 2px solid var(--text)` (eski `var(--accent)`).
  - Migration yok, `ENGINE_VERSION` değişmedi, OpenAPI değişmedi; route/react-query
    key/OCC/Idempotency/hook/SSE/`lib`/`app/nav.ts` hiç dokunulmadı.
  - **Neden:** `--accent` (`#00a9e8`) odak halkası olarak uygulamadaki **15 zeminin
    hiçbirinde** WCAG 1.4.11'in istediği 3:1'i geçmiyordu — beyaz **2.68:1**, `#f5f5f5`
    **2.46:1**, `.dropdown-blue` üzerinde **1.00:1** (görünmez).
  - Sayılar kabul edilmedi, sRGB linearizasyonu + `(L1+0.05)/(L2+0.05)` ile **sıfırdan
    yeniden hesaplandı** ve birebir tuttu.
  - `var(--text)` (`#222222`) ile ölçülen: beyaz **15.91:1**, `#f5f5f5` 14.59:1,
    `#e8e8e8` başlık çubuğu 12.98:1, `#00a9e8` panel 5.94:1, `#8f8f8f` panel 4.92:1,
    `#8b8b8b` 4.67:1, ve **en kötü zemin `#0092c8` (`.menu-blue:hover`) 4.50:1**.
  - `.ready-status` zeminleri (`#b60000`/`#00a651`/`#d98c00`) hesaba **girmez**: o şerit
    odaklanabilir değil ve `outline-offset: 2px` halkayı **ebeveynin** zeminine basar.
  - **axe bu kuralı KOŞMUYOR** — `color-contrast` metin içindir. a11y/Lighthouse/görsel
    kapıların yeşil olması bu soru için **kanıt değildi**. Repoda başka hiçbir yerde
    ölçülü değildi.
  - **Bu D-10 DEĞİL:** D-10 = **1.4.3** (metin) ekseninde imzalı kalıcı sapma; K-6b =
    **1.4.11** (metin-dışı). Ayrı ölçüt, ayrı eşik; `--accent` token'ına dokunulmadı.
  - **v18 sapması DEĞİL:** mockup **hiçbir odak durumu tarif etmiyor** — tarif edilmeyen
    bir şeyden sapılamaz. Palet/dolgu/kenarlık değişimi sapma **olurdu**.
  - Defterde **K-6 İKİYE ayrıldı**: `K-6b` **KAPANDI** (ölçülü),
    `K-6a` (*"bir insan halkayı görebiliyor mu"*) **AÇIK — yalnız A-08 kapatabilir**.
    RC raporu §6.5 ve sayım tablosu da aynı şekilde bölündü.
  - Doğrulama: frontend lint/typecheck/build exit 0, **721 passed / 70 dosya** (taban
    birebir aynı, hiçbir test yeniden hizalanmadı); documentation-truth gate yeşil.
  - **Görsel kapı İKİ farklı tabanda geçti:** `aa1baf5`'te 23 passed (4.0m),
    `b45f342`'de 23 passed (3.9m) — **23/23 rota, 0 diff**, `--update-snapshots` yok.
    CI'da nihai durum **22/22**.
  - `pages/RationaleFamilies.tsx:368` inline `outline: var(--accent)` bilerek bırakıldı:
    o bir **seçim** göstergesi, odak halkası değil.
  - Blocker sayısı **değişmedi (1 — yalnız A-08)**, verdict **BLOCKED**.
  - Dürüst sınır: `npm run visual` / `npm run a11y` **yerelde koşturulamadı** — ortamın ağ
    politikası `production.cloudfront.docker.com`'a CONNECT'i 403 reddediyor,
    `registry-1.docker.io` 429 veriyor; docker daemon açıldı ama imaj çekilemedi.
- **relations:** `unblocks` → `Entropia Stage ADIM 49` (henüz adlandırılmadı)

---

## 2. claude-mem

İki checkpoint observation (`mem-search` ile aranabilir olmalı):

> **ADIM 47 (PR #682, `7dd1dfe`)** — RC §6.7'nin iki PO kararı uygulandı.
> `../validate` + `../baseline-parse` 200 → 202 (otorite PO kararı, kanonik sessiz;
> tipli gövdeler `ValidationRunAcceptedResponse` / `BaselineParseAcceptedResponse`).
> 9 kelepçeli `limit` 200 kalır — kod değişmedi, yazılmayan gerekçe kapandı.
> `/library/{id}/validation-runs` **201'de kaldı**, ayrışma açık. §6.7 bitmedi:
> tabloda 24 satırda 10 açık. Blocker 1 (A-08), BLOCKED.

> **ADIM 48 (PR #688, `04c6a9c`)** — K-6b: `:focus-visible` halkası `var(--accent)` →
> `var(--text)`. Eski hâli hiçbir zeminde 3:1'i geçmiyordu (beyaz 2.68:1, dropdown-blue
> 1.00:1); yenisi her zeminde geçiyor (beyaz 15.91:1, en kötü `#0092c8` 4.50:1).
> **axe bu kuralı koşmaz** — yeşil ratchet kanıt değildi. 1.4.11'dir, D-10'un 1.4.3'ü
> DEĞİL; mockup odak durumu tarif etmediği için v18 sapması da değil. K-6 ikiye ayrıldı:
> K-6b kapandı, **K-6a açık (yalnız A-08)**. Görsel kapı iki tabanda 23/23, 0 diff.
> Blocker 1 (A-08), BLOCKED.

---

## Yazdıktan sonra

1. İki entity + iki claude-mem observation'ı yaz.
2. **Bu dosyayı sil** (`git rm docs/memory/PENDING_CHECKPOINTS.md`).
3. `docs/ADIM48_LANDED_KICKOFF.md`'deki *"memory checkpoint borcu"* maddesini ve
   `CLAUDE.md` §Current position'daki *"Memory checkpoint yine YAZILAMADI"* cümlesini
   kaldır.
4. **Kalıcı çözüm — insan kararı:** bu borcun tekrar birikmemesi için ya `ecc` /
   `claude-mem` remote ortama kaydedilmeli (repoda `.mcp.json`), ya da ritüelin 4. maddesi
   remote oturumlar için resmen muaf sayılmalı. **İkisi de agent işi değildir.**
   Üçüncü bir seçenek yok: şu anki hâliyle her remote kapanış bu maddeyi kaçırır.
