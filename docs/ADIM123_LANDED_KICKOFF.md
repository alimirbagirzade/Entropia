<!-- doc-status: current -->

# ADIM 123 landed — `G14` Karar 2 (`B3`) + Karar 4 (`B0`) imzalandı, `B0` uygulandı

**Taban:** ADIM 122 (`98498d99`). **Migration YOK** · `ENGINE_VERSION` değişmedi · OpenAPI
değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (el değmedi) · golden digest'ler el
değmedi · blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.

## Bu slice ne yaptı

İki imza kutusu doldu (`alimirbagirzade`, 2026-08-27):

- **§Karar 2 = `B3`** — `B` sevk edildiğinde `'NET'` satırı varsa migration **DURSUN**.
- **§Karar 4 = `B0`** (yeni bölüm) — yazma yolu **şimdi** dondurulur.

Ve `B0` **uygulandı**. `B`'nin migration'ı **YAZILMADI** — sıra kısıdı imzanın parçası:
ikisi aynı sürümde çıkarsa `B0`'ın drenaj penceresi hiç oluşmaz.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Çapa | Nerede | Ne yapar |
|---|---|---|
| `CrossItemConflictPolicyNotSelectableError` | `shared/errors.py` | O-02 zarfı; `code=CROSS_ITEM_CONFLICT_POLICY_NOT_SELECTABLE`, `field_path="conflict_policy"`, `suggested_action`, `remediation` |
| NET token reddi | `commands/allocation_plan.py::upsert_allocation_draft` | **asıl freeze**; `_parse_config`'ten sonra, `_op`/`run_idempotent`'ten ÖNCE |
| `Sev.BLOCKER` | `domain/allocation/rules.py` (NET dalı) | drenaj **sinyali**: saklanan NET plan `NOT_READY` okunur |
| `CONFLICT_POLICIES` | `frontend/src/lib/allocation.ts` | iki üye (`NET` düştü) |
| `CONFLICT_POLICY_LABELS` | aynı dosya | **bilerek daha geniş** — saklanan NET hâlâ render edilir |
| disabled option | `frontend/src/pages/Portfolio.tsx` (`<select>` içinde) | saklanan-ama-seçilemez değeri dürüstçe gösterir; sunucu-güdümlü |
| `test_b0_freezes_the_net_write_path` | `tests/integration/test_allocation_persistence.py` | satırı **geri okur**, **rollback yapmaz**, pozitif kontrollü |
| `test_a_stored_net_plan_still_reads_back_verbatim` | aynı dosya | yerleşim tuzağının muhafızı (`_plan_to_config`) |
| `test_net_policy_is_a_blocker_and_keeps_its_signed_message` | `tests/unit/test_allocation_rules.py` | severity **ve** Karar 3'ün imzalı metni, iki ayrı eksen |
| iki vitest case'i | `frontend/src/test/portfolio.test.tsx` | `describe("Portfolio — the NET conflict policy notice")` altında |

## Sıradaki kalem — `B`'nin migration'ı (`C9` ÖNCESİ, bu sürümde DEĞİL)

Ön koşul: `B0` **üretime çıkmış** ve operatör kümeyi drene etmiş olmalı. Sonra:

1. alembic revision — `portfolio_allocation_plan.conflict_policy` CHECK'ini yeniden yaz
   (`enum_column(CrossItemConflictPolicy, "allocation_conflict_policy")`, `native_enum=False`).
2. **`B3`:** migration `SELECT count(*) ... WHERE conflict_policy = 'NET'` > 0 ise **DURSUN**
   (satırları yeniden yazma, `NULL`'a çevirme — ikisi de imzada reddedildi).
3. `CrossItemConflictPolicy.NET` enum üyesini düşür → `arbitration.py:269` kuralı,
   `engine.py::conflict_downgraded_from_net`, `execution/state.py`, `output.py` temizlenir;
   `rules.py::_net_policy_warning` + `_NET_POLICY_BODY` **ölü koda** döner.
4. `AllocationIssueCode.CONFLICT_POLICY_NET_V1` + `CONFLICT_POLICY_LABELS.NET` +
   `Portfolio.tsx`'in disabled-option bloğu kaldırılır (**bu slice'ın çapaları**).
5. `up/down/up` + L1 FK insert-order proof (CLAUDE.md §Local verify) **ZORUNLU**.
6. `#544` **ancak o zaman** kapatılır; ön koşul 20 **ancak o zaman** yeşile döner.

## Yapılmayanlar (bilerek)

- **`B`'nin migration'ı** — sıra kısıdı (yukarıda).
- **`#544` / `#559`** — `human-only`, dokunulmadı.
- **ADR-0002 amendment'i** — o `A` yolunun işi, imzalanan `B` değil.
- **`closure_w0_containment_lift_preconditions_2026-08-17.md` satır 20** — *"#544 kapalı →
  ❌ AÇIK"* hâlâ **doğru**; uydurma güncelleme yapılmadı.
- **`final_closure_delta_audit_2026-08-25.md`** — denetim, ölçtüğü anı dondurur (ADIM 65).
- **Üretim `'NET'` satır sayısı** — erişim yok, **ikame edilmedi**; `B0` onu gereksiz kılar.
- **`SHARED_ALLOCATION_STATUS`, `ENGINE_VERSION`, golden digest'ler** — el değmedi.

## Paste-ready resume prompt

```
ENTROPIA — B0 sevk edildi; sıradaki kalem `B`'nin migration'ı (G14, C9 öncesi)

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state open
  docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md §Karar 2 = B3 ve §Karar 4 =
  B0 İMZALI (2026-08-27). B0 ADIM 123'te sevk edildi. §Karar 1 = "C şimdi + B (KALDIR) C9
  öncesi".

ÖN KOŞUL — ÖLÇ, VARSAYMA: B0 üretime çıktı mı? Çıkmadıysa DUR (sıra kısıdı imzanın
  parçası: B0 ile migration aynı sürümde çıkarsa drenaj penceresi hiç oluşmaz).
  Üretimde kalan NET satırı: SELECT count(*) FILTER (WHERE conflict_policy='NET') FROM
  portfolio_allocation_plan;  — B3 gereği satır varsa migration DURACAK.

GÖREV: `B` — alembic revision + CHECK yeniden yazımı + enum üyesinin düşürülmesi.
  ÇAPALAR (ADIM 123, tam adlarıyla): commands/allocation_plan.py::upsert_allocation_draft
  içindeki NET token reddi · shared/errors.py::CrossItemConflictPolicyNotSelectableError ·
  rules.py::_net_policy_warning + _NET_POLICY_BODY · arbitration.py:269 NET kuralı ·
  engine.py::conflict_downgraded_from_net · frontend CONFLICT_POLICY_LABELS.NET +
  Portfolio.tsx'in disabled-option bloğu. B inince BUNLARIN HEPSİ ölü koda döner.
  Beş test dosyası: test_allocation_rules.py, test_allocation_persistence.py,
  test_backtest_output.py, test_backtest_cross_item_arbitration.py,
  test_oracle_portfolio_capital.py (+ portfolio.test.tsx).

YASAKLAR: SHARED_ALLOCATION_STATUS'a DOKUNMA. ENGINE_VERSION/golden el değmez —
  oynuyorsa DUR ve raporla. #544/#559 human-only. ADR-0002'ye amendment yazma.
  B3'ü gevşetme: satır varsa migration DURUR, yeniden yazmaz ve NULL'a çevirmez.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  L1 FK insert-order proof + alembic up/down/up ZORUNLU; GateGuard'da 4 olguyu sun;
  kapanış ritüeli ZORUNLU.
```
