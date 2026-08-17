<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular).

# ADIM 73 LANDED — kabul borcu batch 06 (doc 07, backend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 73. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

Base **`df7df92`** · alembic head **`0043_i08_registry_strategy_fks`** · `ENGINE_VERSION`
**değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` = **`future_dev`** ·
migration **YOK** · **ürün kodu değişmedi**. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
verdict BLOCKED.**

Tavanlar `partial` **103 → 100**, `debt_class.B` **72 → 69**. Açık kabul borcu:
**A=1 · B=69 · C=6 · D=32 → 108**. Clause düzeyinde `covered` **1007 → 1010**, `uncovered`
**120 → 117**; `total_criteria` **383** (taban).

## Bu slice'ın öğrettikleri

1. **KICKOFF'UN TABAN ETİKETİNE DEĞİL SHA'SINA GÜVEN.** Bu slice'ın kickoff'u tabanı
   *"ADIM 68 sonrası"* diye tarif ediyordu; SHA doğruydu ama o commit'te son kayıt **ADIM
   71**'di (69/70/71 arada inmişti). `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1`
   **her slice'ta** koşulmalı — kickoff'un düzyazısı değil, o komut numarayı söyler.
   Şansımıza kabul defteri sayıları oynamamıştı (69/70/71 kriter kapatmadı), ama bu
   **ölçülerek** doğrulandı, varsayılmadı.
2. **"Son açık clause'u benim yüzeyimde mi?" — parti seçiminin TEK doğru sorusu.** Tavan
   **kriter** düzeyinde sayılır, clause düzeyinde değil. Son clause'u kapatmayan bir clause
   kapatmak defteri iyileştirir ama **hiçbir tavanı indirmez**. `PC-01.c3` tam olarak bu
   yüzden alınmadı: backend'di ama `.c2` frontend olduğu için satır kapanamazdı.
3. **Aynı exception'ı fırlatan iki kol AYIRT EDİLEMEZ — ayrımı audit'ten kanıtla.**
   `_enforce_precheck_gate`'in `context_hash` ve `registry_fingerprint` kolları **aynı**
   `PrecheckStale`'i fırlatır. `pytest.raises(PrecheckStale)` tek başına hangi kolun
   koştuğunu **söylemez**; testi anlamlı yapan şey durable audit'te
   `old_context_hash == new_context_hash` (context kolu çalışmadı) **ve**
   `new_registry_fingerprint is not None` (context kolu oraya `None` yazar) assert etmek.
   **Bir dalı test ediyorsan, komşu dalın aynı sonucu üretemeyeceğini kanıtla.**
4. **Bir kriterin adlandırdığı davranışı grep'le — dördün biri sevk edilmemişti.**
   `PC-20.c3` defterde sınıf B'ydi; ölçünce restore yolunda **hiçbir bayatlık işareti**
   olmadığı çıktı (§Bulgu). Sekizinci böyle bulgu.
5. **Negatif kontrolü ürün kodundan kaldırarak yap, testi bozarak değil** — ve hangi
   assertion'ın kırmızıya döndüğünü **kaydet**. `signature_matches` etkisizleştirilince
   scan `passed`'a düştü; bu aynı zamanda vakanın gerçekten imza kontrolüne **ulaştığını**
   kanıtladı (ADIM 71'in dersi: geçen bir kontrol yolun koşulmadığını söyler).

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Düğüm / sembol | Nerede | Ne işe yarar |
|---|---|---|
| `test_signature_mismatched_resolver_blocks_the_scan` | `tests/integration/test_create_package_precheck_worker.py` | scan düzleminde tipli resolver reddi + saklanan satırı geri okuma |
| `test_registry_move_under_a_passed_scan_is_stale_on_the_registry_arm` | `tests/integration/test_precheck_audit_events.py` | **registry kolunu** context kolundan ayıran audit kalıbı |
| `test_same_idempotency_key_replays_one_admission` | `tests/integration/test_create_package_precheck_worker.py` | admission-key replay: bir Job + bir audit + bir scan |
| `_audit_count(session, event_kind)` | `test_create_package_precheck_worker.py` | tek satırda audit sayımı (yeni yardımcı) |
| `esp_repo.set_trust_state(entry, ...)` | `repositories/esp.py` | registry'yi **oynatmanın** en ucuz yolu (`registry_version`'ı da bumplar) |

## BULGU — `PC-20.c3` sınıf D (kapatmaya çalışma)

*"Restore edilen bir package REQUEST bayat döner"* — doc 07 §5 talep ediyor, **kod
etmiyor**. Restore generic `_restore_registry_target`'tan geçer (yalnız `deletion_state`),
`get_current_scan` deletion filtresi olmadan okur, gate yalnız `context_hash` +
`registry_fingerprint` karşılaştırır — hiçbiri delete/restore ile oynamaz. **Restore edilen
istek Send kapısını GEÇER.** Ürün işi; **yeniden sınıflandırılmadı** (D tavanını yükseltir).

Defterdeki sekiz açık "sınıfı şüpheli" bulgusu: `TL-11.c3`, `TL-16`, `TL-01.c4`,
`RD-01.c4`, `RD-05.c5`, `RD-12.c4`, `RD-13.c4`, **`PC-20.c3`**. Bunları kapatmaya çalışma.

## Sıradaki tasarım işaretleri

- **Doc 07'de kalan açık clause'ların hepsi FRONTEND**: `PC-01.c2` (`Not Checked` pill,
  `pages/CreatePackage.tsx:973`'te tam bir kez var, hiçbir test assert etmiyor),
  `PC-01.c3` (backend ama satırı `.c2` kilitliyor), `PC-02.c2`, `PC-17.c4`,
  `PC-21.c2/.c3`. **Doc 07'yi frontend yüzeyiyle bitiren bir parti `PC-01`'i de kapatır** —
  `.c2` + `.c3` birlikte, tek satırda iki clause.
- **`PC-21.c3` bir NEGATİF KAPSAM iddiasıdır** (yüzey repaint / future leak / validation /
  approval hakkında hiçbir şey iddia **etmemeli**). Bugün onu koruyan hiçbir şey yok ve
  "yokluğu assert etmek" kolayca totolojiye kayar — düşünülmüş bir test şekli ister.
- **Sınıf B'de 69 kriter kaldı.** Kalan yoğun belgeler: doc 05 (TL, 8 — ama üçü şüpheli),
  doc 04 (TS, 6), doc 02 (AT, 5), doc 03 (AOS, 5), doc 18 (AL, 5).
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).
- `C2` hâlâ **G9** (ADR-0002 §6/§8 amendment) ve **G13** (P10 equity noktası) imzasız insan
  kapılarının arkasında — `docs/ADIM71_LANDED_KICKOFF.md` §Sıradaki'ye bak.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, batch 07
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

TABAN: ADIM 73'ün merge edildiği main.
  SHA'yı doğrula AMA etikete güvenme — numarayı
  `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile ÖĞREN (ADIM 73 dersi).
  Farklıysa durma, farkı raporla, aşağıdaki her ölçümü yeniden yap.

