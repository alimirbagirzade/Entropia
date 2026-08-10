<!-- doc-status: current -->

# ADIM 34 landed — kickoff for the next session

**Ne indi:** RC readiness raporu §6.7'nin **P4-1 + P4-2** kalemleri — *"`alembic check`
exit 255, 40 index-adı sapması, hiçbir CI workflow'u onu koşmuyor"* ve *"`agent_event.seq`'te
iki kurulum yolu bit-özdeş değil."* Sapmaların **hepsi** kapatıldı, iki kurulum yolu index
ekseninde **bit-özdeş** hale geldi ve bir kapı CI'ya bağlanıp **negatifiyle** kanıtlandı.

**Ne inmedi (bilinçli):** `alembic check`'in kendisi **hâlâ exit 255**. Sebebi bu koşuda
**yeni ölçülen** bir sınıf: raporun *"tip/server-default değişimi = 0"* iddiası yanlıştı —
aynı komut **60 `modify_default`** işlemi de emitliyor. Rapora **P4-3** olarak yazıldı,
ölçüldü, **düzeltilmedi**.

> **Numara notu:** bu slice önce `ADIM 33` yazılmıştı; çalışma sürerken **#656 (P9-F1)
> `ADIM 33` adıyla merge oldu**. PR'ı merge edilmemiş olduğu için slice temiz biçimde
> **ADIM 34'e taşındı** — `CLAUDE.md`'nin kaydettiği çift-numara sorunundan bir tane daha
> üretmemek için. Merge edilmiş hiçbir başlık değiştirilmedi.

---

## 1. Nerede duruyoruz

