# O-16 landed → sonraki oturum kickoff

**Bu slice:** User Manual arama sonucu için bayat (stale) anchor kurtarma — doc 21 §7 / §14,
acceptance UM-18. PR **#444**, branch `feat/o16-manual-stale-anchor-recovery`. Sadece frontend;
migration yok, backend'e dokunulmadı.

> Tam anlatı **`docs/PROJECT_HISTORY.md` § "O-16 · User Manual — bayat arama anchor'ı için kurtarma
> yolu (PR #444)"**. Aşağısı yalnızca bir sonraki oturumun ihtiyaç duyacağı çapa ve yöntem.

---

## Nerede duruyoruz

Doc 21 §7'nin arama-sonucu satırı artık üç maddesiyle de karşılanıyor: anchor current stream'de
doğrulanıyor, bayatsa stream refetch edilip tekrar deneniyor, bulunamazsa §7'nin **verbatim** metni
gösteriliyor. Öncesinde üçü de yoktu (`grep "no longer available" frontend/src` = 0 hit).

---

## Bu slice'ın bıraktığı REUSE çapaları (kesin sembol adlarıyla)

Hepsi `frontend/src/pages/UserManual.tsx` içinde, modül düzeyinde:

| Sembol | Ne işe yarar | Yeniden kullanım |
|---|---|---|
| `ANCHOR_UNAVAILABLE_MESSAGE` | Doc 21 §7 metni, verbatim sabit | Başka bir yüzey aynı mesajı gösterecekse **bu sabiti import et**, yeniden yazma |
| `scrollToAnchor(element)` | `scrollIntoView?.({behavior:"smooth", block:"start"})` | Fragment hedefine götüren her yeni yüzey |
| `waitForAnchorElement(anchor)` | Sınırlı poll (`ANCHOR_RETRY_ATTEMPTS=10` × `ANCHOR_RETRY_POLL_MS=16`) | "Veri geldi ama DOM henüz yok" olan her retry |
| `ManualSearchNav` prop `onRefetchStream` | Çocuğun parent'ın query'sini tazelemesi | Aynı kalıp: **refetch ver, reset verme** |

Testte: `stubScrollIntoView()` (hedefi de kaydeder), `streamGetCount(fetchMock)`,
`searchPageFor(chunkId, title, anchor)`, `LATE_SECTION` / `STREAM_WITH_LATE_SECTION` —
`frontend/src/test/userManual.test.tsx`.

**Kritik davranış notu:** parent `stream.refetch()` veriyor, `resetToFirstPage()` **vermiyor**.
Sayfa `accumulate-on-load-more` çalıştığı için reset biriken kuyruğu düşürür ve kurtarmaya çalıştığı
anchor'ı silebilir. Bu kalıbı kopyalarken aynen koru.

---

## Bu slice'ın bilerek bıraktığı açık uçlar

1. **Yüklenmemiş sayfa.** Anchor hâlâ getirilmemiş bir "Load more" sayfasındaysa mesaj yanlış
   tarafa düşer (bölüm aslında var, sadece render edilmemiş). Çözüm bir okuma yüzeyi ister:
   sunucudan anchor → `stream_position`/cursor çözümü, sonra hedefli sayfa getirme. **Doc 21 §12'de
   `GET /manual/section` route'lu DEĞİL** (Agent onu Tool Gateway'den okuyor) — yani bu iş yeni bir
   endpoint tasarımı demektir, presentation slice'ı değildir. Yapılacaksa ayrı slice.
2. **Kenar çubuğu bölüm listesi** (`UserManual.tsx:118`) çıplak `<a href>` — bilerek. Aynı
   snapshot'tan türüyor, bayatlayamaz. Buraya kurtarma eklemek olmayan bir kusuru kovalamak olur.
3. **E2E yok.** Kurtarma tamamen istemci tarafı; gerçek tarayıcı ek davranış kanıtlamıyor.

---

## İşe yarayan çalışma yöntemi (tekrarla)

1. **Önce ampirik doğrulama, sonra kod.** Spec satır numarasını (`grep -n` doc 21) ve kusurun
   kendisini (`grep -rn "no longer available" frontend/src` = 0 hit) yaz. Denetim bulgusunun doğru
   olduğunu varsayma — bu seferki doğruydu, ama kanıt ucuzdu.
2. **Verbatim metni sabite pinle** ve yorumda "never reworded" de. Spec metni yeniden yazılırsa
   acceptance sessizce kaybolur.
3. **Test hedefi assert et, olayı değil.** `scrollIntoView` çağrıldı mı değil, **hangi elemente**
   çağrıldı. jsdom'da bu fonksiyon yok — `this`'i kaydeden bir double kur, `afterEach` prototipten
   sil.
4. **`--no-file-parallelism` ZORUNLU** (frontend suite'i bu bayrak olmadan sahte hata verir).
   Bu worktree'de `frontend/node_modules` yoktu → `npm ci`; ilk vitest çağrısındaki
   `ERR_MODULE_NOT_FOUND` bir test hatası değil kurulum eksiğiydi.
5. **GateGuard:** mevcut dosyaya EDIT → 4 fact sun (importers / etkilenen public API / veri şeması /
   kullanıcı isteği verbatim), **sonra aynı çağrıyı tekrarla**. Fact'ları aynı mesajda göndermek
   yetmiyor; gate bir tur reddediyor.

---

## Paste-ready resume prompt

```
Entropia — sıradaki iş. Session START protokolünü uygula (git fetch; git log --oneline origin/main -6;
gh pr list --state all) ve şu sırayla oku: docs/O16_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md
("O-16 … landed" + "Next") → CLAUDE.md §Current position. Slice ayrıntısı gerekirse
docs/PROJECT_HISTORY.md'den HEDEFLİ oku.

Son landed: O-16 (PR #444) — User Manual arama sonucu için stale anchor kurtarma (doc 21 §7/§14,
UM-18). Frontend-only, migration yok. Çapalar: UserManual.tsx içinde ANCHOR_UNAVAILABLE_MESSAGE /
scrollToAnchor / waitForAnchorElement, ManualSearchNav prop onRefetchStream; testte
stubScrollIntoView / searchPageFor / STREAM_WITH_LATE_SECTION.

Açık iş (CLAUDE.md §Next):
1. F-07 §4.4 — 4 yüzey backend display-DTO bekliyor (docs/implementation/v18_visual_traceability.md §4.4).
2. R2 banner kapanışı (docs işi) — entropia_v18_remediation_status.md RE-OPENING banner'ı.
3. O-03 kalıntısı — 5 ölü error sınıfı (KNOWN_UNRAISED).
4. Round-3 backlog — S5 (a/b/c/d) + S-L1…S-L6 (docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md §DURUM TAZELEME).

Kurallar: her CRITICAL/HIGH bulguyu ampirik doğrula (çoğu yanlış çıkıyor); UI işi presentation-only
(route path / react-query key / OCC token / Idempotency-Key / lib/*.ts veri mantığı / app/nav.ts
DEĞİŞMEZ); frontend testi `cd frontend && npx vitest run --no-file-parallelism` (node_modules yoksa
önce `npm ci`); branch feat/<slug>, kapanış docs/<slug>-landed, commit'te AI attribution YOK.
```
