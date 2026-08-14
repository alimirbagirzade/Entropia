<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM63_LANDED_KICKOFF.md`'dir.**
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 62 LANDED — Ready Check'in son iki artık N+1'i batch'lendi · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice DÖRT KEZ taşındı: 57 → 58 → 59 → 60 → 62.** Dal
> `fix/closure-e2-ready-check-batching`; commit mesajları ADIM numarası **taşımaz**, o yüzden
> yeniden yazılmadı. Beklerken `#698` 57'yi, `#715` 58'i, `#718` 59'u, `#716` 60'ı ve `#723`
> 61'i **merge edilmiş adla** aldı. Kural değişmedi: **numaralar yeniden atanmaz, merge
> edilmiş ad kazanır**; taşınan taraf hep merge edilmemiş olandır.
>
> **Sebep yapısal:** `Backend` ~43–53 dk + ruleset `strict: true` + main'in ~30–60 dk'lık
> landing aralığı. **Auto-merge bunu kapatmaz** — yeşili fark etme gecikmesini kapatır,
> kapının main'in landing aralığından uzun olmasını kapatmaz.

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 62. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED** — bu slice A-08'i **ölçmedi**.
`ENGINE_VERSION` değişmedi, migration yok, `SHARED_ALLOCATION_STATUS` = `future_dev`.

ADIM 46 (#617) Ready Check'in market-data bacağındaki döngü-içi `get_dataset_root`'u
kapatmıştı. **Aynı şekil iki bacakta daha yaşıyordu** ve hiçbir issue onu izlemiyordu —
#700'ün adli denetimi bunu **M-13** olarak kaydetmişti. İkisi de artık **2 statement /
slope 0**; **davranış değişikliği yok** (aynı kodlar, severity, sıralama, `field_path`,
`scope_id`, `root_active`).

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `repositories/research_data.py::get_dataset_roots` | **YENİ** çoğul okuyucu; `market_data.py::get_dataset_roots`'un **alan-alan aynası** — yeni bir Root batch'i gerekirse bu ikisinden birini kopyala, üçüncü bir idiom **icat etme** |
| `repositories/market_data.py::get_dataset_roots` | Yeniden kullanıldı, **değiştirilmedi** |
| `commands/readiness_check.py::_resolve_signal_market_data_issues` | Batch'lenmiş signal bacağı |
| `commands/readiness_check.py::_resolve_research_sources` | Batch'lenmiş research bacağı |
| `query_budgets.json` → `readiness_check.signal_market_data_leg` · `.research_funding_leg` | İki yeni yüzey, ikisi de `per_item: 0` — **ratchet, tavanı yükseltme** |
| `tests/integration/test_batched_dereference_equivalence.py` | 11 yeni eşdeğerlik testi; #617'nin emsali ("bütçe round-trip'in düştüğünü kanıtlar, aynı şeyi SÖYLEDİĞİNİ kanıtlayamaz") |

## Pazarlıksız — bir sonraki oturum bunları bilmeden dokunmasın

1. **Root batch'i revision map'inden SONRA kurulur.** Bir Root ancak onu pinleyen revision
   üzerinden erişilebilir; sırayı ters çevirmek boş map verir.
2. **Filtre paritesi ölçüldü:** tekil `get_dataset_root` yalnız `entity_type`'a bakar
   (soft-delete filtresi **yok**); batch aynı yükümü **SQL'de** uygular. Batch'e ek bir
   yüküm koyarsan tekil okuyucunun `None`'ıyla ayrışır ve fail-closed dal sessizce kayar.
3. **Bütçe sayacının ÖLÇÜLMÜŞ kör noktası var.** Aynı session'da batch'in yüklediği bir PK
   için yeniden konan `session.get` **hiç SQL üretmez** → sayaç görmez. Bu bir kapı zaafıdır
   ve `query_budgets.json` `_comment`'inde beş ölçülmüş şekliyle **yazılıdır**. Bedeli olan
   her şekil yakalanır (per-item `select()` 13, yüklenmemiş id için okuma 11, batch'in
   kaldırılması 12). **Kokuyu kapıya bağlamak sayaçla değil kaynak-düzeyi assertion'la olur.**
4. **Negatif kontrolü pristine dosyayla koş.** İlk deneme sahte yeşil verdi (batch identity
   map'i ısıtıyor); gerçek negatif kontrol dosyanın değiştirilmemiş hâlini geri koymaktır.

## Sıradaki oturum için açık eksenler

- **Dört döngü-içi okuma bilerek ALINMADI** ve gerekçeleri §ADIM 62 md. 5'te tek tek yazılı:
  `_resolve_strategy_payload` (blast radius + kazanç sıfır), `_resolve_external`
  (`work_object_revision_id` **UNIQUE DEĞİL** → bugünkü kazanan **tanımsız**, önce ürün
  kararı), `find_approved_tick_revision_for_instrument` (`ORDER BY … LIMIT 1`, `DISTINCT ON`
  ister), `resolve_indicator_plan` (tek satır okuma değil). **Hiçbiri "yok" diye değil,
  "bu teknikle aynı değil" diye dışarıda.**
- Bacakların **kalan** maliyeti hâlâ O(n): `_build_item_inputs` her item için okur. Bu slice
  o ekseni **ölçtü ve bıraktı**.
- **`## Next:` DEĞİŞMEDİ:** PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:299`
  call site, hâlâ **ADR §16 insan kapısının** arkasında.

## Paste-ready resume prompt

```
Entropia — ADIM 63 slice'ına başla.

Önce §Session START protokolünü uygula: git fetch, `git log --oneline origin/main -6`,
açık PR'ları listele; sonra sırayla `docs/ADIM62_LANDED_KICKOFF.md` (bu belge),
`docs/STAGE2_HANDOFF.md` (§Stage 62 landed + §Next), `docs/STAGE_BUILD_PLAN.md`,
ilgili `docs/spec/NN_*`. Handoff STALE-BY-DEFAULT'tur — neyin gerçekten merge olduğunu
doğrulamadan hiçbir şey planlama.

Durum: blocker 1 (yalnız A-08), verdict BLOCKED. alembic head
`0043_i08_registry_strategy_fks`. `ENGINE_VERSION` =
`backtest-engine-v18-percent-sizing-per-fill-commission` (#720).

ADIM 62 Ready Check'in son iki artık N+1'ini kapattı (P-E2). Kod yazmadan önce
`docs/CODEMAPS/` haritasını oku ve `codebase-memory-mcp` ile sembolleri bul
(taze container'da önce `index_repository`, `list_projects` boş döner).

Sayısal otorite: `docs/generated/repository_facts.md` (collected) + bir CI koşusu
(passed + coverage). CLAUDE.md'ye sayı yazma.
```