- **Base:** `970ec81` (ADIM 33 / #656). **alembic head DEĞİŞMEDİ** —
  `0043_i08_registry_strategy_fks`; bu dalgada **migration YOK**.
- `ENGINE_VERSION` sabit · `docs/openapi.json` değişmedi · **ürün davranışı değişmedi** ·
  route path / react-query key / OCC token / Idempotency-Key / SSE taksonomisi / `lib/*.ts`
  **hiç dokunulmadı**.
- **RC verdict'i BLOCKED kalır, blocker sayısı DEĞİŞMEDİ (üç).** P4-1/P4-2 blocker değildi.

## 2. Bu slice'ın bıraktığı REUSE anchor'ları (tam sembol adlarıyla)

`scripts/schema_parity_gate.py`:

| Sembol | Ne işe yarar |
|---|---|
| `INDEX_AXIS_OPS` | kapının **sahiplendiği** autogenerate operasyon kümesi (`add_index`, `remove_index`, `add_constraint`, `remove_constraint`) |
| `EXPECTED_SERVER_DEFAULT_DEVIATIONS` | **60** — P4-3 tavanı. Düzeltilmemiş bir sorun kalabilir ama **yayılamaz**; azaltırsan bu sabiti de düşür |
| `INDEX_SHAPE_SQL` | `pg_index` üzerinden ad + kolon + uniqueness; `pg_get_indexdef`'i ad'dan ayırır ki rename **ad farkı** olarak görünsün |
| `MODEL_PACKAGE` | models paketinin adı; `run()` başındaki guard onu okur — import'un yan etkisi `Base.metadata`'yı doldurmaktır, CodeQL "unused import" sanmasın |
| `_verdict()` | PASS/FAIL metni. f-string içine koşullu ifade **yazma**: CodeQL `py/uninitialized-local-variable` false-positive'i tam oradan çıktı |
| `_index_shape()` / `_build_create_all()` / `_model_vs_migration_ops()` | üç ölçüm bloğu |

**Model tarafı ev stili — bu artık pazarlıksız:** yeni bir index eklerken
`mapped_column(..., index=True)` **KULLANMA**. Adı `__table_args__` içinde açıkça yaz:
`Index("ix_<tablo>_<kısa>", "<kolon>")`, ve migration'da **aynı** adı kullan. Aksi halde
SQLAlchemy `ix_<tablo>_<kolon>` üretir, migration'ın adıyla ayrışır ve kapı **kırmızıya
döner**. `audit.py`, `capability.py`, `auth.py`, `resource_share.py` bunu zaten yapıyordu;
artık dokunulan dokuz model dosyası da yapıyor.

## 3. ÖLÇÜLMÜŞ TUZAKLAR — bir daha düşme

1. **`alembic check`'in çıktısını yalnız `Detected …` satırlarından sayma.** §6.7 tam olarak
   bunu yaptı ve **60 server-default sapmasını kaçırdı**: `compare.server_defaults` farklı bir
   cümle kurar. **Otorite ERROR satırındaki operasyon listesidir**, INFO satırları değil.
2. **`alembic check` bu iş için tek başına yetersiz.** Operatör sınıfı taşıyan dört
   `audit_events` expression index'ini **atlayıp "eşit varsayar"**. Kurulum-yolu
   karşılaştırması (`pg_get_indexdef`) onları görür.
3. **`unique=True, index=True` birlikte = TEK unique index.** Migration `unique=True` **artı**
   ayrı `create_index` yazmışsa iki yol ayrışır. P4-2 tam olarak buydu.
4. **Sevk edilmiş adı isim benzerliğinden tahmin etme** — `pg_index`'ten oku.
   `ix_backtest_run_snapshot` sütunu `composition_snapshot_id`'dir.
5. **`uv run ruff/mypy/pytest` worktree'de `Failed to spawn` verirse** dev bağımlılıkları
   kurulu değildir: `uv sync --extra dev` (`[project.optional-dependencies]`, group değil).
6. **Tam backend suite ~22 dakika.** Foreground timeout'la koşma. Arka planda, **tek
   çağrıda**, `TEST_DATABASE_URL` ile worktree'ye özel izole DB'de koş.
7. **`scripts/` CI'da ruff'tan GEÇMİYOR** (`ruff check .` `backend/` içinden koşar) ama
   **CodeQL oradan da okur**. Yeni bir `scripts/*.py` yazarken CodeQL'i hesaba kat.
8. **`ci.yml` concurrency kusuru ONARILMIŞ** (satır 9–14). `CLAUDE.md` onu açık listeliyordu,
   bayattı; bu dalgada düzeltildi.
9. **Uzun bir slice sürerken `main` ilerleyebilir.** Bu dalgada #656 tam ortada indi ve
   **`ADIM 33` numarasını aldı**. Kapanış belgelerini yazmadan **önce** `git fetch` +
   `git log origin/main -3` ile numarayı doğrula.

## 4. Kapanmayan artıklar — bir sonraki slice bunları KAPATMAK ZORUNDA DEĞİL, ama BİLMELİ

- **P4-3 (YENİ):** 60 `modify_default` sapması, 40 tabloda 60 kolon. DB'de server default
  var, model onu yalnız Python tarafında bildiriyor. P4-2 ile **aynı aileden gerçek bir
  ayrışma** — `create_all` o kolonları DB-seviyesi default olmadan kurar. Düzeltmek
  `create_all` şemasını değiştirir → **ayrı karar, ayrı PR**. Kapı sayıyı tavana bağladı;
  **`alembic check` bu kapanana kadar yeşile dönmez**.
- **P11-1 açık:** `main`'de branch protection / ruleset YOK → yeni kapı da diğerleri gibi
  **job kapısıdır, required status check DEĞİLDİR**. **Repo ayarı, insan kararı.**
- §6.7'nin geri kalanı: P10-B2 · P11-2/3/6/8 · P10-7 · P1-B1/B2 · P8-B1/B2/B3 · P6-6 ·
  P6-ek · P1-Gate3 — hepsi **ayrı PR**. (P9-F1 ve P9-F2 kapandı: #656, #655.)

## 5. Çalışma yöntemi (bu slice'ta işe yaradı, tekrar et)

**Önce ölç, sonra düzelt, sonra kapıyı bağla, sonra kapının negatifini kanıtla.** Sırayla:
(a) iddiayı izole DB'de yeniden üret ve **şeklini** çıkar (yalnız ad mı, yapısal mı — fix
tipini bu belirler); (b) merdivenin **ilk uyan** basamağını seç (burada: DB'ye dokunmadan
model hizalama); (c) otoriteyi **DB'den oku**, tahmin etme; (d) kapıyı yaz ve **yeşil
doğrula**; (e) sapmayı geri koyup kapının **exit 1** verdiğini göster; (f) kapının
**ölçmediğini** açıkça yaz. Adım (f) bu dalganın tekrarlayan hatasının panzehiridir.

## 6. Next

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
Değişmedi; ADIM 25–34'ün hiçbiri motor yoluna dokunmadı. `run_portfolio` hâlâ üretimde
**çağrısız**, `SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI).

## 7. Paste-ready resume prompt

```
ENTROPIA V18 — devam

BASE: origin/main (DOĞRULA — ADIM 34 "fix(db): reconcile model and migration index
names, and gate the check" (PR #657) merge olmuş OLMALI; olmadıysa DUR).

Oturum başlangıcı: git fetch · git log --oneline origin/main -6 · gh pr list --state all.
Sonra oku: docs/ADIM34_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (§ADIM 34 + Next) →
docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 + §6.7.3 → gerekiyorsa
docs/PROJECT_HISTORY.md §ADIM 34 (hedefli oku, baştan sona DEĞİL).

ADIM 34'ün bıraktığı durum:
· §6.7 P4-1 ve P4-2 KAPANDI. index ekseni 40 → 0; alembic ↔ create_all BIT-IDENTICAL
  (361/361). alembic head DEĞİŞMEDİ (0043), migration YOK, ENGINE_VERSION sabit.
· Kapı: scripts/schema_parity_gate.py, ci.yml backend job'ında `alembic upgrade head`
  hemen ardından. exit 0 doğrulandı, negatifi kanıtlandı (exit 1).
· AÇIK: P4-3 (YENİ) — 60 modify_default sapması, 40 tabloda 60 kolon. `alembic check`
  bu yüzden HÂLÂ exit 255 ve kapı bunu sıfırmış gibi göstermez. Ayrı PR.
· RC verdict BLOCKED, blocker sayısı üç — DEĞİŞMEDİ.

Pazarlıksız: yeni index eklerken `index=True` KULLANMA — `__table_args__` içinde
`Index("<ad>", "<kolon>")` yaz ve migration'da AYNI adı kullan, yoksa kapı kırmızıya döner.
Tam suite ~22 dk → arka planda, tek çağrıda, TEST_DATABASE_URL ile izole DB.
Worktree'de `uv sync --extra dev` gerekebilir. scripts/ CI ruff'ından geçmez ama CodeQL okur.

Next: PR B — `ItemParticipant` adaptörü + jobs/backtest_engine.py:298 call site.
```
