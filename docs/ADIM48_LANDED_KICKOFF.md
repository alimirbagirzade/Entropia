<!-- doc-status: current -->
# ADIM 48 LANDED — K-6b: odak halkasının kontrastı (WCAG 1.4.11) · sıradaki slice için kickoff

> **Bu belge ADIM 48 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 48.

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

1. **Memory checkpoint borcu — İKİ slice birden.** `ecc` ve `claude-mem` MCP sunucuları
   ADIM 47'de de ADIM 48'de de **bağlı değildi** → kapanış ritüelinin 4. maddesi **üst üste
   iki oturumdur eksik**. Bağlı bir oturumda **ADIM 47 + ADIM 48** için birden yaz.
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

---

## Paste-ready resume prompt

```
ENTROPIA — sıradaki slice

CLAUDE.md §Session START protokolünü uygula: önce `git fetch` + `git log --oneline
origin/main -6` ile NEYİN GERÇEKTEN MERGE OLDUĞUNU doğrula (handoff STALE-BY-DEFAULT),
sonra docs/ADIM48_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md → docs/STAGE_BUILD_PLAN.md
sırasıyla oku. Sayısal otorite docs/generated/repository_facts.md.

DURUM: ADIM 48 landed — K-6b (odak halkası kontrastı, WCAG 1.4.11) KAPANDI:
frontend/src/styles/global.css `:focus-visible` halkası var(--accent) → var(--text).
Ölçülen: beyazda 15.91:1, en kötü zemin (#0092c8, .menu-blue:hover) 4.50:1 — hepsi ≥3:1.
Öncesi 2.68:1 / 2.46:1 idi. Presentation-only; --accent token'ına, dolgu/kenarlık/link
paletine, route/react-query key/OCC/Idempotency/hook/SSE/lib'e DOKUNULMADI.
Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.

İLK İŞ — İKİ BORÇ:
(1) MEMORY CHECKPOINT BORCU İKİ SLICE'TIR. ecc + claude-mem ADIM 47'de de 48'de de bağlı
    değildi. Bağlıysan ADIM 47 VE ADIM 48 için birden yaz; değilse bunu yine kaydet.
(2) ADIM 48'in PR'ında `e2e.yml::e2e` (görsel) ve `e2e.yml::a11y` (axe) job LOG'larını oku —
    bu iki kapı yerelde KOŞTURULAMADI (ortam Docker Hub blob CDN'ine 403 veriyor), otorite
    CI'dır. Görsel diff varsa TABANI GÜNCELLEME: kural odak dışına sızmıştır, selector'ı daralt.

KAPATILMADI, KAPATILDIĞI İDDİA EDİLMİYOR:
· K-6a (bir insan halkayı GÖREBİLİYOR mu) — AÇIK, yalnız A-08 kapatabilir.
· A-08 — defter 0/4, dört çıkış kriteri de ☐, #514 kanıtsız kapalı. Hiçbir belgeye
  Complete/PASS/Done yazma; "açık issue #514'te izleniyor" da yazma.
· D-10 — 45 accent-blue düğüm, 1.4.3 (METİN) ekseni. K-6b 1.4.11'di; AYRI ölçüt.
· RC §6.7: P11-1 (branch protection, İNSAN KARARI), P11-6b, P11-3b, P8-B3b, P4-3,
  P10-B6, P1-Gate3, P10-B3/B4/B5. · /library/{id}/validation-runs hâlâ 201.

Planlı ana eksen hâlâ: PR B — ItemParticipant adaptörü + jobs/backtest_engine.py:298
call site. ADIM 35 §4.1'in (c) engelini kapattı; (a) faz-bölünmüş bar ve (b) book-etmeyen
değerlendirme girişi run_engine'in gövdesine dokunur → ADR §16 İNSAN KAPISI + ADR
amendment'ı gerekir, o kapıdan geçmeden BAŞLAMA.

Kapanışta ritüelin altısı (CLAUDE.md §Session CLOSING). Verdiğin sayıları KABUL ETME,
yeniden ölç. Frontend doğrulama: cd frontend && npm run lint && npm run typecheck &&
npm test -- --no-file-parallelism (vitest'te --no-file-parallelism ZORUNLU).
```
