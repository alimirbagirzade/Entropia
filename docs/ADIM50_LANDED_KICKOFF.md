<!-- doc-status: current -->
# ADIM 50 LANDED — K-6b: odak halkasının kontrastı (WCAG 1.4.11) · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice ADIM 48 olarak yazıldı, ADIM 50'ye taşındı.** Aynı gün üç
> slice paralel yürüdü ve üçü de kendini "ADIM 48" sandı: `#686` (kabul borcu sınıf B)
> **main'e ADIM 48 adıyla merge edildi ve o adı KORUR**; RC §6.5'in K-2 + K-4 slice'ı
> (PR #685) **ADIM 49** oldu; bu slice (K-6b, #688) **ADIM 50**'dir. Kural: **merge
> edilmiş ad kazanır**, taşınan taraf merge edilmemiş olandır. Commit mesajları
> yazıldıkları hâlde kalır (`adim-48`), belgelerin adı budur.
>
> **Bu belge ADIM 48'in kickoff'unun İÇİNDE yazılmıştı** (`ADIM48_LANDED_KICKOFF.md`)
> — merge iki slice'ın metnini üst üste yığmıştı: iki `doc-status` işareti, iki H1.
> Buraya ayrıldı; `ADIM48_LANDED_KICKOFF.md` yeniden **yalnız #686'nın** belgesidir.

> **Bu belge ADIM 50 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 50.


## Neredeyiz

Base `7dd1dfe` (#682, ADIM 47). Migration yok, `ENGINE_VERSION` değişmedi, OpenAPI
değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).
**Blocker sayısı DEĞİŞMEDİ — 1 (yalnız A-08). RC verdict BLOCKED.**

Bu slice **presentation-only** idi ve **tek bir CSS deklarasyonu** sevk etti.

## Bu slice ne bıraktı (reuse anchor'ları, tam sembol adlarıyla)

- **`frontend/src/styles/global.css` `:focus-visible`** — uygulamadaki odak halkasının
  **TEK** tanımı. `outline: 2px solid var(--accent)` → **`var(--text)`**. Kuralın üstündeki
  yorum artık ölçülmüş oranları ve zemin kümesini taşıyor; sayı arıyorsan oradan oku.
  **Yeni bir odak stili yazma** — bileşene özel bir halka eklemek yerine bu kuraldan geçir,
  yoksa kontrast tekrar ölçülmemiş bir yere kaçar.
- **`docs/audit/a11y_screen_reader_audit_results.md` §6** — **K-6 İKİYE ayrıldı:**
  - **`K-6b` KAPANDI (2026-08-12)** — ölçülü. Satır, değişiklikten *sonraki* yedi zemin
    oranını taşır.
  - **`K-6a` AÇIK** — *"bir insan halkayı görebiliyor mu"*. **Yalnız A-08 kapatabilir.**
    Sayım tablosundaki satır da `K-6a` olarak yeniden adlandırıldı (ölçen prob odur).
  - *"K-2 … K-7 bilerek kapı değildir"* paragrafı **K-6b'yi tek istisna** olarak tarif eder
    ve istisnanın nerede olduğunu söyler. Yeni bir K-N kapatmadan önce o paragrafı oku.
- **Ölçüm yöntemi** — sRGB linearizasyonu + `(L1+0.05)/(L2+0.05)`. Kickoff'un verdiği
  sayılar kabul edilmedi, **sıfırdan yeniden hesaplandı** ve birebir tuttu. Bir sonraki
  kontrast kalemi için de aynısını yap: **verilen sayıyı doğrulamadan kod yazma.**

## Ölçülen oranlar (halka `#222222`, değişiklikten sonra)

| Zemin | Nerede | Oran |
|---|---|---:|
| `#ffffff` | gövde, kartlar | 15.91 : 1 |
| `#f5f5f5` | | 14.59 : 1 |
| `#e8e8e8` | başlık çubuğu | 12.98 : 1 |
| `#00a9e8` | `.dropdown-blue` paneli | 5.94 : 1 |
| `#8f8f8f` | `.dropdown` paneli | 4.92 : 1 |
| `#8b8b8b` | `.run-button:disabled` | 4.67 : 1 |
| `#0092c8` | `.menu-blue:hover` — **en kötü zemin** | 4.50 : 1 |

Öncesi (`#00a9e8`): beyazda **2.68:1**, `#f5f5f5`'te **2.46:1**, `.dropdown-blue`
üzerinde **1.00:1**. Uygulamadaki **15 zeminin hiçbirinde** 3:1 geçilmiyordu.

## Bir sonraki oturumun ilk işi (borç)

1. **Memory checkpoint borcu — ÜÇ slice birden, İÇERİK HAZIR.**
   → **`docs/memory/PENDING_CHECKPOINTS.md`** (#690'da yazıldı; dosya ADIM 47 + 48 adını
   kullanır, numaralandırma uzlaştırmasından sonra kastettiği slice'lar **ADIM 47 + 49 + 50**'dir).
   İki ecc entity'si ve iki claude-mem observation'ı **tam metin** hâlde orada; yeniden
   türetme, yapıştır. Yazdıktan sonra o dosyayı **SİL** — kendini tüketen bir belgedir.
   **Neden iki oturumdur eksik olduğu ölçüldü ve sebep yapısal:** bu iş remote
   container'da yürüyor ve orada `ecc`/`claude-mem`/`codebase-memory-mcp` **kayıtlı
   değil** — `/root/.claude.json`'da bu projenin `mcpServers` listesi **boş**, repoda
   `.mcp.json` **yok**. Yani borç **bu ortamdan kapatılamaz**; yapılandırmanın bulunduğu
   bir **yerel** oturum ister. Aynı ortamda açılan her slice aynı şekilde kaçırır —
   kalıcı çözüm (sunucuları kaydetmek **veya** remote oturumları ritüelin 4. maddesinden
   resmen muaf tutmak) **insan kararıdır**.
2. **CI'ın söylediğini oku.** `npm run visual` ve `npm run a11y` bu oturumda
   koşturulamadı (ortam ağ politikası Docker Hub blob CDN'ini **403** ile reddediyor).
   PR'ın `e2e.yml::e2e` ve `e2e.yml::a11y` job'ları **otoritedir** — job log'undan
   gerçekten koştuğunu doğrula. **Görsel diff çıkarsa tabanı GÜNCELLEME:** kural odak
   dışına sızmış demektir, selector'ı daralt.

## Kapatılmayan, kapatıldığı iddia EDİLMEYEN

- **K-6a** — insan gözü ister. Ölçülebilir kontrast ≠ görülebilirlik.
- **A-08** — defter **0/4**, dört çıkış kriteri de ☐, #514 kanıtsız kapalı. Hiçbir belge
  `Complete`/`PASS`/`Done` göstermez, *"açık issue #514'te izleniyor"* da yazılmaz.
- **D-10** — 45 accent-blue metin düğümü, **1.4.3** ekseni, imzalı kalıcı sapma. Bu slice
  o ekseni **değiştirmedi**; `--accent` token'ına dokunulmadı.
- **RC §6.7 kalanları** — P11-1 (branch protection, **insan kararı**), P11-6b, P11-3b,
  P8-B3b, P4-3, P10-B6, P1-Gate3, P10-B3/B4/B5.
- **`POST /library/{id}/validation-runs` 201'de** — ADIM 47'nin açık bıraktığı ayrışma.
**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 48 bir blocker kalemi
değildi: ADIM 42'nin ürettiği borç defterini **işlemeye başladı**. Doc 05 (Trade Log)
backend yüzeyinden **sekiz sınıf-B kriteri** kapandı → **partial 126 → 118**,
**sınıf B 95 → 87**. **Ürün kodu değişmedi** (tek satır bile), migration yok,
`ENGINE_VERSION` sabit, OpenAPI değişmedi.

Kapanan sekiz: `TL-03` · `TL-06` · `TL-07` · `TL-08` · `TL-15` · `TL-17` · `TL-21` ·
`TL-23`.