ÖN KOŞUL — ÖLÇEREK SEÇ
  1. docs/ADIM73_ ve ADIM71_LANDED_KICKOFF.md'deki REUSE ANCHOR tablolarını oku.
  2. Her aday için: kriterin ADLANDIRDIĞI davranış backend/src veya frontend/src'te
     SEVK EDİLMİŞ Mİ? grep ile doğrula. Değilse sınıf D'dir — bulguyu `notes`'a
     ölçümüyle yaz, YENİDEN SINIFLANDIRMA, başka kriter seç.
  3. "Son açık clause'u benim yüzeyimde mi?" — değilse tavan İNMEZ (ADIM 73 dersi).
  4. Defterde SEKİZ açık şüpheli bulgu var (TL-11.c3, TL-16, TL-01.c4, RD-01.c4,
     RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3) — bunları kapatmaya çalışma.

ÖNERİLEN PARTİ: doc 07 FRONTEND yüzeyi — PC-01(.c2+.c3), PC-02.c2, PC-17.c4, PC-21.c2.
  Bu doc 07'yi bitirir ve PC-01'i kapatır. PC-21.c3 bir negatif-kapsam iddiasıdır,
  totolojiye kaymadan yazılabiliyorsa al, yazılamıyorsa GEREKÇESİYLE bırak.

YAPILACAK
  Her clause için davranışı adlandıran testi yaz ve NEGATİF KONTROLDEN geçir:
  davranışı ÜRÜNDEN kaldır -> test KIRMIZI olmalı, hangi assertion'da olduğunu KAYDET.
  Kontrol GEÇERSE önce vakanın o yolu gerçekten koştuğunu kanıtla.
  Frontend düğüm id'si `::` DEĞİL ` > ` ile yazılır (UNRESOLVED_NODE).

RATCHET
  acceptance_semantic_map.yaml -> güncelle (clause evidence kriter düzeyindeki
  test_evidence'a DA eklenmeli, AXIS_NOT_IN_EVIDENCE).
  Son clause kapanıyorsa kriteri `covered` yap ve `debt_class`'i KALDIR.
  python3 docs/audit/acceptance_semantic_scan.py --root . --ratchet docs/audit/acceptance_coverage_baseline.json
  Tavanları ÖLÇÜLEN değere İNDİR (partial 100 / B 69 taban). total_criteria = 383 TABAN.
  Clause toplamlarını TAHMİN ETME, --report'tan oku. Sonra --write-ledger + repository_facts.

DOKUNMA
  sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py
  jobs/research_data.py::_pin_member / ::_seal_bundle

TEST
  cd backend && uv run pytest -q            (tam suite = coverage kapısı)
  alt kümede --no-cov EKLE. `pytest | tail` KULLANMA.
  cd frontend && npm test -- --run
  cd backend && ./.venv/bin/python ../scripts/generate_repository_facts.py --root .. --check

COMMIT / PR
  DAL: test/closure-acceptance-batch-07
  commit: test(closure-acceptance): <kapatilan clause'lar>
  AI ATTRIBUTION YOK. Draft PR aç, MERGE ETME. Kapanış ritüeli 6 madde.

FINAL RESPONSE
  Kapanan clause'lar + inen tavanlar + KAYDEDİLEN BULGULAR + koşan kapıların GERÇEK
  sayıları + dürüst sınırlar. DUR.
```
