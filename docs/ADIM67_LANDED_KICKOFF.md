<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM68_LANDED_KICKOFF.md`'dir.**
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 67 LANDED — RD-11.c3: successor onayı run manifest'ini yeniden yazmaz · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 67. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Migration yok,
`ENGINE_VERSION` değişmedi, OpenAPI değişmedi, **ürün kodu değişmedi**.
Kabul borcu: `partial` **106 → 105**, `debt_class.B` **75 → 74** (ratchet aşağı indi).

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Sembol | Nerede | Ne için |
|---|---|---|
| `_ready_composition(..., funding_for=...)` | `test_backtest_persistence.py` | Funding'i AÇIK bir ready composition. Callback `(market_entity_id, market_revision_id)` alır — pin ancak market revision var olduktan sonra kurulabilir. |
| `_strategy_payload(..., funding=...)` | aynı dosya | Varsayılan `None` → `{"enabled": False}`, mevcut çağıranlar **bayt bayt aynı**. |
| `_approved_funding_revision` | `test_research_successor_manifest_immutability.py` | Readiness'in VE worker'ın kabul ettiği funding revision — beş kapının hepsi karşılanmış. |
| `_completed_funded_run` | aynı dosya | `_completed_run`'ın funding'li ikizi; `load_funding_rows` enjekte eder (S3 yok). |
| `_approve_successor` | aynı dosya | Aynı root altında ikinci revizyonu **sevk edilmiş komutlarla** yaratıp onaylar. |
| `_research_feed(manifest)` | aynı dosya | Manifest'in data/time grubundan **tek** research feed'i çeker, sayısını assert eder. |

## Pazarlıksız — bu slice'ın öğrendikleri

1. **"Saklanan satır değişmedi" TEK BAŞINA totolojidir.** Manifest admission'da yazılır,
   Result'a kopyalanır; hiçbir şey onu yeniden yazmaz. Kanıt değeri **okuma yolundadır**:
   `manifest_excerpt.research_data_revision_refs`. Yeni bir immutability testi yazarken
   saklanan satırı okumakla yetinme.
2. **Fundable research revision'ın BEŞ kapısı var, beşi de farklı yerden gelir** —
   `category_key=funding_rate` + native asset, `usage_scope` + APPROVED, pozitif delay'li
   `fixed_delay`, market link **eşitliği**, `instrument_mapping_ref` (link'le birlikte
   var/yok olmalı). Biri eksikse composition **admissible olmaz**, test zayıflamaz.
3. **Linki ELLE YAZMA** — `create_research_dataset` onu DR3 gereği kendi pinler; testin
   işi yalnız eşitliği assert etmek.
4. **Successor da DR3'e tabidir** — `market_entity_id` geçirmezsen onay `DependencyBlocked`
   ile düşer.
5. **Successor'ın gerçekten indiğini assert et** (yeni id + `approved` + root'un head'i),
   yoksa test "olmayan bir onaydan sonra hiçbir şey değişmedi" der ve vacuous geçer.
6. **Kriterin son clause'u kapanınca `debt_class` KALDIRILIR** — scanner kapalı bir
   kriterin sınıf taşımasını reddeder, ve İKİ tavan birden iner.

## Sıradaki tasarım işaretleri

- **Kabul borcu:** `A=1 · B=74 · C=6 · D=32`, `partial` 105 / `uncovered` 8 → açık **113**.
  Sınıf B partileri sayfa-belgesi + yüzey başına dar tutulur (batch 01 = doc 05 backend).
- **Sınıf D kalemleri test slice'ıyla kapanmaz** — `alignment_policy_versions[]`,
  `missing_and_stale_policies[]`, `TL-16`, `AT-04`, `AT-17`, `CP-16`, `PC-15`, `AM-13`,
  `AM-15` ürün boşluğudur.
- **Karar 1 (#552) ve Karar 3 (#559) imzasız** — komisyon tabanı ve DST açık.
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce harness'ın VAR OLUP OLMADIĞINI ölç.** `grep -l FundingPolicy tests/ | xargs grep -l run_backtest`
  sıfır döndü — clause'un dört partidir açık kalmasının sebebi buydu, tembellik değil.
- **Sembol adlarını doğrula, varsayma.** `bt_repo.get_run_manifest` ve
  `get_result_detail` **yok**; doğruları `get_manifest_by_run` ve `get_backtest_result`.
- **Negatif kontrolü İKİ eksende koştur** — biri saklanan satırı, biri okuma yolunu
  bozmalı; ikisi farklı assertion'ı kırmızıya çevirmeli.
- **Postgres bu container'da apt ile kurulu değil ama binary var**
  (`/usr/lib/postgresql/16`); `su postgres -s /bin/bash -c "…pg_ctl … start"`.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, sıradaki parti
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ORTAK SÖZLEŞME bloğunu buraya yapıştır]

TABAN
  Beklenen: ADIM 67'nin merge edildiği main. FARKLIYSA durma, farkı raporla,
  aşağıdaki her ölçümü yeniden yap.

ÖN KOŞUL — PARTİ SEÇMEDEN ÖNCE ÖLÇ (ADIM 52/54'ün dersi)
  docs/audit/acceptance_coverage_debt_ledger.md içinden sınıf B kriterlerini oku.
  SEÇMEDEN ÖNCE: kriterin adlandırdığı davranış backend/src'te SEVK EDİLMİŞ mi?
  Edilmemişse sınıfı YANLIŞTIR (D'dir) — o partiye girme, bulguyu KAYDET.
  Bir partiyi tek sayfa belgesi + tek yüzeyle sınırla.

YAPILACAK
  Seçtiğin her clause için: davranışı adlandıran testi yaz, NEGATİF KONTROLDEN geçir
  (davranışı kaldır -> test kırmızı olmalı). "İşaretlemek != kapsamak".
  Saklanan bir satırın değişmezliğini kanıtlıyorsan OKUMA YOLUNU da assert et —
  saklanan satırı okumak tek başına totolojiye yakındır (ADIM 67).

KABUL BORCU RATCHET'İ
  Kapattığın her clause icin acceptance_semantic_map.yaml'i güncelle, sonra:
    python3 docs/audit/acceptance_semantic_scan.py --root . --ratchet docs/audit/acceptance_coverage_baseline.json
  Bir kriterin SON clause'u kapanıyorsa kriteri covered yap ve debt_class'ini KALDIR.
  Tavanları ölçülen değere İNDİR. RATCHET YALNIZ AŞAĞI İNER.
  total_criteria = 383 TABANDIR. Bir kriteri B'den D'ye taşımak D TAVANINI YÜKSELTİR
  -> bu bir adjudication'dir, test slice'inin karari degil.
  Sonra ledger'i yeniden uret (--write-ledger) ve repository_facts'i TAZELE.

DOKUNMA
  sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py
  jobs/research_data.py::_pin_member / ::_seal_bundle

TEST
  cd backend
  uv run pytest -q --no-cov <hedef dosyalar>
  Sonra tam suite + ruff + mypy + openapi --check + repository_facts --check.
  ALT KÜME KOŞARKEN --no-cov EKLE. `pytest | tail` KULLANMA (exit code tail'in olur).

COMMIT / PR
  DAL: test/closure-acceptance-batch-<n>
  commit: test(closure-acceptance): <kapatilan clause'lar>
  MERGE ETME. Kapanış ritüeli 6 madde.

FINAL RESPONSE — [ORTAK ŞABLON] + "kapanan clause'lar + inen tavanlar"
DUR.
```
