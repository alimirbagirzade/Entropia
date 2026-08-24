<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu kaydeder;
> SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir. Canlı kickoff artık
> `docs/ADIM103_LANDED_KICKOFF.md`.

# ADIM 102 LANDED — kabul borcu batch 23 (doc 16 Results History, backend): iki kriter kapandı, DOC 16 BİTTİ · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 102. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`43dc70d`** (`ADIM 101` / batch 22 = #814, doc 21 User Manual BACKEND). Dal
  kesilirken açık PR listesi **boş** döndü — son dört partinin kaydettiği gibi bu bir **garanti
  değil, anlık görüntüdür**. **Ürün kodu değişmedi** (`backend/src` altında sıfır satır); diff =
  iki yeni integration case + kabul defteri + üretilmiş artefaktlar. Migration yok, OpenAPI
  değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `RH-13` (c2) · `RH-14` (c3)** — doc 16'nın BACKEND yüzeyi. İkisi de kendi
  kriterinin son açık clause'uydu → ikisinin de `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 64 → 62, `debt_class.B` 32 → 30**; açık borç **71 → 69**
  (A=1 · B=30 · C=6 · D=32).
- **Doc 16 = 16 covered / 0 partial — HER SINIFTAN sıfır açık borç. Belge BİTTİ.** Bu partinin
  seçim gerekçesi buydu: doc 16'nın açık iki satırı da sınıf B, ikisi de backend, ikisi de tek
  clause; ikisini kapatmak bir belgeyi **bitirir**.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_result_row_immutability.py` — dosyanın sonundaki
  **"Acceptance batch 23"** bölümü. Üç yeniden kullanılabilir parça:
  - **`_history_digest(session, actor, result_id)`** — Results History'yi listeler ve TEK bir
    result'ın `key_metrics` digest'ini **`expire_all()` sonrası** döndürür. *"History satırı
    kıpırdamadı"* iddiası kuracak her slice bunu ödünç alabilir.
  - **`_apply_metric_profile(session, actor, codes)`** — kişisel profil revizyonu uygular ve
    komutun **GERÇEKTEN persist ettiği** seçimi geri okuyup döndürür (istediğini değil). Bir
    komutun sessizce genişlettiği bir seçim testi vacuous yapardı; bu yardımcı onu kapatır.
  - **`_seed_agent(session)`** — `Principal(AGENT)` + `AgentRuntime(ALPHA_AGENT_ID)`; agent
    gateway'i (`dispatch_tool_call`) bu modülden sürmek için gereken **tek** plumbing.
  - **Mevcut yardımcılar** `_snapshot` (her dayanıklı sütun), `_reread` (**`expire_all` + `get`**),
    `_manifest_snapshot`, `_checksums`, `_one_result`, `_count_audits` aynen kullanılabilir.
  - Dışarıdan ödünç alınanlar: `test_arrange_metrics::_seed_registry` (metrik REGISTRY'si — bir
    profil revizyonu doğrulanmadan önce ŞART), `test_results_history::{_seed_result, _workspace,
    _seed_principals}`.
- **Negatif kontrol harness'i** — `run(name, edits, pytest_args)`: yamayı uygular, **diskte
  doğrular**, pytest koşar, `finally`'de geri yazar. Bu slice onu scratchpad'de tuttu; deseni
  `PROJECT_HISTORY.md` §ADIM 94'te, **düzeltilmiş doğrulayıcısı** §ADIM 102'de yazılı.
- **Ortam — bu container ÇIPLAK başladı** (**repo bile klonlanmamıştı**, `.venv` yok, cluster yok).
  Tam dizi:
  ```
  # repo yoksa: mcp add_repo + git clone --depth 1 <url> /home/user/entropia
  cd backend && uv sync --all-extras
  PGDATA=/var/lib/postgresql/entropia-data
  mkdir -p $PGDATA && chown postgres:postgres $PGDATA && chmod 700 $PGDATA
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -U postgres --auth=trust -E UTF8 --locale=C"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-p 5432' -w start"
  su postgres -c "/usr/lib/postgresql/16/bin/psql -p 5432 -U postgres -c \"CREATE ROLE entropia LOGIN SUPERUSER PASSWORD 'entropia';\""
  su postgres -c "/usr/lib/postgresql/16/bin/createdb -p 5432 -U postgres -O entropia entropia"
  cd backend && LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONUTF8=1 uv run alembic upgrade head
  ```
  **`LC_ALL=en_US.UTF-8` bu imajda alembic'i `UnicodeDecodeError` ile patlatır.** Alt küme
  koşarken kendi izole DB'ni ver:
  `export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_rh"`.
  Pytest alt kümesinde `--no-cov` kullan — proje `--cov-fail-under=90` taşır ve bir alt küme
  onu **her zaman** kırar; bu bir kırmızı DEĞİLDİR ama gerçek kırmızıyı gizler.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **`expire_all()` ELDEKİ HER NESNEYİ EXPIRE EDER, yalnız geri okuduğunu değil.** ADIM 100
   identity map'i *"geri okumadan önce `expire_all`"* diye kaydetmişti; **ters yönü de vardır**.
   `_reread` içindeki `expire_all` **task nesnesini de** expire etti ve sonraki `task.task_id`
   sync bağlamda lazy-load olup **`MissingGreenlet`** verdi. Kural: expire edici bir çağrıdan
   **ÖNCE** ihtiyacın olan skaler id'leri yakala.
