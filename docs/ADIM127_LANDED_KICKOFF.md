<!-- doc-status: historical -->

# ADIM 127 — `C8` (üretim worker'ı üzerinde oracle'lar) İNDİ · sıradaki kalem

> Bu belge **canlı** kickoff'tur. Bir önceki (`docs/ADIM126_LANDED_KICKOFF.md`) `historical`
> işaretlendi. Sayısal otorite **bu belge değil** —
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).

---

## Nerede duruyoruz

`C7` ADIM 126'da indi. `C8` bu slice'ta indi ve planın sözüyle bir **oracle slice**'ıdır:
**`backend/src` ve `frontend/src`'te SIFIR SATIR**, migration yok, `ENGINE_VERSION`
değişmedi, OpenAPI değişmedi, golden dosyası el değmedi. `SHARED_ALLOCATION_STATUS` hâlâ
`future_dev`; **lift olmadı**. Blocker DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 127.

---

## Bu slice'ın bıraktıkları (yeniden kullanım çapaları — TAM sembol adlarıyla)

`backend/tests/integration/test_shared_clock_production_oracles.py`:

| Sembol | Ne işe yarar |
|---|---|
| `_enable_shared_pool_plan(session, actor, cid, *, reserve_percent, shares)` | **EŞİT OLMAYAN** share'li ve rezervli shared-pool planı; item id'leri mainboard sırasında döner. `_enable_shared_pool` (eşit bölen) hâlâ `C4` modülünde. |
| `_trade_rows(session, result_id)` | Composite trade ledger'ı `seq` sırasında, satır ULID'i **düşürülmüş** olarak |
| `_flat_signal_events(session, result_id)` | Karar izini `(item_id, occurred_at, event_type)` ile anahtarlanmış, **noktalı yaprak yollarına düzleştirilmiş** olarak — bir diff'in ALAN adlandırabilmesi için |
| `_final_equity(session, result_id)` | Persist edilmiş equity eğrisinin son noktası |
| `_canonical_rows(rows)` | Satırları sıraya duyarsız, içeriğe duyarlı **multiset** olarak |
| `_PERMUTATION_MOBILE_FIELDS` | Bir mainboard permütasyonunun oynatmasına **izin verilen** üç signal-event alanı |
| `_PERMUTATION_REORDERED_ARTIFACTS` | Satır sırası pin sırasını izleyen iki checksum'lı artefakt (`signal_events`, `trade_ledger`) |

`C4` modülünden **aynen** yeniden kullanılanlar (kopyalama): `_lifted`, `_admit_and_run`,
`_composition`, `_artifact_checksums`, `_enable_shared_pool`.

---

## Sıradaki kalem

**`C9` — lift.** Ama önce, bu slice'ın **açıkta bıraktıkları**:

1. **A4 çekişmeli hâlde ölçülmedi** ve `covered` **işaretlenmedi**. Ölçülen kompozisyon
   çekişmesizdi. Çekişmeli bir fixture kurmak A4'ü kapatmaz — tam tersine, orada
   `(pin_ordinal, item_id)` **tasarım gereği** karar verir; kapatılacak şey, o sınırın
   nerede olduğunun ölçülmesidir.
2. **A6/A7 ve A9/A10 worker düzeyine çıkarılmadı.** Üçü de unit düzeyde kanıtlı; worker
   oracle'ları yazılmadı. `C8`'in kapsamı bunları içeriyordu — **kapsanmadı ve iddia
   edilmiyor**.
3. **A13 pini bugün bağımsız yanlışlanabilir değil** (golden testi adlar üzerinde total).
   Değeri `C9`'un baseline'ı yeniden ürettiği andaki tripwire'dır.

**`C9` için pazarlıksız devir (ADIM 126'dan, DEĞİŞMEDİ):** `ENGINE_VERSION`'ı lift
commit'inde **TEKRAR bump et**. `C7`'nin bump'ı A16'nın kayıt değişikliği için harcandı ve
A15'i **KAPATMAZ**; `test_lifting_containment_requires_a_second_engine_version_bump` bunu
zorlar.

---

## Yöntem notu — bu slice'ta işe yarayan

- **Bir "ölçülemez" kaydını, GEREKÇESİYLE birlikte yeniden ölç.** A4'ün gerekçesi
  (*"needs the real engine behind the loop"*) `C3`/`C4` ile kapanmıştı; kayıt bayattı.
- **Fixture'ın kendisi vacuity deliği olabilir.** 50/50 sleeve, sleeve'leri pin konumundan
  dağıtan bir kusuru **görünmez** kılıyordu; 60/40'a geçmek testi falsifiable yaptı ve deliği
  **negatif kontrol süreci** buldu.
- **Bir kontrol yalnız hedefi düşürmelidir.** NC-1'in dört denemesi reddedildi; üçü mevcut
  guard'lara çarpıp koşuyu tamamen düşürdü. Kırmızının **hangi assertion'da** olduğunu oku.

---

## Paste-ready resume prompt

```
ENTROPIA — C9 öncesi: A4'ün çekişmeli yarısı + A6/A7/A9/A10 worker oracle'ları

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: C8 ADIM 127'de indi (oracle slice; backend/src'te sıfır satır). A4 PARA için
ölçüldü ve sağlanıyor, ama ÇEKİŞMESİZ kompozisyonda — `covered` İŞARETLENMEDİ.
Otorite: docs/PROJECT_HISTORY.md §ADIM 127 + docs/ADIM127_LANDED_KICKOFF.md.

GÖREV (ürün kodu YAZMA — bu da oracle işidir):
  1) A6/A7 (compound ↔ fixed sleeve) ve A9/A10 (blokeli pay devredilmez, solvency reddi)
     worker düzeyinde, PERSIST EDİLMİŞ Result üzerinden. Bugün yalnız unit düzeyde kanıtlı:
     test_oracle_portfolio_capital.py · test_backtest_cross_item_arbitration.py ·
     test_backtest_portfolio_ledger.py
  2) A4'ün çekişmeli sınırı: jointly-insolvent iki intent kurup mainboard sırasının
     KARAR VERDİĞİNİ ölç. Bu A4'ü kapatmaz; sınırı ölçer.

ÇAPALAR: tests/integration/test_shared_clock_production_oracles.py içindeki
  _enable_shared_pool_plan (EŞİT OLMAYAN share + rezerv) · _trade_rows ·
  _flat_signal_events · _final_equity · _canonical_rows

YASAKLAR: capability.py DOKUNULMAZ (o C9). ENGINE_VERSION / golden / migration / OpenAPI:
  dördü de HAYIR. shared_shapes.py'ye imzasız satır ekleme.

TUZAKLAR (ADIM 127'de birinci elden ölçüldü):
  - Eşit sleeve'ler vacuity deliğidir; UNEQUAL share kullan (_enable_shared_pool_plan).
  - Negatif kontrollerin çoğu mevcut guard'lara çarpıp koşuyu tamamen düşürür
    (RUN_FAILED_ENGINE_ERROR) — bu AYIRT EDİCİ DEĞİLDİR. Kırmızının hangi assertion'da
    olduğunu oku; dokunulmamış 14 C4 testi YEŞİL kalmalı.
  - trade_ledger satırı item etiketi TAŞIMAZ; aynı-instant iki satırı yalnız sıra ayırır.
  - Alt küme koşarken --no-cov. Wrapper subshell'in exit code'u pytest'in DEĞİLDİR.

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB kullan.
  backend/.venv yoksa `uv sync --all-extras`.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
