# I-17 landed — sıradaki slice için kickoff

**Baseline:** PR #416 (`feat/t2-acceptance-id-traceability`) · **Migration YOK · ENGINE_VERSION değişmedi.**

> **STALE-BY-DEFAULT.** Bu dosyaya güvenmeden önce `git fetch && git log --oneline origin/main -6 &&
> gh pr list --state all` çalıştır. #416'nın gerçekten merge olduğunu ve **Backend CI'ının yeşil
> olduğunu** doğrula — RF-16 lokalde koşturulamadı, otoritesi o job'dur.

---

## Nerede duruyoruz

`docs/spec` kabul ID'leri artık büyük ölçüde suite'ten alıntılanabilir:
kapsam içi **108/130**, tüm spec **162/215**. Ölçümü yeniden üret:

```bash
python3 docs/audit/acceptance_id_scan.py
```

Tam kayıt: `docs/PROJECT_HISTORY.md` §I-17 · Denetim artefaktı:
`docs/audit/acceptance_id_traceability.md` (§C = doc 06/08/09 eşlemesi, §E = gerçek boşluklar).

---

## Bu slice'ın bıraktığı REUSE çapaları (birebir sembol adları)

| Çapa | Ne için |
|---|---|
| `docs/audit/acceptance_id_scan.py` | ID izlenebilirliğini yeniden ölçen tarayıcı (rapor, gate değil) |
| `docs/audit/acceptance_id_traceability.md` §C | `CP-01…16` / `PL-01…21` / `ESP-01…20` audit-local ID'leri |
| `tests/unit/test_source_scan.py:1,28` | Kanonik etiketleme deseni ("PC-05/PC-06") |
| `unit/test_readiness_validators.py::test_strategy_without_a_rationale_family_blocks_ready_check` | RF-12 + yanındaki KUSUR yorumu |
| `unit/test_trade_log_config.py::test_ready_save_without_a_source_file_is_an_import_binding_issue` | TL-04 deseni |
| `integration/test_rationale_persistence.py::test_client_manipulated_delete_still_meets_the_server_guards` | RF-16 — client-manipüle çağrı için üç-kapı deseni |
| `frontend/src/test/strategyForm.test.tsx` §`STRATEGY_INFO_PANELS` | AT-25 ⓘ katalog deseni |

---

## Sıradaki adaylar (öncelik sırasıyla)

**1. `fix/rf12-blank-rationale-family-blocks-ready` — KUSUR, en yüksek öncelik.**
`backend/src/entropia/domain/strategy/config.py:40` → `rationale_family_id: str = Field(...)`
`min_length` taşımıyor. `rationale_family_id: ""` parse ediyor ve **READY** veriyor; manipüle
client Family'siz RUN'a ulaşabilir. Gerekli: `min_length=1` + `test_readiness_validators.py`'de
boş-string regresyon testi (bu slice'ta yazıldı, başarısız olduğu için kaldırıldı — kusur yorumu
testin yanında duruyor). Domain değişikliği olduğu için izlenebilirlik slice'ına alınmadı.

**2. AT-25 uyuşmazlığını PO ile netleştir.** Brief AT-25'i "Agent private root edit reddi" diye
tarif etmişti; doc 02 §12 AT-25 **"Info content"**. Spec'inki uygulandı. Agent'a özel test
isteniyorsa o **AT-21** (Strategy save Agent parity) — hâlâ açık.

**3. Gerçek kapsam boşlukları (etiket değil, test yok).**
TS-20/AOS-20 — Trading Signal için Tool Gateway parity testi yok; `test_gateway_parity_s4.py`
Allocation + Trade Log kapsıyor (TL-22), Signal hattı kanıtsız · AT-21 · AT-24 ·
TS-16/TL-18/AOS-16 (expand/collapse no-op) · RF-15/ESP-05 · AOS-12 (`KIND_REVISION_MISMATCH`
implementasyonu yok) · PC-14/PC-19/PC-22 · CP-05, CP-14, PL-06, ESP-19.

**4. §C eşlemelerini uygulanabilir yap.** Doc 06/08/09 eşlemeleri şu an **beyan**; testler
audit-local ID'leri anmıyor, hiçbir araç zorlamıyor. Testlere `CP-07 (docs/audit, doc 06 row 7)`
biçiminde alıntı eklenirse tarayıcı bunları da ölçebilir.

**5. ID sütunsuz kalan sayfalar.** Doc 01/11/12/13/15/17/19/20 de kabul tablolarını ID'siz
yayımlıyor — aynı yapısal sorun, aynı `docs/audit/` çözümü uygulanabilir.

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

```
Entropia — RF-12 boş Rationale Family kusuru (I-17 takibi).

Session START + git doğrulama: git fetch && git log --oneline origin/main -6 && gh pr list --state all.
PR #416'nın (I-17 acceptance ID izlenebilirliği) merge olduğunu ve Backend CI'ının YEŞİL olduğunu
doğrula — RF-16 lokalde koşturulamadı, otoritesi o job.

Bağlam: docs/PROJECT_HISTORY.md §I-17 ve docs/audit/acceptance_id_traceability.md §E.1.

KUSUR (ampirik doğrulandı, 2026-07-28): backend/src/entropia/domain/strategy/config.py:40
`rationale_family_id: str = Field(...)` min_length taşımıyor. Sonuç:
  - anahtar YOK        -> STRATEGY_CONFIG_INVALID / NOT_READY  (doğru)
  - rationale_family_id: "" -> parse ediyor, READY veriyor      (YANLIŞ)
Doc 10 §14 RF-12 "Family seçmeden Ready Check -> failure, RUN locked" diyor; manipüle bir client
şu an Family'siz RUN'a ulaşabiliyor.

Yap:
1. min_length=1 ekle (veya normalize+boş kontrolü — hangisi domain'in geri kalanıyla tutarlıysa,
   önce benzer zorunlu ULID alanlarının nasıl tanımlandığını oku).
2. tests/unit/test_readiness_validators.py'de boş-string regresyon testini yaz; RF-12 etiketini
   koru. Geçen RF-12 testinin yanındaki "HOLE (verified ...)" yorumunu kaldır/güncelle.
3. Boş string'in başka bir yerden (payload normalizasyonu, frontend) zaten süzülüp süzülmediğini
   ampirik kontrol et — süzülüyorsa kusur daha dar, bunu dürüstçe raporla.
4. Verify: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
   && uv run pytest --no-cov -q  (izole TEST_DATABASE_URL ile).
5. Branch fix/rf12-blank-rationale-family-blocks-ready, ayrı PR, NO AI attribution.
   Kapanışta docs/PROJECT_HISTORY.md + docs/STAGE2_HANDOFF.md + CLAUDE.md §Current position güncelle.
```
