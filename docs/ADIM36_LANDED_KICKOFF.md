<!-- doc-status: historical -->
> **DEVREDİLDİ (2026-08-11, ADIM 37).** Canlı kickoff artık
> `docs/ADIM37_LANDED_KICKOFF.md`'dir; buradaki resume prompt **bayattır** ve
> yapıştırılmamalıdır. Bu belge ADIM 36'nın (RC §6.7 / P6-ek + P6-6, PR #658)
> tarihsel kaydı olarak durur.
>
> Bu belge **ADIM 36 kapanışında** yazıldı. En altındaki *paste-ready resume prompt*
> temiz bir oturuma yapıştırılacak devam tohumudur.
> Sayısal otorite: `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check`).

# ADIM 36 LANDED — RC §6.7 / P6-ek + P6-6: harness fail-fast

**Tip:** harness/script slice'ı. **Ürün kodu değişmedi** — `backend/src` ve `frontend/src`
hiç düzenlenmedi, migration yok, `ENGINE_VERSION` sabit,
`SHARED_ALLOCATION_STATUS` = `future_dev`. Base `970ec81` (#656).

---

## Nerede duruyoruz

RC readiness raporunun §6.7 tablosunda iki **blocker olmayan** kalem vardı:

* **P6-ek** — `e2e-acceptance.sh` preflight koruması takılmış daemon'a karşı işlemiyor.
* **P6-6** — `dropdb` takılıyor → `backup-verify.sh` sağlam bir yedeği başarısız
  raporlayabilir.

İkisi de **yeniden üretildi** (rapor körü körüne kabul edilmedi), düzeltildi ve
**CI kapısı olan** bir regresyon testine bağlandı. Rapor kaydı: **§6.7.4** + §6.2 notu.

**Blocker sayısı DEĞİŞMEDİ (üç); RC verdict'i BLOCKED kalır.**

---

## Bu slice ne bıraktı — reuse anchor'ları (tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `scripts/lib/bounded.sh::bounded_run` | **Kısa bir harici sorguyu sınırlamanın TEK yolu.** `bounded_run SECONDS CMD…` → komutun kendi statüsü ya da **124**. Kendi timeout'unu yazma; GNU `timeout` bu repoda **kullanılamaz** (macOS'ta yok) |
| `BOUNDED_TIMEOUT_RC` | 124. Çağıran taraf "timeout mu, gerçek hata mı?" ayrımını **bununla** yapar |
| `e2e-acceptance.sh::dc` | **Bilerek sınırsız** — `up --build` / `exec` / `logs` buradan geçer, dürüst süreleri dakikalardır |
| `e2e-acceptance.sh::dc_probe`, `::inspect_field` | Kısa docker sorguları için sınırlı sarmalayıcılar. Yeni bir kısa sorgu eklerken **bunları** kullan |
| `E2E_DOCKER_PROBE_TIMEOUT_SECONDS`, `E2E_TEARDOWN_TIMEOUT_SECONDS`, `BACKUP_VERIFY_PG_TIMEOUT_SECONDS`, `BACKUP_VERIFY_RESTORE_TIMEOUT_SECONDS` | Sınır sabiti kalıbı: **adlandır, ölçüme dayandır, env ile geçersiz kılınabilir bırak** (test aynı kod yolunu 3s ile koşar) |
| `backup-verify.sh::EXIT_UNVERIFIED` (3) / `::EXIT_NOT_RESTORABLE` (1) | 3 **ORTAM** hakkında, 1 **YEDEK** hakkında karardır. Yeni bir ortam hatası eklerken 3 kullan |
| `backup-verify.sh::unverified` | Ortam hatalarının log etiketi — `fail` (yedek hakkında) ile karıştırma |
| `backend/tests/contract/test_harness_failfast_contract.py` | Kalıp: PATH'e sahte binary koy (takılan / patlayan / anında cevaplayan), exit code + **sınırlı dönüş süresi** assert et; asılı kalma `pytest.fail` olur, CI asılmaz |

**`bounded_run`'ın iki inceliği** (ölçülerek bulundu, tekrar keşfetme):
(i) `kill -0` ile yoklama kabuğun çocuğu reap etmesiyle **yarışır** → sonuç gerçek bir
`wait`'ten alınır. (ii) Yalnız doğrudan çocuğu öldürmek **yetmez**: `docker compose …`
eklentiyi `docker`'ın çocuğu olarak koşar, hayatta kalan torun `$( )` borusunu açık tutar
(2s sınıra karşı çağıran **60s** bloke ölçüldü) → **süreç grubu** öldürülür.

---

## Dürüst sınırlar (bir sonraki oturum bunları biliyor olmalı)

* **"Docker düzeldi" DEĞİL.** Daemon'a dokunulmadı; ölçüm günü zaten normal cevap
  veriyordu (`docker version` rc=0, 1.44s). Değişen tek şey: bir sonraki takılma
  **kendini bildirecek**.
* **P5/P6 blocker'ı KAPANMADI.** §6.2'nin açık ekseni kapsam boşluğu ve `flows`'un
  **CI kapısı olmaması** — o ADIM 30'un eksenidir.
* Aynı kusur sınıfı **yalnız bu iki script içinde** tarandı. `acceptance.sh`,
  `a11y-audit-stack.sh`, `dr-acceptance.sh`, `restore.sh` **taranmadı** — süpürme
  bilerek yapılmadı. Biri gerekirse ayrı bir slice.
* `dc up --build` / `exec` / `logs` sınırsız kaldı. Bunları sınırlamak **sahte
  başarısızlık** üretir — bu slice'ın tam tersi.
* Frontend suite'i koşulmadı (tek satır TS değişmedi; gerekçedir, ölçüm değil).
* **P11-1 (branch protection)** hâlâ açık — repo ayarı, **insan kararı**.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — devam

BASE: origin/main (DOĞRULA — ADIM 36 / P6-ek + P6-6 merged olmalı; `git fetch` + `gh pr list`)

OTURUM BAŞLANGICI
  1. git fetch; git log --oneline origin/main -6; gh pr list --state all
     → ADIM 36 (bounded.sh + fail-fast harness) gerçekten indi mi? Handoff BAYATTIR, doğrula.
  2. Oku: docs/ADIM36_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §Next
     → docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 + §8.
  3. Kod tarafına geçmeden ilgili docs/CODEMAPS/ haritasını oku, sonra
     codebase-memory-mcp ile sembolleri bul. Kör grep + tam dosya okuma YOK.

NEXT — DEĞİŞMEDİ: PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298`
call site. Tasarım işaretleri: docs/ADIM16_STEPPER_LANDED_KICKOFF.md, docs/ADIM26_KICKOFF.md.
`SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI) — ADIM 20 matrisindeki
A1/A3/A5 dışında hiçbir satır bu boşluk kapanmadan kapanamaz.

