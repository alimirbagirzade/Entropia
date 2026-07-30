# I-17 landed — sıradaki slice için kickoff



> **STALE-BY-DEFAULT.** Bu dosyaya güvenmeden önce `git fetch && git log --oneline origin/main -6 &&
> gh pr list --state all` çalıştır.
>
> **2026-07-29 tazelemesi:** #416 merge oldu; bu dosyanın 1 numaralı adayı olan **RF-12 kusuru da
> kapandı (PR #434)**. "Sıradaki adaylar" aşağıda yeniden sıralandı.

---

## Nerede duruyoruz

`docs/spec` kabul ID'leri büyük ölçüde suite'ten alıntılanabilir. Ölçümü yeniden üret:

```bash
python3 docs/audit/acceptance_id_scan.py
# 2026-07-29 çıktısı: scanned 324 test files · GLOBAL 163/215 (75%) untraced=52
```

> **Dikkat — iki dürüstlük notu (2026-07-29):**
> 1. Tarayıcı **yalnız GLOBAL** basıyor. Bu dosyanın eski "kapsam içi **108/130**" rakamını
>    yeniden üretecek bir komut YOK; o sayı ampirik olarak doğrulanamaz, kullanma.
>    Tüm spec sayısı **162/215 → 163/215**.
> 2. Eşleşme naif metin aramasıdır (`acceptance_id_scan.py:27` `ID_RE`) ve **test dosyasındaki her
>    anmayı** sayar — kapsamı *reddeden* bir docstring bile "traced" görünür. Somut örnek: `RF-15`
>    doc 10'un MISSING listesinde değil, ama tek anması
>    `backend/tests/integration/test_rationale_persistence.py:15` — *"RF-15 … is NOT covered here"*.
>    Yani **163 bir tavandır**, taban değil.

Tam kayıt: `docs/PROJECT_HISTORY.md` §I-17 · Denetim artefaktı:
`docs/audit/acceptance_id_map.md` (§C = doc 06/08/09 eşlemesi, §E = gerçek boşluklar).

---

## Bu slice'ın bıraktığı REUSE çapaları (birebir sembol adları)

| Çapa | Ne için |
|---|---|
| `docs/audit/acceptance_id_scan.py` | ID izlenebilirliğini yeniden ölçen tarayıcı (rapor, gate değil) |
| `docs/audit/acceptance_id_map.md` §C | `CP-01…16` / `PL-01…21` / `ESP-01…20` audit-local ID'leri |
| `tests/unit/test_source_scan.py:1,28` | Kanonik etiketleme deseni ("PC-05/PC-06") |
| `unit/test_readiness_validators.py::test_strategy_without_a_rationale_family_blocks_ready_check` | RF-12 "anahtar yok" kolu (~~yanındaki KUSUR yorumu~~ — PR #434'te kaldırıldı) |
| `unit/test_readiness_validators.py::test_strategy_with_a_blank_rationale_family_blocks_ready_check` | RF-12 "boş string" kolu — parametrik blank regresyon deseni (PR #434) |
| `unit/test_trade_log_config.py::test_ready_save_without_a_source_file_is_an_import_binding_issue` | TL-04 deseni |
| `integration/test_rationale_persistence.py::test_client_manipulated_delete_still_meets_the_server_guards` | RF-16 — client-manipüle çağrı için üç-kapı deseni |
| `frontend/src/test/strategyForm.test.tsx` §`STRATEGY_INFO_PANELS` | AT-25 ⓘ katalog deseni |

---

## Sıradaki adaylar (öncelik sırasıyla — 2026-07-29'da yeniden sıralandı)

**0. ✅ LANDED — `fix/rf12-blank-rationale-family-blocks-ready` (PR #434).** Eski 1 numaralı
aday **kapandı**. `backend/src/entropia/domain/strategy/config.py:76-89`
`validate_rationale_family_not_blank` field validator'ı boş/whitespace `rationale_family_id`'yi
reddediyor; regresyon testi `tests/unit/test_readiness_validators.py:201-202`
(`test_strategy_with_a_blank_rationale_family_blocks_ready_check`, `["", "   ", "\t\n"]` ile
parametrik) + `:220` "padded ama gerçek id geçerli kalır" ikizi. Testin yanındaki eski
"HOLE (verified …)" yorumu **kalmadı**. Bu maddeye DOKUNMA.

**1. Doc 16 [RH] — en büyük tek delik: `2/16`.** Tarayıcı bugün RH-01…RH-06, RH-08, RH-10…RH-16'yı
MISSING veriyor; Results History suite'i var ama kabul ID'lerini anmıyor. En ucuz/en yüksek getirili
iş: mevcut history testlerine RH etiketlerini **doğrulayarak** ekle (etiketi testi okumadan yazma).
Sonra sırayla doc 07 [PC] `14/22` ve doc 14 [RC] `13/18`.

**2. Gerçek kapsam boşlukları (etiket değil, test yok) — 2026-07-29'da yeniden ölçüldü.**
TS-20/AOS-20 — Trading Signal için Tool Gateway parity testi yok; `test_gateway_parity_s4.py`
Allocation + Trade Log kapsıyor (TL-22), Signal hattı kanıtsız · AT-21 · AT-24 ·
TS-16/TL-18/AOS-16 (expand/collapse no-op) · **AOS-12** — `grep -rn "KIND_REVISION_MISMATCH"
backend/src frontend/src` → **0 hit** (implementasyon hâlâ yok) · PC-14/PC-19/PC-22 ·
CP-05, CP-14, PL-06, ESP-19 (docs 06/08/09 — tarayıcıya görünmez, §C).
**Düzeltme:** eski listedeki `RF-15` artık doc 10'un MISSING listesinde DEĞİL — ama bu
tarayıcı yanılması (yukarıdaki dürüstlük notu 2); RF-15 gerçekte hâlâ kapsanmıyor.

**3. AT-25 uyuşmazlığını PO ile netleştir.** Brief AT-25'i "Agent private root edit reddi" diye
tarif etmişti; doc 02 §12 AT-25 **"Info content"**. Spec'inki uygulandı. Agent'a özel test
isteniyorsa o **AT-21** (Strategy save Agent parity) — hâlâ açık.

**4. §C eşlemelerini uygulanabilir yap.** Doc 06/08/09 eşlemeleri şu an **beyan**; testler
audit-local ID'leri anmıyor, hiçbir araç zorlamıyor. Testlere `CP-07 (docs/audit, doc 06 row 7)`
biçiminde alıntı eklenirse tarayıcı bunları da ölçebilir.

**5. ID sütunsuz kalan sayfalar.** Doc 01/11/12/13/15/17/19/20 de kabul tablolarını ID'siz
yayımlıyor — aynı yapısal sorun, aynı `docs/audit/` çözümü uygulanabilir.

**6. Tarayıcıyı yanılmaya karşı sıkılaştır (opsiyonel, küçük).** `acceptance_id_scan.py` bugün
docstring'deki "NOT covered" anmasını da traced sayıyor. Basit iyileştirme: yalnız test
fonksiyon adı / `@pytest.mark` / ilk satır etiketinden say, ya da olumsuzlayan kalıpları ele.

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce ampirik doğrula.** Brief'in sayımlarının üçü yanlıştı (`PC-10` zaten etiketliydi).
  `docs/audit/acceptance_id_scan.py` ile yeniden say, brief'e güvenme.
- **Yalnız TEST dosyaları sayılır.** Production kaynak yorumu (`lib/tradeLog.ts`) implementasyonu
  belgeler, test kanıtlamaz. Naif grep bu yüzden olduğundan iyi bir tablo gösterir.
- **Yanlış etiket, etiketsizden kötüdür.** Bu slice'ta bir RF-15 iddiası yazıldıktan sonra
  ampirik olarak çürütüldü ve geri alındı (`_seed_principals` aile değil principal seed'liyor).
  Her eşlemeyi testi okuyarak doğrula.
- **Başarısız testi zorla geçirme.** RF-12'nin boş-string ikizi gerçek bir kusuru ortaya çıkardı;
  test kaldırıldı, kusur belgelendi — domain sessizce yamanmadı.
- **Ortam tuzağı.** Paralel worktree oturumları paylaşılan Postgres'in lock tablosunu tüketiyor.
  `TEST_DATABASE_URL` ile izole DB kullan; `max_locks_per_transaction` yetmezse
  `select pg_terminate_backend(pid) ... where state='idle in transaction'` ile sızıntıları temizle.
  Frontend'de **`--no-file-parallelism` ZORUNLU**.

---

## Paste-ready resume prompt

> **Not (2026-07-29):** buradaki eski RF-12 prompt'u **tükendi** — kusur PR #434'te kapandı.
> Aşağıdaki prompt yeni 1 numaralı adaya (doc 16 [RH] kabul-ID deliği) göre yazıldı.

```
Entropia — doc 16 [RH] kabul-ID izlenebilirliği (I-17 takibi).

Session START + git doğrulama: git fetch && git log --oneline origin/main -6 && gh pr list --state all.

Bağlam: docs/I17_LANDED_KICKOFF.md, docs/PROJECT_HISTORY.md §I-17,
docs/audit/acceptance_id_map.md §E. RF-12 kusuru KAPANDI (PR #434) — ona dokunma.

ÖLÇÜM (2026-07-29, kendin yeniden koş — bana güvenme):
  python3 docs/audit/acceptance_id_scan.py
  -> scanned 324 test files · GLOBAL 163/215 (75%) untraced=52
  -> doc 16 [RH] 2/16  MISSING: RH-01..RH-06, RH-08, RH-10..RH-16   <- en büyük tek delik

TARAYICI TUZAĞI: eşleşme naif metin aramasıdır (acceptance_id_scan.py:27) ve test dosyasındaki
HER anmayı sayar — kapsamı REDDEDEN bir docstring bile "traced" görünür (canlı örnek:
RF-15, backend/tests/integration/test_rationale_persistence.py:15). Yani 163 bir TAVAN.
Bu yüzden: etiketi testi OKUMADAN yazma; yanlış etiket, etiketsizden kötüdür.

Yap:
1. doc 16'nın kabul tablosunu (RH-01..RH-16) oku, her satır için mevcut Results History
   testlerinden gerçekten o davranışı kanıtlayanı bul (backend integration + frontend
   resultsHistory testleri). Eşleşmeyeni ZORLAMA — "test yok" diye raporla.
2. Eşleşenlere kanonik etiketi ekle (desen: tests/unit/test_source_scan.py:1,28 "PC-05/PC-06").
   Yalnız TEST dosyaları sayılır; production kaynak yorumu kanıt değildir.
3. Tarayıcıyı yeniden koş, öncesi/sonrası sayıyı raporla. Kapsanmayan RH ID'lerini
   docs/audit/acceptance_id_map.md §E'ye gerçek boşluk olarak yaz.
4. Verify: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
   && uv run pytest -q  (izole TEST_DATABASE_URL ile; alt küme koşarsan --no-cov ekle).
   Frontend: npm run test -- --no-file-parallelism.
5. Branch feat/rh-acceptance-id-traceability, ayrı PR, NO AI attribution.
   Kapanışta docs/PROJECT_HISTORY.md + docs/STAGE2_HANDOFF.md + CLAUDE.md §Current position güncelle.
```