2. **NEGATİF KONTROL DOĞRULAYICISI EKLEME YAMASINI REDDEDEBİLİR.** `assert new in after and
   old not in after` bir **değiştirme** varsayar; `new`, `old`'u İÇEREN bir **ekleme** yamasında
   bu koşul asla sağlanamaz → sahte *"patch NOT applied"*. Doğrusu `after.count(new) == 1`.
   Harness'in yanlış alarmı sessiz bir yeşilden iyidir, ama **doğrulayıcı da test edilmelidir**.
3. **BİR ÖNCEKİ SLICE'IN "ERTELENDİ" GEREKÇESİ BAYATLAR — YENİDEN ÖLÇ.** ADIM 55, `RH-14.c3` için
   *"capability registry'yi Limited'a yürütmek gerekir"* yazmıştı; bu **yanlış fonksiyona**
   (`commands/capability.create_analysis_artifact`) aitti. Kriterin adlandırdığı yol agent
   gateway'in **`artifact.create`**'idir ve capability-gated **değildir**. Gereken tek plumbing
   bir `Principal` + `AgentRuntime` + bir task satırıydı. *"Şu yüzden pahalı"* diyen her not
   yeniden ölçülmelidir.
4. **VACUITY'Yİ İKİ YÖNDE KAPAT.** *"X değişmedi"* iddiasında iki ayrı boşluk vardır: X'in
   **gerçekten dolu** olması (beş `None` kendine eşittir ve hiçbir şey kanıtlamaz) VE kusuru
   tetikleyecek eylemin **gerçekten yapılmış** olması (persist edilen seçim anahtar metrikleri
   gerçekten dışlamalı). İkisi de eşitlik iddia edilmeden ÖNCE assert edilir.
5. **GÖLGEYİ ÖNCE KALDIRMAYA ÇALIŞ (ADIM 101), SONRA ÖLÇ.** Bu partide her iki kontrolde de
   hedeften önceki non-vacuity assertion'ları **geçti** — yani gölge yoktu ve bu **ölçüldü**,
   varsayılmadı.

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **Bitmiş belgeler/yüzeyler:** doc 05 · doc 18 · doc 10 · doc 22-BACKEND · doc 02-BACKEND ·
  doc 17-BACKEND · doc 01-BACKEND · doc 14-BACKEND · doc 21-BACKEND · **doc 16 TAMAMEN (bu slice)**.
- **Kalan sınıf-B yoğunluğu (30 satır):** doc 09 (ESP: `ESP-03` gerçek seeder'ı hiç çağrılmıyor,
  `ESP-05` resolver payload koruması, **`ESP-20`** yabancı aktörle rol filtresi — defter satırı
  kapatma reçetesini **birebir** yazıyor: user_2'nin PRIVATE proposal'ı + bir SYSTEM resolver
  seedle, user_1'in listesinde yalnız system satırı çıksın ve `get_esp_detail` foreign root'ta
  `AccessDeniedError` versin) · doc 06 (CP: `CP-09` Send replay'i hiç iki kez sürülmüyor,
  `CP-13` Supervisor/Agent approval-request izni, `CP-03` UI yarısı) · doc 20 (**`TR-08.c4`** —
  `UM-08.c5`'in birebir ikizi: restore `add_outbox_event` çağırıyor ama test yalnız
  `AuditEvent.event_kind` okuyor, `OutboxEvent` restore yolunda **hiç sorgulanmıyor**; doc 20'de
  `TR-07` bir bulgu olduğu için belge bitmez) · doc 08 (`PL-07` pinlenmiş indicator revizyonu) ·
  doc 03 (`AOS-04`/`AOS-06` — ikisi de bulgu, DOKUNMA).
