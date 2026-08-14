<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 66 LANDED — research timing provenance bundle kimliğine pinlendi (P-E3, #558) · sıradaki slice için kickoff

> **NUMARA NOTU.** Yazıldığında main'in son kaydı **ADIM 65**'ti (base `2a314ae`). Dal
> (`fix/closure-e3-research-timing-provenance`) ve commit mesajları ADIM numarası **taşımaz**;
> bir çakışmada **merge edilmiş ad kazanır** ve bu belge yeniden numaralanır, dal yeniden
> yazılmaz.

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 66. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Migration yok, alembic head
`0043_i08_registry_strategy_fks`, `ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` =
`future_dev`. **OpenAPI DEĞİŞTİ** (iki bundle route'u artık tipli gövde yayımlıyor).

Bu slice **ürün kodunu değiştirdi**: `bundle_hash` artık timing provenance'ına **duyarlı**.
Deponun **tek `xfail(strict)`'i kaldırıldı** — üretilmiş artefakt bunu doğruluyor
(`repository_facts.md`: `Backend xfail markers: 1 (1 strict)` → **`0 (0 strict)`**).

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

| Sembol | Nerede | Ne için |
|---|---|---|
| `_pin_member(session, revision)` | `application/jobs/research_data.py` | **Her** bundle üyesi buradan geçer. Yeni bir bundle yüzeyi eklersen üyeyi elle kurma, bunu çağır. |
| `_derived(members, key)` | aynı dosya | Üye anahtarından sıralı + tekilleştirilmiş + null'suz üst düzey dizi. Yeni bir §9.2 dizisi eklersen bundan geçir. |
| `_enum(value)` | aynı dosya | `str(enum)`/`None` — manifest'in kendi coercion'ı. |
| `SealedBundleResponse` / `BundleMemberModel` | `apps/api/routes/research_data.py` | Yayımlanan gövde şeması. **`response_model` olarak bağlama** — gerekçe aşağıda. |
| `TIMING_KEYS` | `tests/integration/test_research_point_in_time_parity.py` | Parity sözleşmesinin **kendisi**. Manifest'e yedinci bir timing alanı eklersen buraya da ekle, yoksa #558 sessizce geri gelir. |
| `_three_artifacts(session, entity_id, revision)` | aynı dosya | Üç artefaktı tek çağrıda kurar (Agent bundle / evidence bundle / Run manifest). |

## Pazarlıksız — bu slice'ın öğrendikleri

1. **`response_model` KULLANMA, `responses={200: {"model": ...}}` + `response_model=None` kullan.**
   Ölçüldü: `response_model` FastAPI'ye gövdeyi yeniden serileştirtir ve `task_id`/`run_request_id`'yi
   `null` olarak **geri ekler**; `_seal_bundle` ise None extra'yı **düşürür** ve düşürülmüş gövde
   **hash'lenen gövdedir**. `response_model=None` olmazsa şema `$ref` + eski serbest alanlarla
   **birleşir** (bu da ölçüldü).
2. **`_derived`'ın `sorted()`'ı taşıyıcıdır.** `canonical_json` nesne anahtarlarını sıralar,
   **dizi elemanlarını sıralamaz** → sıralamayı kaldırmak `bundle_hash`'i çağıranın argüman
   sırasına bağlar. Negatif kontrolü kanıtlı.
3. **Aynı token'lı iki üyeyle sıralama SINANMAZ.** Tek elemanlı küme her hâlde sıralı görünür.
   Sıralama testi **farklı** policy taşıyan bir üçüncü üye ister (`same_as_event_time`, doc 12
   §5.2 gereği `delay=None`).
4. **Harness zone alanlarını kurmaz.** `_research(...)` `source_timezone_mode`'u **set etmez**;
   kurmazsan üç artefakt `None` üzerinde anlaşır ve hiçbir yüzey alanı taşımasa da test geçer.
5. **Boş dizi bir BEYANDIR.** Arkasında alan olmayan bir §9.2 adını `[]` olarak yayımlamak
   *"böyle bir şey yok"* der — provenance **yalanı**. Yokluk provenance **boşluğudur**.
   Yokluk `test_the_sealed_bundle_publishes_doc_12_92_arrays` içinde **assert edilir**.
6. **Kabul borcunda CLAUSE ≠ KRİTER.** `RD-11.c2` kapandı ama tavanlar **kriter** sayar →
   hiçbir tavan oynamadı ve oynamamalıydı. Clause defteri: uncovered **124 → 123**.
7. **Test ekleyen slice `repository_facts`'i TAZELEMELİ** (ADIM 60'ın dersi; bu slice'ta
   collected 3570 → 3575 ve xfail 1 → 0 olarak yeniden üretildi).

## Sıradaki tasarım işaretleri

- **`RD-11.c3` AÇIK** (sınıf B): *"yeni bir onay canlı/bitmiş bir run manifest'ini yeniden
  yazmaz."* Hiçbir test bir successor revision'ı **run ortasında** onaylayıp manifest'i geri
  okumuyor. Harness'ın yarısı hazır: `_three_artifacts` manifest'i zaten kuruyor; eksik olan
  TAMAMLANMIŞ bir Backtest Run — `tests/integration/test_external_object_run_provenance.py::_completed_run`
  (ADIM 52) **yeniden kullanılabilir**.
- **§9.2'nin iki adı sınıf D** (`alignment_policy_versions[]`, `missing_and_stale_policies[]`).
  Bunlar **test borcu değil ürün boşluğudur**; kolon + migration + kim yazar sorusu bir
  **ürün kararıdır**, bir test slice'ının kararı değil.
- **Karar 1 (#552) ve Karar 3 (#559) HÂLÂ İMZASIZ.** #720 komisyonu imzasız sevk etti;
  komisyon **tabanı** (bps-on-notional ↔ düz tutar) açık.
- **GH #558 AÇIK BIRAKILDI.** Kapatmak insan kararıdır; issue durumu kanıt değildir.

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Ön koşulu ölçerek başla, belgeden alma.** Tasarım belgesi `0d8bf8f`'te ölçmüştü, main
  **81 commit** ilerlemişti; her satır `2a314ae`'ye karşı yeniden okundu ve **hepsi tuttu** —
  ama iki **yeni** bulgu çıktı (şema körlüğü, frontend aynası).
- **İmzasız karar = DUR, ama ölçümü önce bitir.** Slice durdu, karar oturum içinde ürün
  sahibine soruldu ve imzalandı. Tutarsız bir cevap (*"A1, A2, B ve C"*) **düzeltilerek**
  imzalandı — B, A'nın tam tersidir.
- **Her assertion'ı negatif kontrolden geçir.** Üç kontrol koşuldu ve üçü de kırmızı verdi.
- **Postgres bu container'da apt ile kurulu DEĞİL ama binary'ler var** (`/usr/lib/postgresql/16`).
  `initdb` root olarak koşmaz → `su postgres -s /bin/bash -c "..."` ile küme kaldır, sonra
  `entropia`/`entropia` @ `:5432`. Integration testleri **gerçekten koşar**.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — RD-11.c3 (run manifest'i bir successor onayına karşı değişmez)
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ORTAK SÖZLEŞME bloğunu buraya yapıştır]

TABAN
  Beklenen: ADIM 66'nın merge edildiği main. FARKLIYSA durma, farkı raporla,
  aşağıdaki her ölçümü yeniden yap.

ÖN KOŞUL — YOK. Bu bir test slice'ıdır, ürün kodu DEĞİŞMEZ.
  Değişmesi gerektiğini ölçersen DUR ve raporla: o bir sınıf-D bulgusudur.

YAPILACAK
  docs/audit/acceptance_semantic_map.yaml → RD-11.c3:
    "Approving a new revision leaves a running or finished run's manifest unchanged."
  Bugün hiçbir test bunu yapmıyor. Kanıtla:
    1. Bir research revision'ı pinleyen TAMAMLANMIŞ bir Backtest Run kur.
       REUSE: tests/integration/test_external_object_run_provenance.py::_completed_run
       ve ::_attach_trade_log (ADIM 52). Yeni builder YAZMA.
    2. Manifest'i oku ve sakla.
    3. AYNI root altında YENİ bir revision oluştur ve ONAYLA (approve Admin-only).
    4. Manifest'i yeniden oku → BİREBİR aynı olmalı; pinli revision_id kaymamalı.
  REUSE: test_research_point_in_time_parity.py::_three_artifacts, ::TIMING_KEYS,
  ::_research(..., approve=False).

  NEGATİF KONTROL ZORUNLU: assertion'ın vacuously geçmediğini göster
  (ör. manifest'i successor'ın id'siyle karşılaştır ve kırmızı verdiğini gör).

KABUL BORCU
  RD-11.c3 uncovered -> covered YAPABİLİRSEN: RD-11 kriteri partial -> covered olur,
  yani ceilings.status.partial 106 -> 105 ve debt_class.B 75 -> 74 İNER.
  RATCHET YALNIZ AŞAĞI İNER. total_criteria = 383 TABANDIR.
  Kapatamıyorsan SINIFINI DEĞİŞTİRME — B'den D'ye taşımak D TAVANINI YÜKSELTİR
  ve bu bir adjudication'dır, test slice'ının kararı değil.

DOKUNMA
  jobs/research_data.py::_pin_member / ::_seal_bundle (ADIM 66'nın alanı)
  sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py

TEST
  cd backend
  uv run pytest -q --no-cov -rxX tests/integration/test_research_point_in_time_parity.py
  Sonra tam suite + ruff + mypy + openapi --check + repository_facts --check.
  ALT KÜME KOŞARKEN --no-cov EKLE. `pytest | tail` KULLANMA.

COMMIT / PR
  DAL: test/closure-rd11-c3-manifest-immutability
  commit: test(closure-rd11): pin the run manifest against a successor approval
  MERGE ETME. Kapanış ritüeli 6 madde.

FINAL RESPONSE — [ORTAK ŞABLON] + "RD-11.c3 durumu: kapandı/kapanmadı + gerekçe"
DUR.
```
