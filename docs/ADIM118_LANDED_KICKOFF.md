<!-- doc-status: historical -->

# ADIM 118 landed — G14/`C` sevk edildi; KAPISINI KAPATMIYOR (G8 paralel olarak #847 ile indi)

> **Bu belge canlı kickoff'tur.** `docs/ADIM115_LANDED_KICKOFF.md` `historical` oldu.

## Nerede olduğumuz

**alembic head `0043_i08_registry_strategy_fks`** (bu dalgada migration YOK) ·
`ENGINE_VERSION` **DEĞİŞMEDİ** · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`** (dokunulmadı) ·
**blocker sayısı 1 (yalnız A-08), verdict BLOCKED.**

İki imzalı karar sevk edildi:

| kapı | imza | sevk | kapandı mı |
|---|---|---|---|
| **`G8`** (#559) | A1 + B2 + C1, 2026-08-26 | **#847** (`ae18f46b`) — `shared/dst.py`; bu dal da yazmıştı, **duplicate SKIP edildi** (üç ürün dosyası birebir aynı ölçüldü) | issue durumu **insan kararı** |
| **`G14`** (#544) | Karar 1 = `C` şimdi + `B` önce-`C9`; Karar 3 = metin | bu slice | **HAYIR — `B` bekliyor** |

## Bu slice'ın bıraktıkları (REUSE çapaları, tam sembol adlarıyla)

- **`domain/allocation/rules.py::_net_policy_warning(*, shared_is_executable: bool)`** —
  bildirim metnini **dünyaya göre** kurar. Gövde `_NET_POLICY_BODY` (bayrağın her iki
  değerinde doğru) + ön ek `_NET_POLICY_NOT_EXECUTABLE_PREFIX` (yalnız contained).
  **Yeni bir kapasite bildirimi yazarken deseni buradan al:** sabit bir cümle bugünkü
  dünyada doğru olabilir ve lift'in ertesi günü yalan olur.
- **`validate_allocation`** artık `shared_allocation_is_executable()`'ı **tek kez** okuyup
  `shared_is_executable` değişkenine alıyor — kapı ile bildirim tek turda iki dünya
  anlatamaz. **İkinci bir çağrı ekleme.**
- **`test_shared_allocation_two_world_gate.py`** — üç yeni case:
  `test_the_net_notice_is_worded_against_the_world_that_applies` (karşı-olgusallık ekseni,
  `_lifted` fixture'ı ile) · `..._states_all_four_things_decision_3_requires` (içerik
  ekseni) · `..._does_not_import_the_phase_loop_to_say_this` (import kısıtı).
  **İki eksen bilerek ayrı** — biri diğerinin kusurunu göremez (NC-1/NC-2 ile ölçüldü).
- **`frontend/src/test/portfolio.test.tsx`** — `describe("Portfolio — the NET conflict
  policy notice (G14 / GH #544)")`, iki case: label sonucu **ilan etmez**, sunucu bulgusu
  **verbatim** render edilir.

## Sıradaki iş

**`G14`'ün `B`'si — ama ÖNCE Karar 2 İMZALANMALI.** Sıra pazarlıksız:

1. **Karar 2'yi imzala** (`closure_g14_net_conflict_policy_2026-08-25.md`): `'NET'` taşıyan
   mevcut satırlar → **B1** yeniden yaz (silent-fallback yasağına takılır) / **B2** `NULL`
   (kolon zaten nullable) / **B3** migration dursun (en dürüstü, elle iş bırakır).
2. Sonra `B`: alembic revision (`portfolio_allocation_plan.conflict_policy` VARCHAR + CHECK
   yeniden yazılır) + frontend + **beş test dosyası** (`test_allocation_rules.py`,
   `test_allocation_persistence.py`, `test_backtest_output.py`,
   `test_backtest_cross_item_arbitration.py`, `test_oracle_portfolio_capital.py`).
   Migration **up/down/up** ile doğrulanır.
3. `B` inince **#544 kapatılır** (kapanış yorumu şıkkı + belgeyi adlandırır), ön koşul
   **20** ve `final_closure_delta_audit_2026-08-25.md` §8 satır 20 güncellenir.

**Sonra:** `G11` + `G12` → `C6` · `G15` (leg 3) · ön koşul 15–18 (OD-1/OD-2/OD-3/OD-6) ·
`G10` (**ADR §16 Gate 2 = lift onayının KENDİSİ — HİÇ TALEP EDİLMEDİ**) · **EN SON `C9`**.
`G11`/`G12`'nin seçenek tabloları **HENÜZ OKUNMADI**; kullanıcıya sunulacak.
A-08 (#514) kendi hattında, **ajan kapatamaz**.

## Ölçülmüş tuzaklar (bu oturumda birinci elden)

- **`rules.py` `execution/arbitration.py`'yi İMPORT EDEMEZ.** Kapı bir **metin taraması**
  (`"execution.arbitration import" in text`) ve allowlist **imzalı**. Sembol adını yaz
  (`import` sözcüğü olmadan), import etme — NC-4'te iki kapı birden kırmızı verdi.
- **`inline_issues` `InlineError` üzerinden AKMIYOR.** Ayrı bir tablo satırı
  (`Portfolio.tsx` `<div>{issue.message}</div>`) render ediyor. `InlineError`'ı kırpan bir
  negatif kontrol **başka** testleri düşürür ve seninkini yeşil bırakır (NC-6 reddedildi).
- **Bir negatif kontrolün kırmızı olması yetmez — HANGİ assertion'da olduğunu oku.**
- **`docs/audit/*` ASLA `current` OLAMAZ.** documentation-truth kapısı bunu reddeder
  (*"bir history/audit kaydı asla canlı handoff olamaz"*) ve ikinci bir bulgu olarak
  *"birden fazla belge `current`"* der. bu dalın `G8` tabanı bu hatayla yazılmıştı; #847 onu zaten `historical` indirdi.
  **`current` yalnız EN YÜKSEK numaralı `ADIM<n>_LANDED_KICKOFF.md`'nindir.**
- **Tam suite, hedefli koşunun göremediği kapıyı kırar (ADIM 95).** Bu partide hedefli
  koşuların hepsi yeşildi; tam suite'in tek kırmızısı bayat üretilmiş olgulardı
  (`generate_repository_facts.py --root ..` ile kapandı) ve yanında yukarıdaki
  `doc-status` bulgusu çıktı.
- **Devir belgesinin dalı başka bir worktree'de KİLİTLİ olabilir.** `baadf5d0`
  `relaxed-mccarthy-b24bee`'de checkout'tu; aynı dal iki worktree'de checkout edilemez →
  commit'ten yeni dal kesildi (`claude/g14-c-net-notice`), eski worktree'ye dokunulmadı.
- **Numara `117`, `116` DEĞİL:** açık PR **#840** `docs/ADIM116_LANDED_KICKOFF.md` yolunu
  ekliyor (ADIM 91: çakışma **dosya yolunda** ölçülür). #840 inmezse bu numara bir
  **boşluk** bırakır — numaralar yeniden atanmaz (ADIM 90).

## Paste-ready resume prompt

```
ENTROPIA — oturum devri (G14/C sevk edildi; sıradaki iş G14'ün B'si — ÖNCE Karar 2 İMZASI)

ÖNCE DOĞRULA (handoff BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3
  gh pr list --state open

DURUM: G14 Karar C sevk edildi (ADIM 118); KAPI KAPATMADI. G8 (#559) paralel olarak
#847 ile indi — bu dal da yazmıştı, duplicate SKIP edildi (ürün kodu birebir aynı ölçüldü).
  SHARED_ALLOCATION_STATUS=future_dev, ENGINE_VERSION değişmedi — İKİSİNE DE DOKUNMA.
  C9 verdict = BLOCKED (docs/audit/closure_c9_containment_lift_verdict_2026-08-26.md,
  22 ön koşulun 12'si yeşil; 10 kırmızının 10'u bir insan imzasının arkasında).

SIRADAKİ İŞ — G14'ün B'si, AMA ÖNCE KARAR 2 İMZALANMALI:
  docs/decisions/closure_g14_net_conflict_policy_2026-08-25.md §Karar 2
  B1 (BLOCK_OPPOSITE'a yeniden yaz — silent-fallback yasağı) /
  B2 (NULL — kolon nullable) / B3 (migration dursun — en dürüstü)
  Kullanıcıya SUN, kendin seçme. İmzasız B UYGULANMAZ.

B'nin kapsamı: alembic revision (portfolio_allocation_plan.conflict_policy VARCHAR+CHECK)
  + CrossItemConflictPolicy'den NET'i düşür + frontend (CONFLICT_POLICIES,
  CONFLICT_POLICY_LABELS, Portfolio.tsx) + BEŞ test dosyası. up/down/up ZORUNLU.
  B inince #544 kapatılır, ön koşul 20 ve delta audit §8 satır 20 güncellenir.

SONRA: G11+G12 -> C6 · G15 (leg 3) · ön koşul 15-18 · G10 · EN SON C9.
  G11/G12 seçenek tabloları HENÜZ OKUNMADI. A-08 (#514) ajan kapatamaz.

ORTAM:
  cd backend && uv sync --all-extras
  export TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_c9
  cd frontend && npm ci && npm run lint && npm run typecheck && npm run coverage

TUZAKLAR (ADIM 118'de ölçüldü):
- rules.py arbitration'ı İMPORT EDEMEZ (imzalı allowlist, METİN taraması). Sembol adı yaz.
- inline_issues InlineError'dan AKMIYOR — Portfolio.tsx'te ayrı tablo satırı render eder.
- Negatif kontrolde kırmızının HANGİ assertion'da olduğunu oku (NC-6 bu yüzden reddedildi).
- Alt küme koşarken --no-cov; exit code'u AYRI oku ("pytest ... | tail" KULLANMA).
- Negatif kontrol yamasını BELLEKTEKİ anlık görüntüden geri al, "git checkout --" ile DEĞİL.
- GateGuard: mevcut dosyayı Edit'te 4 olgu sun; YENİ dosyayı Bash heredoc ile yaz.
```