- **`UM-15.c3`** doc 21'i, **`RC-09.c3`** doc 14'ü bitirir ama ikisi de **FRONTEND**
  (`cd frontend && npm ci`).
- **En ucuz satır: `TR-08.c4`.** `_event_trail`/`_latest_outbox` deseni (§ADIM 101 çapaları)
  doğrudan uygulanır ve bu slice'ın `_snapshot`/`_reread` çifti restore yolunda zaten kullanılıyor
  (`test_result_row_immutability::test_restore_preserves_artifact_checksums_and_writes_its_audit_row`).

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
ENTROPIA V18 — kabul borcu (sıradaki parti)

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, numarayı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o 'batch [12][0-9]' | sort -u
  Açık PR'ları listele (gh yoksa: curl api.github.com/repos/<owner>/<repo>/pulls?state=open).
  # NUMARAYI başlıktan değil, açık PR'ların EKLEDİĞİ docs/ADIM<n>_*.md YOLLARINDAN ölç.
  Canlı kickoff = ilk satırında 'doc-status: current' olan EN YÜKSEK numaralı ADIM dosyası:
    for f in docs/ADIM*KICKOFF.md; do head -1 "$f" | grep -q 'doc-status: current' && echo "$f"; done
  Onu oku, bunu değil.

Bu prompt yazılırken main `43dc70d` üzerine ADIM 102 / batch 23 yazıldı (doc 16 Results History
BACKEND, RH-13 + RH-14 — doc 16 BİTTİ). Yine de kendin ölç.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: container ÇIPLAK başlayabilir — REPO BİLE KLONLANMAMIŞ olabilir, backend/.venv YOK,
  Postgres cluster YOK, ve container yeniden başlayınca Postgres DÜŞER.
  Kurulum dizisi: docs/ADIM102_LANDED_KICKOFF.md §çapalar.
  `alembic upgrade head` için LC_ALL=C.UTF-8 PYTHONUTF8=1 kullan — en_US.UTF-8 bu imajda
  UnicodeDecodeError verir. Alt küme pytest'inde `--no-cov` ver (proje --cov-fail-under=90
  taşır; bir alt küme onu HER ZAMAN kırar ve gerçek kırmızıyı gizler).
  `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     Kapsama zaten sevk edilmiş olabilir -> cite et, yazma (ADIM 88).
  3) Kriterin adlandırdığı davranışın sevk edildiğini üründe DOĞRULA. Üç şekli ayır:
     unshipped (D) · unconstructible (C) · unfalsifiable (işaretle, kapatma).
  4) "X kıpırdamadı" clause'unda İLK SORU: X test veritabanında GERÇEKTEN VAR MI? (ADIM 100)
     "Olay yazılıyor" clause'unda İLK SORU: onu OKUYAN bir test var mı? (ADIM 101)
     Bir önceki slice "ertelendi, çünkü pahalı" diyorsa: O GEREKÇEYİ YENİDEN ÖLÇ — ADIM 102'de
     yanlış fonksiyona ait çıktı ve engel hiç yoktu.

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN UYGULANDIĞINI DOĞRULA; geri yazmayı `finally`'ye koy —
     AMA `finally` süreç SIGTERM alırsa KOŞMAZ: her turdan sonra `git status` (ADIM 100).
     Doğrulama `after.count(new) == 1` olmalı — `old not in after` bir EKLEME yamasında
     asla sağlanmaz ve sahte alarm verir (ADIM 102).
  c. KIRMIZININ HANGİ ASSERTION'DA OLDUĞUNU OKU — ve o HEDEF assertion mı? Değilse KONTROLÜ
     REDDET, yenisini kur (ADIM 98). İlk kırmızı sonrakini GÖLGELER: önce gölgeyi KALDIRAN
     bir kontrol tasarla (ADIM 101 NC-4); kaldırılamıyorsa DEFTERE YAZ (ADIM 100).
  d. YEŞİL kontrol = yama uygulanmadı VEYA assertion totolojik. Bir yan etkinin YOKLUĞUNU
     iddia ediyorsan, önünde onu geri alan hiçbir şey olmamalı — rollback DE, identity map DE:
     integration session'ı `expire_on_commit=False` kurar, geri okumadan önce
     `session.expire_all()` (ADIM 100). AMA `expire_all` ELDEKİ HER NESNEYİ expire eder —
     ihtiyacın olan skaler id'leri ONDAN ÖNCE yakala, yoksa MissingGreenlet (ADIM 102).
  e. Bir GÖVDE iddiasını key lookup'la kurma — tam sözlük eşitliği ya da serileştirilmiş
     metne karşı substring taraması (ADIM 98/101).
  f. EZME ile EKLEME ayrı kusur sınıflarıdır: satır DEMETLERİNİ karşılaştır (ezme) VE tam
     sıralı LİSTELERİ karşılaştır (ekleme); `count(*)` ikisini de kaçırır (ADIM 100/101 —
     hazır yardımcı: `test_user_manual.py::_event_trail`).
  g. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  h. Kriterin SON clause'u kapanıyorsa KRİTER-DÜZEYİ `status`'ü de covered yap ve
     `debt_class`'ı KALDIR.
  i. YAML notu düz skalerse `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.
  j. EŞZAMANLILIK clause'u seçtiysen: iki AYRI engine/bağlantı + `asyncio.Barrier`, bariyer
     komuttan ÖNCE salınır (içeride salmak KİLİTLENİR). Hazır harness:
     `test_user_manual.py::_append_in_own_transaction`. Determinizmi İKİ YÖNDE ölç.
  k. VACUITY'Yİ İKİ YÖNDE KAPAT: iddia edilen şey gerçekten DOLU mu, VE kusuru tetikleyecek
     eylem gerçekten YAPILDI mı? İkisi de eşitlikten ÖNCE assert edilir (ADIM 102).

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RF-08.c2,
  TR-07.c3, RD-01.c4, RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4,
  AOS-04.c2, AOS-06.c2 + `unfalsifiable: true` clause'lar.
  Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ OLANLAR: doc 05 · doc 18 · doc 10 · doc 22-BACKEND · doc 02-BACKEND · doc 17-BACKEND ·
  doc 01-BACKEND · doc 14-BACKEND · doc 21-BACKEND · doc 16 TAMAMEN.
  Kalan sınıf-B yoğunluğu (yine de ölç): doc 09 (ESP) · doc 06 (CP) · doc 20 (TR) · doc 08 (PL).
  TR-08.c4 EN UCUZ satır: UM-08.c5'in birebir ikizi — restore `add_outbox_event` çağırıyor ama
  test yalnız `AuditEvent.event_kind` okuyor, `OutboxEvent` hiç sorgulanmıyor.
  ESP-20 defterde birebir reçeteli (yabancı aktörle liste + get_esp_detail).
  UM-15.c3 ve RC-09.c3 kendi belgelerini bitirir ama FRONTEND (`cd frontend && npm ci`).

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula. Merge edilmiş ad kazanır.
  TEST EKLEDİYSEN `generate_repository_facts.py --root ..` KOŞ — collection sayısı bayatlar
  ve README'nin gömülü bloğu da (ADIM 60, ADIM 100). Onu `uv run python` ile koş; çıplak
  `python3` `entropia` modülünü bulamaz (ADIM 102).
  `--write-report`/`--write-ledger` yolları `--root`'a GÖRE çözülür: `docs/audit/...` yaz,
  `../docs/audit/...` DEĞİL.
  PR AÇIKKEN main ilerlerse: sunucu tarafı "Update branch" DÜĞMESİNE DAYANMA. Dalı güncel
  main üzerine REBASE et; çakışmaları İKİ TARAFI DA KORUYARAK çöz (PROJECT_HISTORY ve
  STAGE2_HANDOFF'ta her iki blok kalır, üretilmiş dosyalar main'den alınıp YENİDEN ÜRETİLİR,
  kickoff demote zinciri bir kademe kaydırılır, gerekirse slice RENUMBER edilir).
  TAVANI TAŞIMA, TAZE BİR --report'tan YENİDEN ÖLÇ.
  Sonra `--report --check-generated --ratchet` + `grep -c '^## ADIM'` (düşmemeli).

  NOT: git guard, komut dizesinin TAMAMINDA "force push" + "main" deseni görürse bloklar —
  fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.

  PR'ı main'e aç. Merge kararı insanındır — aksi açıkça söylenmediyse MERGE ETME.
```
