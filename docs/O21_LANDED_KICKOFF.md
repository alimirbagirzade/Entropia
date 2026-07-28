# O-21 landed — devam kickoff

> Bu dosya O-21 (Agent SSE sequence replay) slice'ının kapanış handoff'udur.
> **En altta paste-ready resume prompt var** — temiz bir oturuma onu yapıştır.

## Nerede duruyoruz

- **PR [#430](https://github.com/alimirbagirzade/Entropia/pull/430)** — `feat/o21-agent-sse-sequence-replay`,
  commit `24a93d5`. **CI 6/6 yeşil, merge BEKLİYOR** (self-merge kapalı → kullanıcı merge eder).
- **Migration yok** (O-21 hiçbir migration eklemez), `ENGINE_VERSION` sabit. Branch `0035` üzerine
  kuruldu; **main bu arada `0039_backtest_run_cancellation`'a ilerledi** (O-06 #419) — #430'u merge
  etmeden önce güncelliği kontrol et.
- Tam kayıt: `docs/PROJECT_HISTORY.md` → "O-21 — Agent SSE sequence replay".
  Handoff girdisi: `docs/STAGE2_HANDOFF.md` → "O-21 — SSE akışı `Last-Event-ID`'den resume ediyor".

## Slice'ın geride bıraktığı reuse anchor'ları (tam sembol adlarıyla)

| Sembol | Dosya | Ne işe yarar |
|---|---|---|
| `looks_like_id(value, *, prefix)` | `backend/src/entropia/shared/ids.py` | Bir id'nin `new_id(prefix)` biçiminde olup olmadığı (prefix + 26 Crockford base32). **Client'tan gelen herhangi bir id'yi sorguya sokmadan önce burayı kullan** — alfabeyi yeniden türetme. |
| `Subscriber` (`.queue`, `mark_overflowed`, `take_overflow`) | `apps/api/sse.py` | Abone mailbox'ı + **overflow bayrağı**. `SseHub.subscribe()` artık bare queue değil bunu döndürür. |
| `RESYNC_EVENT` / `HEARTBEAT_EVENT` / `_control_frame` | `apps/api/sse.py` | Taksonomi **dışı** kontrol çerçeveleri. `_control_frame` id yazmaz — cursor'ı ilerletmemeleri buna bağlı. |
| `requested_cursor(request)` | `apps/api/sse.py` | `Last-Event-ID` okuma + doğrulama. Bozuk değer → `None` = live-only. |
| `replay_after(cursor, *, limit)` | `apps/api/sse.py` | `(events, resync_required)`. Kısa session açar, `limit+1` ile pencere taşmasını saptar, hata → `([], True)`. |
| `REPLAY_LIMIT` / `_SUBSCRIBER_BUFFER` | `apps/api/sse.py` | 500 / 256. Modül sabiti — settings'e bağlı değil (bilinçli). |
| `STREAM_RESYNC` | `frontend/src/lib/sse.ts` | Frontend karşılığı; `EVENT_QUERY_KEYS`'te **yoktur**, tam refresh'e bağlanır. |
| `_StubRequest` / `_SessionFactory` / `_wait_subscribed` | `backend/tests/integration/test_sse_replay.py` | SSE generator'ını deterministik sürmenin yolu: gerçek Starlette `Headers`, testin kendi session'ı, abonelik beklemesi. Yeni bir stream testi yazacaksan bunları kopyala. |

## Dokunulmaması gerekenler (bu slice'ın sınırı)

- **SSE taksonomisi ve `EVENT_QUERY_KEYS` eşlemesi** — değişmedi, değişmemeli.
- `AgentEvent.seq` **wire cursor değildir**; docstring'i artık bunu söylüyor. `/events` outbox
  fan-out'udur, heterojendir; agent-only bir sequence onu sıralayamaz.
- İkincil `GET /agent-events/stream` yalnız heartbeat üretir ve frontend'de bağlı değildir.
  `repositories/agent_lab.py::events_after` / `latest_event_seq` **hâlâ çağrısızdır**.

## Buradan mantıklı devam adayları (hiçbiri başlatılmadı)

1. **`/agent-events/stream`'i ya bağla ya kaldır.** Bugün ölü bir yüzey: rol kapısı var, olayı yok,
   tüketicisi yok. Bağlanacaksa `agent_event.seq` + `events_after` ile gerçek bir replay'i hak eder —
   ama abone başına DB yoklaması eklemeden (ana akışın tek-process poller'ı gibi bir fan-out lazım).
2. **`REPLAY_LIMIT` / `_SUBSCRIBER_BUFFER`'ı settings'e taşı** — üretimde ayar gerekirse.
3. **`Last-Event-ID`'yi OpenAPI'de belgele** — `Header(...)` parametresi eklemek ölü imza alanı
   yaratır; alternatif, route'a bir `openapi_extra` ile parameters girdisi eklemek. Drift guard
   snapshot'ı yenilemeyi ister (`make openapi`).
4. **PO imzası + R2 kapanışı** — proje düzeyindeki asıl blokaj (aşağıya bak).

## Ortam tuzağı (her oturumda geçerli)

Paralel worktree oturumları paylaşılan `entropia_test` DB'sini ezer (`conftest` her testte
`drop_all`/`create_all`). **`TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan:**

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug>_test"
```

Tam suite koşusunu **ortada öldürme** — artakalan bağlantılar DDL'i `ACCESS EXCLUSIVE` lock-wait'e
sokar ve sonraki koşuda düzinelerce sahte FAILED üretir (O-02'de 51 tane görüldü).
Frontend suite'i makine yükü altında flaky: `npx vitest run --testTimeout=20000` kullan, tek tük
timeout görürsen o dosyayı izole koş ve stash'li baseline ile kıyasla.

---

## Paste-ready resume prompt

```
Entropia — O-21 (Agent SSE sequence replay) landed, PR #430 CI 6/6 yeşil, merge bekliyor.
Session START protokolünü uygula: git fetch + git log --oneline origin/main -6 +
gh pr list --state all → #430'un merge olup olmadığını ÖNCE doğrula (handoff STALE-BY-DEFAULT).

Oku (otorite sırası): docs/O21_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md ("O-21 … landed" +
"Next") → docs/PROJECT_HISTORY.md "O-21 — Agent SSE sequence replay" (ayrıntı gerekirse, hedefli
oku) → docs/CODEMAPS/JOBS_AND_EVENTS.md §"Kayıp toleransı + resume (INF-11 + O-21)".

Durum: O-21 migration eklemez (main head 0039_backtest_run_cancellation). SSE artık resumable —
GET /events her veri çerçevesinde id: (outbox satır id'si) yayınlar, Last-Event-ID header'ından
replay eder (looks_like_id ile biçim doğrulama, REPLAY_LIMIT=500), buffer taşması / aşırı geniş
boşluk / replay hatası durumunda stream.resync yayınlar. Taksonomi ve EVENT_QUERY_KEYS DEĞİŞMEDİ.
Frontend native EventSource kullanamaz (AUTH-11 header kimliği → fetch stream), cursor'ı kendi
tutar; full-refresh fallback olarak korundu.

Dokunma: SSE taksonomisi, EVENT_QUERY_KEYS, OCC token'ları, Idempotency-Key.
Açık: ikincil /agent-events/stream hâlâ yalnız heartbeat + frontend'de bağlı değil;
repositories/agent_lab.py::events_after / latest_event_seq hâlâ çağrısız.

Proje düzeyindeki asıl blokaj değişmedi: product-owner imzası —
docs/implementation/v18_final_acceptance.md §4 (D-1…D-9). İmza olmadan R2 RE-OPENING banner'ı
kalkmaz. O-serisinin geri kalanı merge oldu (O-01/03/04/05/06/08/09/10); açık kalan tek slice #430.

Backend verify: cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && uv run pytest --no-cov -q  (TEST_DATABASE_URL ile İZOLE DB kullan).
Frontend verify: npm run typecheck && npm run lint && npx vitest run --testTimeout=20000.
```
