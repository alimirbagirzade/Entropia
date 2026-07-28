# O-14 landed — kickoff / devam notu

**Nerede duruyoruz.** O-14 (`PR #417`, merged 2026-07-28) Results History'nin görünürlük
sorgusunu mevcut `resource_share` altyapısına bağladı ve Supervisor rolünü doc 16 §2'ye göre
ayrıştırdı. Migration yok, ENGINE_VERSION değişmedi, route/şema değişmedi, frontend'e dokunulmadı.
Tam kayıt: `docs/PROJECT_HISTORY.md` §"O-14". Kısa kayıt: `docs/STAGE2_HANDOFF.md` §"O-14 … landed".

> **UYARI — main hızlı akıyor.** O-14 merge olduktan sonra #424 (K-09) ve #429 (K-10) landed.
> Bu dokümana güvenmeden önce `git fetch && git log --oneline origin/main -8` çalıştır.

---

## Slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

| Sembol | Nerede | Ne yapar |
|---|---|---|
| `can_view_result_composition(actor, *, owner_principal_id, workspace_kind, shared_principal_ids)` | `domain/backtest/result_visibility.py` | Saf yüklem. `identity.can_view`'i `EXPLICITLY_SHARED` ile çağırır → grant'ler sayılır; `None` fail-closed. |
| `ensure_can_view_result_composition(...)` | aynı dosya | Yukarıdakinin raise eden hali (`AccessDeniedError`). |
| `is_lab_scope_readable(actor, *, workspace_kind)` | aynı dosya | Agent research + `LAB_SCOPE_ROLES` (= `agent_workspace._LAB_ROLES` ikizi). |
| `LAB_SCOPE_ROLES` | aynı dosya | `frozenset({Role.ADMIN, Role.SUPERVISOR})`. |
| `shared_composition_ids(session, actor)` | `application/queries/result_access.py` | İstek başına TEK küme okuması (satır başına probe YOK). |
| `visible_composition_stmt(stmt, actor, *, shared_ids)` | aynı dosya | List SQL yüklemi. `EntityRegistry`'ye join'lenmiş bir statement bekler; lab kapsamı için `MainboardWorkspace`'i **outer** join'ler. |
| `ensure_can_view_composition(session, actor, workspace_entity_id)` | aynı dosya | Satır-bazlı yeniden kontrol (detail/compare/metrics/artifacts). Owner/Admin için hızlı yol. |
| `ShareResourceType.COMPOSITION` | `domain/sharing/enums.py` | `"mainboard_workspace"` — değer = paylaşılan kökün `entity_type`'ı. |

**Yeni bir Result okuma yüzeyi eklersen** onu `result_access` üzerinden bağla; dosyaya özel bir
`_ensure_can_view_workspace` kopyası **yazma** — O-14'ün kapattığı kusur tam olarak buydu.

---

## Sıradaki doğal işler (öncelik sırasıyla)

1. **Composition-share komut yüzeyi** — O-14'ün en somut açık ucu. Okuma yolu hazır; grant'i YAZAN
   komut/route yok. Deseni `application/commands/sharing.py` (paket paylaşımı) birebir veriyor:
   `resolve grantee → policy → OCC (`row_version`) → shareable-visibility → repo → audit + outbox`,
   `run_idempotent` içinde. Dikkat: composition'da `visibility_scope` kolonu **yok** — ya kolon
   eklenir (migration) ya da paylaşım visibility'den bağımsız modellenir; bu bir **karar**, sessizce
   varsayma. Bu slice gelince `soft_delete` yetkisinin iki farklı sahip alanına bakması
   (DTO → workspace owner, komut → `result.created_by_principal_id`) **yeniden değerlendirilmeli**.
2. **Doc 16 §2 "published" sütunu** — bugün erişilemez (composition'da visibility yok). Ancak
   composition'a `visibility_scope` gelirse anlamlı; o zamana kadar dürüst sınır olarak kalır.
3. **PO imzası + R2 kapanışı** — repo genelindeki tek büyük açık iş (değişmedi).
   `docs/implementation/v18_final_acceptance.md` §4, D-1…D-9.

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Önce spec'in erişim tablosunu oku, sonra kodu ampirik doğrula.** O-14'te bildirilen satır
  numaraları doğruydu ama asıl bulgu grep'le çıktı: aynı daralma **dört** dosyada kopyalanmıştı.
- **Kapsam uydurma.** Spec "erişilebilir çalışma kapsamı" diyorsa, repoda gerçekten modellenen bir
  kapsam ara (`_LAB_ROLES` gibi). Yoksa dürüst sınır yaz — sahte bir takım/proje modeli üretme.
- **Tam suite'i `| tail -N` ile koşma.** Özet satırı kaybolur, yalnız ERROR kuyruğu görünür ve
  yanlış teşhise götürür. Çıktının tamamını dosyaya yaz; otoriteyi CI'a bırak.
- `TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan.

---

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch && git log --oneline origin/main -8 &&
gh pr list --state all --limit 10 ile main'de gerçekten ne landed olduğunu doğrula (handoff
STALE-BY-DEFAULT). Sonra oku: docs/O14_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md §Next →
docs/PROJECT_HISTORY.md §O-14.

Görev: composition-share komut yüzeyi (O-14'ün açık ucu). Bugün Results History paylaşılan
composition'ları OKUYABİLİYOR (queries/result_access.py + domain/backtest/result_visibility.py,
resource_type='mainboard_workspace') ama bu grant'i YAZAN hiçbir komut/route yok — grant yalnız
repo katmanından (share_repo.create_share) yazılabiliyor.

Yap: application/commands/sharing.py desenini REUSE et (resolve grantee → policy → OCC row_version
→ repo mutasyonu → audit + outbox, run_idempotent içinde). YENİ paylaşım mekanizması icat etme.
KARAR gerektiren nokta: mainboard_workspace'te visibility_scope kolonu YOK — paket akışındaki
ensure_shareable_visibility karşılığını ya bir migration'la (kolon ekleyerek) ya da visibility'den
bağımsız bir kuralla modelle; hangisini seçtiğini gerekçesiyle yaz, sessizce varsayma.
Ayrıca yeniden değerlendir: soft_delete yetkisi DTO'da workspace owner'a, komutta
result.created_by_principal_id'ye bakıyor — grantee run başlatamadığı için bugün ayrışmıyor, bu
slice sonrası ayrışabilir mi?

+integration (owner grant verir / grantee görür / revoke sonrası görmez / yabancı 403 / OCC stale
409 / idempotent retry no-op). Backend verify: cd backend && uv run ruff check . &&
uv run ruff format --check . && uv run mypy src && TEST_DATABASE_URL=<izole-db> uv run pytest
--no-cov -q (çıktıyı dosyaya yaz, tail ile kırpma). Migration eklersen alembic up/down/up kanıtı.
Ayrı branch + ayrı PR, NO AI attribution.
```
