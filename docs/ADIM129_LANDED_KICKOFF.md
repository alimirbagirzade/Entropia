<!-- doc-status: current -->

# ADIM 129 — ön koşul 17/18 ölçüldü, ikisi de KIRMIZI kaldı · sıradaki kalem

**Taban:** `origin/main` @ `3fffb9de` (ADIM 128, PR #865) · **Dal:**
`claude/entropia-precondition-17-18-ec6744` · alembic head
`0044_drop_net_conflict_policy` (**migration yok**) · `ENGINE_VERSION` **değişmedi** ·
OpenAPI **değişmedi** · golden **el değmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`
(**el değmedi**) · `capability.py` **el değmedi** · `frontend/src` **sıfır satır**.
Blocker DEĞİŞMEDİ (1 — yalnız A-08), **BLOCKED**.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 129.

---

## Bu slice ne YAPMADI (önce bu okunmalı)

- **Ön koşul 17 ve 18 KAPANMADI.** İkisi de defterde `❌`; hiçbiri `covered` işaretlenmedi.
- **`CONTENTION_SELECTION_STATUS` ELLENMEDİ** — hâlâ `"recommended_pending_approval"`.
  Kanıt iddia değil, **negatif kontrol**: etiketi çevirmek yalnız önceden var olan
  `test_the_od3_selection_rule_is_labelled_as_pending_approval`'ı kırmızıya çevirir.
- **`MARK_STALENESS_POLICY` ELLENMEDİ** — hâlâ `"undefined_pending_od2"`, iki yerde
  (`manifest.py` + `execution/provenance.py`), parite testiyle bağlı.
- **`capability.py`, ADR 0002, golden digest dosyası: hiçbirine dokunulmadı.**

## Ölçülmüş dört gerçek — bir sonraki oturum bunları YENİDEN ÖLÇMESİN, ama GÜVENMESİN de

1. **17 = KOD, 18 = etiket.** ADR §13.1 *"Effect"* kolonu: OD-2 *"Not built … a
   prerequisite of ADIM 20"*; OD-3 *"Already the shipped behaviour"*.
   `provenance.py`'nin *"the same shape"* cümlesi bu eksende **yanlıştır**.
2. **18'in adındaki onay ALINDI** — ADR §13.1 (2026-08-05), ADR §16 **Accepted**. Sabitin
   docstring'i: *"it describes the LABEL's state, not the decision's."*
3. **ADR'nin flip gerekçesi ÇÜRÜDÜ** — *"`build_portfolio_manifest`, which nothing calls
   yet"* artık yanlış: `portfolio_projection.py::project_portfolio_run` → worker
   `jobs/backtest_engine.py`. Ayrıca A16 `mark_staleness_policy`'yi **sevk edilen**
   manifest'e koydu (`manifest.py::_portfolio_policy`).
4. **`capability.py` #4 ↔ OD-3(a) ÇELİŞKİSİ GERÇEK** ve **ürün sahibi 2026-08-28'de
   `C` dedi: şimdi çözme, `C9`'a adıyla devret.** Adjudication YAPILMADI.

## REUSE — çapa isimleriyle

| Ne | Nerede |
|---|---|
| OD-3 disclosure bloğu (düzeltilmiş) | `execution/arbitration.py::CONTENTION_SELECTION_POLICY` · `::CONTENTION_SELECTION_STATUS` · `::CONTENTION_SELECTION_NOTE` |
| Kendi kendine çelişmeme kapısı | `tests/unit/test_backtest_cross_item_arbitration.py::test_the_od3_disclosure_does_not_contradict_itself` |
| Etiketin (dokunulmamış) pini | aynı dosya `::test_the_od3_selection_rule_is_labelled_as_pending_approval` |
| OD-2 etiketinin İKİ yazımı + paritesi | `manifest.py::MARK_STALENESS_POLICY` · `execution/provenance.py::MARK_STALENESS_POLICY` · `tests/unit/test_a16_manifest_policy_parity.py` |
| `stale_after` sınırının **yokluğu** (17'nin işi) | `execution/clock.py::ItemTickView.staleness_ms` (ölçer, sınır uygulamaz) · `execution/portfolio_ledger.py` |
| İkinci bump borcunu zorlayan test | `test_lifting_containment_requires_a_second_engine_version_bump` |
| Ön koşul defteri | `docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md` §2 (satır 17/18 tazelendi; **donmuş `❌` kolonu el değmedi**) |

## Tuzaklar — birinci elden ölçüldü

- **`CONTENTION_SELECTION_NOTE`'un OKUYUCUSU YOK** (kendi tanımı + `__all__`). Hiçbir
  davranışsal test ona ulaşamaz → metni sessizce bayatlar. Yeni bir disclosure string'i
  eklerken ona bir **kaynak-düzeyi** kapı yaz.
- **Bir iddianın birden çok yazımı olabilir.** #852 üçünden **birini** düzeltti. Yeni bir
  karar kaynağa yazılırken `grep` ile **tüm** yazımlarını say.
- **Bayat bir kaynak, doğru okuyan bir denetimi yanıltır.** 2026-08-26 verdict'i
  *"OD-3 açık"* yazdı çünkü modül öyle diyordu. Verdict **yanlış değil, BAYAT** —
  `doc-status: historical`, **dokunulmaz**.
- **Kendi taraman kendi kanıtını yakalayabilir.** Retired bir cümleyi yorumda alıntılamak
  meşrudur (ADIM 90: *"alıntıyı temizlemek kanıtı siler"*), iddia etmek değil → tarama
  **yorum satırlarını dışlar**, ve bu bir kuraldır, gevşetme değil.
- **Alt küme koşarken `--no-cov`.** Wrapper subshell'in exit code'u pytest'in değildir —
  çıktıyı dosyaya yaz, `$?`'i ayrı oku.
- **Bu container'da `backend/.venv` YOKTU** → `uv sync --all-extras`. Arka plan komutu
  cwd'yi miras alır; **mutlak yol kullan**. Postgres :5432 ayakta;
  `TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan (integration şemayı
  `Base.metadata`'dan kurar, **alembic gerekmez**).

## Sıradaki kalem

**Ön koşul 17 (OD-2 mark policy) — ve o, `C9` ile birlikte yapılmalıdır**, çünkü literal
`execution_content` içindedir ve çevirmek **her `execution_key`'i kaydırır**; ADIM 126'nın
bump'ı zaten harcandı, ikinci namespace kayması `C9`'un lift commit'ine aittir. Ondan önce
gelen imza/kod kalemleri için `docs/audit/final_closure_delta_audit_2026-08-25.md` §10.

**`C9`'un devraldığı, artık ADLANDIRILMIŞ borç:** ikinci `ENGINE_VERSION` bump'ı · ön koşul
17'nin mark policy'si · 18'in flip'i (**ve flip sonrası DEĞER hiçbir belgede tanımlı
değil**) · **`capability.py` #4 ↔ OD-3(a) çelişkisi**.

---

## Paste-ready resume prompt

```
ENTROPIA — C9 öncesi: ön koşul 17 (OD-2 mark policy) sonrası kalemler

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: ADIM 129 ön koşul 17 ve 18'i ÖLÇTÜ ve İKİSİNİ DE KAPATMADI (ikisi de defterde ❌).
Ölçüm: 17 = KOD (OD-2 mark policy yazılmadı; `clock.py::ItemTickView.staleness_ms` boşluğu
ÖLÇER, sınır UYGULAMAZ), 18 = yalnız bir ETİKET ve adındaki onay ADR §13.1'de (2026-08-05)
ZATEN ALINMIŞ. `capability.py` #4 ("symmetric") ile OD-3(a) `pin_order_admission`
(kıtlıkta düşük pin'i kayırır) ÇELİŞİYOR — ürün sahibi 2026-08-28'de "C: şimdi çözme,
C9'a adıyla devret" dedi. Otorite: docs/PROJECT_HISTORY.md §ADIM 129 +
docs/ADIM129_LANDED_KICKOFF.md.

GÖREV: docs/audit/final_closure_delta_audit_2026-08-25.md §10'daki sırayı ÖLÇ ve sıradaki
  kalemi al. ÖNCE ÖLÇ: bir kalem "imza" gibi duruyorsa imza kutusunu BÖLÜM bazında oku
  (dosya düzeyinde grep yanıltır — ADIM 119); "kod" gibi duruyorsa ADR'nin "Effect on the
  delivery plan" kolonuna bak, orası KOD/ETİKET ayrımını söyler.

ÇAPALAR: arbitration.py::CONTENTION_SELECTION_{POLICY,STATUS,NOTE} ·
  test_backtest_cross_item_arbitration.py::test_the_od3_disclosure_does_not_contradict_itself ·
  manifest.py::MARK_STALENESS_POLICY + execution/provenance.py::MARK_STALENESS_POLICY
  (İKİ yazım, test_a16_manifest_policy_parity.py ile bağlı) ·
  test_lifting_containment_requires_a_second_engine_version_bump

YASAKLAR: capability.py DOKUNULMAZ (o C9). ADR §13.1/§14 invariant tablosunu YENİDEN YAZMA
  (adjudication). golden / migration / OpenAPI: hayır. İmza kutusu doldurma.
  MARK_STALENESS_POLICY'yi politikayı yazmadan ÇEVİRME — literal execution_content
  içindedir, çevirmek HER execution_key'i kaydırır ve o namespace kayması C9'un lift
  commit'ine aittir (ADIM 126'nınki zaten harcandı).

TUZAKLAR:
  - Bir kararın kaynakta BİRDEN ÇOK yazımı olabilir; #852 üçünden birini düzeltti.
  - Okuyucusu olmayan bir sabit (ör. eski CONTENTION_SELECTION_NOTE) hiçbir davranışsal
    testle korunmaz → kaynak-düzeyi kapı yaz.
  - doc-status: historical bir denetim BAYAT olabilir ama YANLIŞ değildir; dokunma, tarihle.
  - Yeşil bir NC bir bulgudur; kırmızının HANGİ assertion'da olduğunu oku.
  - Alt küme koşarken --no-cov. Wrapper subshell'in exit code'u pytest'in DEĞİLDİR.

ORTAM: Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB.
  backend/.venv yoksa `uv sync --all-extras` (mutlak yol kullan; arka plan komutu cwd miras alır).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
