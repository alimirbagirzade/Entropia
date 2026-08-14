<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 64 LANDED — kabul borcu sınıf B, parti 04 (Backtest Result satır değişmezliği) · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice ÜÇ kez taşındı: 60 → 62 → 63 → 64.** `#716` 60'ı, `#723` 61'i,
> `#712` 62'yi, `#719` 63'ü **merge edilmiş adla** aldı. **Numaralar yeniden atanmaz, merge
> edilmiş ad kazanır**; taşınan taraf hep merge edilmemiş olandır.

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 64. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** Ürün kodu **DEĞİŞMEDİ** — tek yeni dosya
`backend/tests/integration/test_result_row_immutability.py`. Migration yok, `ENGINE_VERSION` /
OpenAPI / OCC / Idempotency / route / react-query key el değmedi.

**`partial` 111 → 106**, **`debt_class.B` 80 → 75**. Kapananlar: `RH-05` `RH-10` `RH-11`
`RH-12` `RH-16`. **P1-Gate3 KAPANMADI** — A=1 · B=75 · C=6 · D=32, açık **114**.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `test_result_row_immutability.py::_snapshot` | Kolonları anlık görüntüler |
| `…::_reread` | Komşu işlemden **sonra** satırı geri okur — modülün tüm değeri burada |
| `…::_checksums` / `::_manifest_snapshot` | Artifact hash'leri round-trip boyunca bit-bit |
| `…::_count_result_audits` | Audit satırını `target_entity_id` ile pinler |

## Pazarlıksız — bir sonraki parti bunları bilmeden dokunmasın

1. **İki olay adı sevk edilmemiş.** Doc 16 `RESULT_SOFT_DELETED` / `RESULT_RESTORED` der;
   sevk edilenler **`backtest.result_soft_deleted`** ve **`trash.restored`** (ikincisi generic
   trash restore yolunun yazdığı). **Sevk edilen ad kanoniktir** (O-02/O-31 emsali).
   Restore testi `target_entity_id`'yi pinler — yoksa **herhangi bir** trash etkinliğiyle geçerdi.
2. **`moved == {deletion_state, row_version}` kümesi TAM olmalı.** Gevşetmek testi bir
   "delete smoke test"ine indirir.
3. **Refüz testleri refüzden SONRA satırı geri okur.** Refüz iddianın yarısı; diğer yarısı
   hiçbir şeyin değişmemesi.
4. **`pytest.raises(Exception)` yazma** — `ruff` B017 yakalar; compare refüzü tipli
   (`CompareRequiresTwoDistinctResultsError`).
5. **RATCHET YALNIZ AŞAĞI İNER.** Rahatsız edici bir `partial`ı silerek tavan düşürmek yasak;
   `total_criteria` **383 sabit (TABAN)**. Bir kriteri B'den D'ye taşımak **D tavanını
   YÜKSELTİR** → bu bir adjudication'dır, test slice'ının kararı değil.

## Sıradaki oturum için açık eksenler — sonraki partinin ilk iki kalemi

- **`RH-13.c2`** — `_digest_from_rows` **sabit** `KEY_METRIC_KEYS` üzerinden filtreler, yani
  profil revizyonu digest'e ulaşamaz; kanıt metrik **registry**'sinin seed'lenmesini ister
  (aksi halde `MetricCodeUnknownError`).
- **`RH-14.c3`** — `create_analysis_artifact` capability-gated; kanıt registry'nin Limited'a
  yürütülmesini ister (`_walk_to_limited`), o helper bu modülün principal'larıyla çakışır.

**Yarım kanıtla işaretleme** (ADIM 54 `RD-09.c4` emsali). **Parti seçmeden ÖNCE ÖLÇ:**
kriterin adlandırdığı davranış `backend/src`'te sevk edilmemişse sınıfı yanlıştır.

**Defterde altı açık bulgu:** `TL-11.c3` · `TL-16` · `TL-01.c4` · `RD-01.c4` · `RD-05.c5` ·
`RD-11.c2`, artı **#703** (`revision.native_asset_id` üretimde **hiç yazılmıyor** → funding
-enabled backtest, uygulama içinde üretilmiş hiçbir research dataset ile çalışamaz).

**`## Next:` DEĞİŞMEDİ:** PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:299`
call site, hâlâ **ADR §16 insan kapısının** arkasında.

## Paste-ready resume prompt

```
Entropia — ADIM 65 slice'ına başla.

Önce §Session START protokolünü uygula: git fetch, `git log --oneline origin/main -6`,
açık PR'ları listele; sonra sırayla `docs/ADIM64_LANDED_KICKOFF.md` (bu belge),
`docs/STAGE2_HANDOFF.md` (§Stage 64 landed + §Next), `docs/STAGE_BUILD_PLAN.md`,
ilgili `docs/spec/NN_*`. Handoff STALE-BY-DEFAULT'tur.

Durum: blocker 1 (yalnız A-08), verdict BLOCKED. alembic head
`0043_i08_registry_strategy_fks`. `ENGINE_VERSION` =
`backtest-engine-v18-percent-sizing-per-fill-commission` (#720).
Kabul borcu: A=1 · B=75 · C=6 · D=32, açık 114.

Sıradaki parti hazır: RH-13.c2 + RH-14.c3 (ikisi de tesisat, davranışa şüphe değil).
PARTİ SEÇMEDEN ÖNCE ÖLÇ — kriterin adlandırdığı davranış sevk edilmemişse sınıfı yanlıştır.

Sayısal otorite: `docs/generated/repository_facts.md` (collected) + bir CI koşusu.
```