TAVİZ VERİLEMEZ
  · Empirically verify her code-review CRITICAL/HIGH bulgusunu düzeltmeden ÖNCE.
  · Tembel merdiven (ponytail-entropia): gerekiyor mu → codebase'de var mı → stdlib →
    kurulu bağımlılık → tek satır. Override listesi pazarlıksız.
  · Bir harness'ta kısa harici sorgu koşacaksan scripts/lib/bounded.sh::bounded_run
    üzerinden geçir; GNU `timeout` bu repoda kullanılamaz (macOS'ta yok).
  · Backend local verify: cd backend && uv run ruff check . && uv run ruff format --check .
    && uv run mypy src && uv run pytest -q   (alt küme koşarken --no-cov; `| tail` YOK;
    TEST_DATABASE_URL ile worktree'ye özel izole DB, sürücü postgresql+asyncpg://)
  · Yeni create_* → L1 FK insert-order proof + alembic up/down/up + migration↔model parity.
  · Yeşile zorlama YOK. "READY" YAZMA — verdict BLOCKED, blocker sayısı üç.

KAPSAM DIŞI (dokunma)
  · Üç blocker (A-08 · kabul akışları CI kapısı · react-router freeze) — insan kararı.
  · P11-1 branch protection — repo ayarı, insan kararı.
  · Diğer script'lere fail-fast süpürmesi — ayrı slice, bu oturumun konusu değil.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin 6 maddesi + docs regresyon kontrolü
  (git diff origin/main -- docs/ | grep '^-## ' → BOŞ) +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
