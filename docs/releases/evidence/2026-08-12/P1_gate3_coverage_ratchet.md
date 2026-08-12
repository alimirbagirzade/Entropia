<!-- doc-status: historical -->
# ADIM 42 — P1-Gate3 kanıt defteri (2026-08-12)

Her satır bir **koşudur**: komut, `$?` ile **ayrı** okunmuş exit code, ve o koşunun
ürettiği sayı. Hiçbir komut `| tail`'e borulanmadı.

Ölçüm ağacı: `origin/main` @ `c697fad` + dal `test/rc-p1gate3-criteria-ratchet`.
İzole DB: `entropia_p1gate3` (`postgresql+asyncpg://`), bu worktree'ye özel.

| # | Ne | Komut | Exit | Ölçülen | Ham |
|---|---|---|---:|---|---|
| 1 | Kapı + ratchet | `uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report --ratchet` | **0** | `383 criteria / 1175 clauses` · covered **234** · partial **126** · uncovered **8** · sınıflar `{A:1, B:95, C:6, D:32}` | [`gate3_acceptance_semantic_scan.txt`](gate3_acceptance_semantic_scan.txt) |
| 2 | **Ratchet negatifi** | aynı komut, tavanı bir düşürülmüş bir baseline ile | **1** | `FAIL: … status.partial: 126 measured, ceiling 125 (+1)` | [`p1gate3_ratchet_negative.txt`](p1gate3_ratchet_negative.txt) |
| 3 | Pin testleri | `uv run pytest …::test_active_run_blocks_work_object_delete …::test_soft_delete_removes_item_from_projection -q --no-cov` | **0** | 2 passed | [`p1gate3_pin_tests.txt`](p1gate3_pin_tests.txt) |
| 5 | Tam backend suite | `uv run pytest -q` (izole DB) | **1** | coverage **%93.61** (kapı ≥90 geçti); tek kırmızı `test_repository_facts_guard.py::test_the_repository_itself_passes_the_documentation_truth_gate` — teşhis edildi ve düzeltildi (aşağıda). **passed/failed özet satırı YAKALANAMADI** (aşağıya bak) | — |
| 6 | Documentation-truth kapısı (düzeltmeden sonra) | `uv run python ../scripts/generate_repository_facts.py --root .. --check` | **0** | `documentation-truth gate OK` | [`p1gate3_documentation_truth_gate.txt`](p1gate3_documentation_truth_gate.txt) |
| 4 | Kapı unit testleri | `uv run pytest tests/unit/test_acceptance_semantic_map.py -q --no-cov` | **0** | 61 passed (13'ü bu slice'ın) | [`p1gate3_gate_unit_tests.txt`](p1gate3_gate_unit_tests.txt) |

## Ölçüm 1'in en önemli tek satırı

Koşu, 2026-08-07'nin **229 / 131 / 8** dağılımını birebir yeniden üretti. **Sayılar
bayat değildi** — kalem "sayı yanlış" diye değil, "sayı anlamsız" diye açıktı.

## Neden negatif kanıt zorunluydu

Kırmızıya dönemeyen bir kapı dekordur. Ölçüm 2 gerçek haritayı bir tavan-eksi-bir
baseline'a karşı koşturur ve **exit 1** verir; ayrıca altı unit test dört ayrı kırmızı
yolu provoke eder: sınıfsız açık kriter, bilinmeyen sınıf, statü sayısının artması,
**tek bir sınıfın** artması (B düşerken D artarsa net yeşil OLMAMALI) ve korpusun
küçülmesi.

## Bu koşunun kapattığı 8 clause / 5 kriter

`AOS-17.c2` · `AOS-17.c3` · `TS-17.c2` · `TS-17.c3` · `TR-06.c3` · `TL-19.c2` ·
`AOS-18.c2` · `TL-20.c2` → kriter düzeyinde `AOS-17`, `TS-17`, `TR-06`, `TL-19`,
`AOS-18` **covered**; `TL-20` `c3` yüzünden **partial kaldı** (sınıf B).

## Kapatılmayanlar

**134 açık kriterin hiçbiri** bu slice'ta kapatılmadı — kapsam dışıydı. Sıralı defter:
[`../../../audit/acceptance_coverage_debt_ledger.md`](../../../audit/acceptance_coverage_debt_ledger.md).

## Ölçüm 5'in bulduğu tuzak (düzeltildi)

`docs/audit/acceptance_semantic_traceability.md` **üretilmiş** bir dosya, ama `origin/main`'de
üstüne **elle** bir `doc-status: historical` banner'ı eklenmişti. Onu yeniden üretmek banner'ı
**sessizce siliyor** ve documentation-truth kapısını kırmızıya çeviriyordu — üreticinin kendi
başlığı *"do not edit by hand"* diyor olmasına rağmen. Kalıcı düzeltme: banner artık
`acceptance_semantic_scan.py::HISTORICAL_BANNER`'dan **üretiliyor**, iki artefakt da onu taşıyor.
Aynı koşu iki kickoff'un birden `current` iddia ettiğini de yakaladı; `ADIM41_LANDED_KICKOFF.md`
**superseded** olarak `historical`'a düşürüldü.

**Tam suite ölçüm 5'ten sonra YENİDEN KOŞULMADI.** Aradaki fark yalnız iki üretici sabiti
(`HISTORICAL_BANNER`), üç doc-status işareti ve yeniden üretilmiş artefaktlardır; ürün kodu ve
test mantığı değişmedi. Kırmızı olan test ile komşuları ayrıca koşuldu (**95 passed**, exit 0).
**Otorite CI'dır.**

## Ölçüm 5'in İKİNCİ bulgusu — özet satırı yine kaybedildi

`CLAUDE.md` bu tuzağı adıyla uyarıyor (*"ADIM 17 koşusunda pytest'in özet satırı ve exit
code'u yakalanmamıştı — çıktıyı dosyaya yaz, `$?`'i ayrı oku"*). Exit code bu kez **doğru**
alındı (`PYTEST_EXIT=1`, ayrı satır), ama **`N passed / M failed` özeti log'da hiç yok**:
543 satırlık çıktı `short test summary info` ve adı verilmiş tek FAILED ile bitiyor.
`grep -c passed` → **0**.

Bu yüzden bu belge bir passed sayısı **iddia etmiyor**. Yakalanan üç olgu: **exit 1** ·
coverage **%93.61** (kapı ≥90 karşılandı, yani suite gerçekten sonuna kadar koştu) · **tek**
adı verilmiş başarısızlık. Sayıyı uydurmak, bu dalganın tam olarak kovaladığı hata olurdu.
**Bir sonraki koşuda `-q` yerine `-rN --tb=short` kullan ve özeti ayrıca `tee` ile yakala.**
