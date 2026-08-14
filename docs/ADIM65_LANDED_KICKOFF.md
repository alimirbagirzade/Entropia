<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 65 LANDED — adli denetim kaydı + #541'in iki blocker gerekçesi · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice ALTI kez taşındı: 54 → 58 → 60 → 62 → 63 → 64 → 65.** Dal ve
> commit mesajları `adim-54` yazar ve **değiştirilmedi**. **Merge edilmiş ad kazanır.**

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 65. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** Migration yok, `ENGINE_VERSION`
değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`. **Closes #541.**

**Bu slice DARALTILDI ve gerekçesi kayıtlı.** PR #700 otuz commit / 2256 satır taşıyordu;
güncel main'e karşı yeniden ölçüldüğünde içeriğinin büyük kısmının **#722 ve #720 ile zaten
indiği**, bir parçasının ise **regresif** hâle geldiği görüldü (`booking.py` — main'in
per-fill komisyon docstring'ini geri alırdı). Ölçüm önce, karar sonra.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `domain/backtest/capabilities.py` §scaling-timeframe yorumu | İki gerekçenin neden yanlış olduğu + gerekçenin neden `dependency`'de değil |
| `domain/strategy/config.py::CANONICAL_TIMEFRAMES` | `1m…1D`; merdivenin tepesi `1D` |
| `domain/backtest/indicators.py:544::_ReferenceSeries` | Resampled seri **var** |
| `docs/audit/final_closure_forensic_audit_2026-08-13.md` | 20 bölümlük adli ölçüm (`historical`) |
| `docs/audit/reopened_issue_reconciliation_2026-08-13.md` | 21 reopen edilmiş issue'nun koda karşı ölçümü |
| `domain/backtest/portfolio_engine.py` HONEST BOUNDARY §1 | (a) kapalı · **(b) kalan tek engel** · (c) kapalı |

## Pazarlıksız — bir sonraki oturum bunları bilmeden dokunmasın

1. **`dependency` metnini UZATMA.** `CapabilityNote.tsx:24` her `future_dev` seçeneğin
   `dependency`'sini tek paragrafta birleştirir ve bu grupta **on tane** vardır → uzun bir
   metin kullanıcıya **on kez tekrar** olarak sevk edilir. Gerekçe **kaynak yorumuna** yazılır.
2. **`capabilities.py`'ye dokunduysan TS aynasını yeniden üret**
   (`uv run python tools/export_capability_matrix.py`) — `test_capability_matrix.py`
   byte-parity'yi pinler ve unutulursa kırmızı verir.
3. **Denetim belgeleri ölçtükleri anı DONDURUR.** §7/§13'ün `#550`/`#551`/`#552` satırları
   *"HÂLÂ BOZUK"* der; bu `e2fa521`'de **doğruydu**, **#720 üçünü de sevk etti**. Banner
   bunu açıkça söyler ve satırlar **bilerek güncellenmedi** — bir denetim kaydını geriye
   dönük düzeltmek onu kayıt olmaktan çıkarır. Bugünkü davranış: §ADIM 61.
4. **`git diff origin/main <dal>` bir kapsam kararı için KANIT DEĞİLDİR.** Dalın gerisinde
   kaldığı her şeyi "silinmiş" gösterir; `merge-base`'e göre **iki tarafın da** ne
   değiştirdiğini ayrı say. Bu slice'ın dört "alınmayan" kararı böyle verildi.

## Sıradaki oturum için açık eksenler (hepsi insan kararı)

- **RC readiness raporunun blocker sayısı yükseltilmedi** — yükseltmek verdict'i değiştirir.
- Denetimin ölçtüğü **13 açık issue**'nun durumu değiştirilmedi; altısı ürün kararıdır.
- **Merdivenin tepesi canonical bir boşluk:** `CANONICAL_TIMEFRAMES` `1D`'de biter ve canon
  `1D` sonrasını söylemez — **clamp / durdur / reddet üç farklı üründür**.
- **`## Next:` DEĞİŞMEDİ:** PR B — `ItemParticipant` adaptörü +
  `jobs/backtest_engine.py:299` call site, **ADR §16 insan kapısının** arkasında. Kalan tek
  engel **(b)**: üç faz **book eder**, `ItemParticipant` **tarif** ister → `run_engine`'in
  bar gövdesine dokunur, yani bir **ADR amendment'ı** da gerekir.

## Paste-ready resume prompt

```
Entropia — ADIM 66 slice'ına başla.

Önce §Session START protokolünü uygula: git fetch, `git log --oneline origin/main -6`,
açık PR'ları listele; sonra sırayla `docs/ADIM65_LANDED_KICKOFF.md` (bu belge),
`docs/STAGE2_HANDOFF.md` (§Stage 65 landed + §Next), `docs/STAGE_BUILD_PLAN.md`,
ilgili `docs/spec/NN_*`. Handoff STALE-BY-DEFAULT'tur.

Durum: blocker 1 (yalnız A-08), verdict BLOCKED. alembic head
`0043_i08_registry_strategy_fks`. `ENGINE_VERSION` =
`backtest-engine-v18-percent-sizing-per-fill-commission` (#720).
Kabul borcu: A=1 · B=75 · C=6 · D=32, açık 114.

Denetim belgeleri `historical`'dır ve ölçtükleri anı dondurur — bir bulguyu
"hâlâ açık" diye okumadan önce `PROJECT_HISTORY.md`'nin ilgili §ADIM kaydına bak.

Sayısal otorite: `docs/generated/repository_facts.md` (collected) + bir CI koşusu.
```
