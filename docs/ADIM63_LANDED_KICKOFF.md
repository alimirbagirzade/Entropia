<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM64_LANDED_KICKOFF.md`'dir.**
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 63 LANDED — K-5'in sorusu düzeltildi (checklist A-3) · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice BEŞ kez taşındı: 58 → 59 → 60 → 61 → 62 → 63.** ADIM 58 olarak
> yazıldı; `#715` 58'i, `#718` 59'u, `#716` 60'ı, `#723` 61'i, `#712` 62'yi **merge edilmiş
> adla** aldı. Commit mesajları `adim-58` yazar ve **değiştirilmedi** — merge edilmiş git
> geçmişi yeniden yazılmaz.
>
> **Sebep yapısal:** `Backend` ~50 dk + ruleset `strict: true` + main'in ~30–60 dk'lık landing
> aralığı. **Auto-merge bunu kapatmaz.**

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 63. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. K-5 KAPANMADI.** ADIM 63 **kod yazmadı** —
`backend/src`, `frontend/src`, `alembic` ağaçlarına tek satır dokunulmadı.

Bu slice bir **bulguyu** değil, bulguyu kapatacak **aracı** düzeltti. Checklist **A-3**
*"`h1→h2→h3` sırası atlamasız"* diye soruyordu; `specs/20-a11y-prechecks.spec.ts` bunu zaten
her rotada sayıyor (`headingSkips`, `:95-96` / `:109-114` — **22 / 23**). İnsandan istenen,
sondanın çıktısını elle tekrarlamaktı → **denetim K-5'i kaç rota gezerse gezsin
kapatamazdı.** Yeni soru atlamanın **yanıltıp yanıltmadığını** istiyor.

RC §6.5'in durumu: **K-2 / K-4 kodla kapandı** (#685) · **K-6b kodla kapandı** (#688) ·
**K-3 beklenti düzeltilerek kapandı** (D-11, #698) · **K-5 + K-6a yalnız A-08 ile kapanır** —
K-5 artık *kapatılabilir* · **K-7 ölçüldü, düzeltilmedi**.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `a11y_screen_reader_audit_checklist.md` **A-3** satırı | Yeni beklenti. **Sayı sorma** — sonda sayıyor; **yanılma** sor |
| `a11y_screen_reader_audit_checklist.md` **§A-3 notu** | Neden değişti · neden `D-xx` değil · `—` hücresi neden kalıyor |
| `a11y_screen_reader_audit_results.md` §6 **K-5** | Altı CSS kuralı, v18 ölçümü, `/market-data` düzeltmesi |
| `a11y_ci_ratchet_and_adjudication.md` §4 | Sicil **iki kararda kaldı** (D-10 + D-11) |

## Pazarlıksız — bir sonraki oturum bunları bilmeden dokunmasın

1. **Gevşetme değil.** Precheck 22 / 23 saymaya devam eder; K-5 audit §6'da ve RC §6.5'te
   **Open**; hiçbir advisory susturulmadı.
2. **`D-xx` YAZILMADI ve yazılmamalı.** D-10/D-11 bir **gözlemin** dispozisyonunu imzalar;
   bu **aracı** düzeltir. Üçüncü bir satır *"K-5 adjudicated"* diye okunurdu.
3. **Rota 1'in `—` hücresi `—` kalır.** Eski cevap yeni soruya da cevap değil; defteri
   eşleştirerek doldurmak onu **sahte** doldurur.
4. **K-5 düzeltilecekse sıra bellidir:** önce **ALTI** tag-scoped CSS kuralını sınıf-tabanlı
   yap, sonra tag'i oynat. `.data-guide-card h4` (`global.css:2261`) her önceki listede
   **eksikti**; unutulursa başlık UA varsayılanına düşer ve **23 görsel baseline kırılır**.
5. **v18 itirazı burada geçerli DEĞİL.** Mockup `h1:0 h2:1 h3:0 h4:14 h5:0`; sevk edilen
   seviyeler oradan kopyalanmadı. v18 *görünümü* dikte eder, görünüm CSS'te yaşar.

## Sıradaki oturum için açık eksenler

- **`/market-data` ayrı bir kusurdur** ve açık bırakıldı: sayı boşluğu değil **yanlış
  yuvalama** (`h1 → h4×4 → h3×3`; rehber adımları DOM'da gerçek bölümlerden önce,
  `MarketData.tsx:272–325` vs `:497/:805/:942`). Tek sayfada birkaç satırda düzelir.
- **A-08 DEĞİŞMEDİ:** defter **2 / 184** hücre, **0 / 10** akış, **SR-1 hiç başlamadı**,
  çıkış kriterleri **0 / 4**, `#514` **açık**. Hiçbir belge A-08'i `Complete`/`PASS`
  gösteremez; **agent #514'ü ne açabilir ne kapatabilir** (`human-only`).
- **`## Next:` DEĞİŞMEDİ:** PR B — `ItemParticipant` adaptörü +
  `jobs/backtest_engine.py:299` call site, hâlâ **ADR §16 insan kapısının** arkasında.

## Paste-ready resume prompt

```
Entropia — ADIM 64 slice'ına başla.

Önce §Session START protokolünü uygula: git fetch, `git log --oneline origin/main -6`,
açık PR'ları listele; sonra sırayla `docs/ADIM63_LANDED_KICKOFF.md` (bu belge),
`docs/STAGE2_HANDOFF.md` (§Stage 63 landed + §Next), `docs/STAGE_BUILD_PLAN.md`,
ilgili `docs/spec/NN_*`. Handoff STALE-BY-DEFAULT'tur — neyin gerçekten merge
olduğunu doğrulamadan hiçbir şey planlama.

Durum: blocker 1 (yalnız A-08), verdict BLOCKED. alembic head
`0043_i08_registry_strategy_fks`. `ENGINE_VERSION` =
`backtest-engine-v18-percent-sizing-per-fill-commission` (#720).

ADIM 63 K-5'in SORUSUNU düzeltti (kod yok); K-5 hâlâ Open ve yalnız A-08 kapatır.
Kod yazmadan önce `docs/CODEMAPS/` haritasını oku ve `codebase-memory-mcp` ile
sembolleri bul (taze container'da önce `index_repository`).

Sayısal otorite: `docs/generated/repository_facts.md` (collected) + bir CI koşusu
(passed + coverage). CLAUDE.md'ye sayı yazma.
```
