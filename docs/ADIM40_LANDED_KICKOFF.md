<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 40 landed — devir belgesi (RC §6.7 / P1-B1+B2 + P8-B1+B3)

**PR pending** · branch `docs/rc-p1-p8-stale-counts` · base `66bdeb4` (ADIM 39, #665).

> **Numaralandırma uyarısı.** Bu slice'a giden istem kendini "ADIM 38" olarak adlandırıyor ve
> base olarak ADIM 37b'yi varsayıyordu. `origin/main` doğrulandığında **ADIM 38 (#664) ve
> ADIM 39 (#665) zaten merge edilmişti** → numara yeniden kullanılmadı. Merge edilmiş PR
> başlıkları ve commit mesajları değiştirilemez; yeniden numaralandırma belgeleri git
> geçmişinden ayırırdı. Bu kayıt **ADIM 40**'tır.

---

## 1. Nerede duruyoruz

RC §6.7'nin dört belge kalemi kapandı: **P1-B1, P1-B2, P8-B1, P8-B3**. Hiçbiri blocker
değildi. **Blocker sayısı üç, §8 verdict BLOCKED. P8 KAPANMADI** — P8-B2 açık.

Kapatma yöntemi kalemlerden daha önemli: **sayı güncellenmedi, sahibi değiştirildi.** Bu, elle
yazılmış bir sayının bayatladığı üçüncü kayıttı ve ADIM 27'nin doküman-gerçek kapısı hiçbirini
yakalamamıştı — o kapı **üretilmiş** olguları koruyor, bu sayılar elle yazılmış düzyazıydı.

## 2. Bu slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

| Çapa | Ne işe yarar |
|---|---|
| `scripts/generate_repository_facts.py::collect_backend_layers` | `application/{commands,queries,jobs}` modül adları + sayıları, `domain/` paketleri. **Sayıyı düzyazıya yazma** — bu collector'ın çıktısına işaret et. |
| `scripts/generate_repository_facts.py::check_codemap_coverage` | **Yeni kapı.** Her application modülünün BACKEND_LAYERS.md satırı, her `@dramatiq.actor`'ın JOBS_AND_EVENTS.md satırı **ve kuyruğu**. `--check` yolunda, `ci.yml`'ın mevcut adımında koşar. |
| `scripts/generate_repository_facts.py::_layer_section` | Katman bölümüne **kapsamlı** arama. `market_data.py` üç katmanda birden var; bütün-dosya eşleşmesi eksik satırı örterdi. |
| `docs/generated/repository_facts.md` §Summary ▸ *Application modules* | Üç katman sayısının + domain paket sayısının **tek** sahibi. |
| `docs/CODEMAPS/BACKEND_ROUTES.md` §DUAL-TOKEN | Dual-token op sayısının **tek** sahibi (tek tek sayan liste, **17**). `CLAUDE.md` artık sayı taşımıyor. |
| `backend/tests/contract/test_repository_facts_guard.py` (son bölüm) | Yeni kapının **negatifi**: 5 kapı testi + 1 türetme testi. Yeni bir codemap kuralı eklerken deseni buradan kopyala. |

## 3. Bir sonraki kişinin BİLMEK ZORUNDA olduğu üç şey

**(a) Sayı, kendisini bayatlatan kusuru göremez.** `BACKEND_LAYERS.md` başlığı `jobs` için 14
diyordu; gerçek 16'ydı **çünkü tabloda iki modülün hiç satırı yoktu** (`delivery.py` — ADIM 21
at-least-once teslim kapısı, `heartbeat.py` — ADIM 25 worker canlılığı). Raporun *"içerik
olarak tam"* ifadesi **yanlıştı**. Bu yüzden kapıya bağlanan şey sayı değil **üyelik**tir.

**(b) Yeni bir application modülü veya dramatiq aktörü eklersen codemap satırı ZORUNLUDUR.**
CI kırmızıya döner. Sayı yazmana gerek yok, hatta yazma. Aktör satırında **kuyruk** da
doğrulanır: `data` scheduler sweep'inin **dışındadır**, yanlış kuyruk kayıp mesajın geri gelip
gelmediğini yanlış anlatır.

**(c) Satır numarası yazma.** `JOBS_AND_EVENTS.md` aktör tablosunun "Satır" kolonu silindi
(12 değerin 11'i bayatmıştı). Sembol adı kullan: `dosya.py::sembol`. Aynı dosyanın
**gövdesinde** hâlâ ~30 `:NN` referansı var (**P8-B3b**) — onlara güvenmeden önce grep'le.

## 4. Açık kalanlar (bu slice KAPATMADI)

1. **P8-B2** — Create-Package durable admission uçları **200**, diğer dokuzu **202**. Belge
   sapması **değil**: wire contract'ı ve muhtemelen frontend'i etkileyen çözülmemiş bir **API
   sözleşmesi**. doc 06'nın kendi §-taksonomisi otoritedir ve **bu koşuda da okunmadı**.
   → **ayrı PR + ürün kararı**.
2. **P8-B3b (YENİ)** — `JOBS_AND_EVENTS.md` gövdesindeki ~30 `:NN` referansı. Ölçüldü,
   düzeltilmedi; her biri ayrı doğrulama ister → ayrı PR.
3. Yeni kapı **satır numarası doğrulamıyor**. Diğer codemap'lerdeki `dosya.py:NN` referansları
   (`BACKEND_LAYERS.md` `config.py:118-119` gibi) bu koşuda **ölçülmedi**.
4. Dört blocker ekseninde hiçbir şey değişmedi: A-08, kabul akışları, Alertmanager artıkları,
   react-router freeze. **P11-1** (branch protection) hâlâ **insan işi**.

## 5. Yöntem — çalışma döngüsü

1. `git fetch` + `git log origin/main` + `gh pr list --state all` → **istemin base varsayımını
   doğrula** (bu slice'ta yanlıştı).
2. Her kalemi **kodun kendisinden** yeniden ölç; rapordaki sayıyı kopyalama (rapor da bayat
   olabilir — bu koşuda raporun bir cümlesi çürütüldü).
3. Merdiveni sırayla sor: **1** üretilene işaret et → **2** üretime ekle → **3** bayatlamayacak
   biçimde elle yaz. İlk uyanı seç, seçimi ve nedenini **yaz**.
4. Kapı eklediysen **negatifini kanıtla** (kapıyı kıran sentetik ağaç + test).
5. Kapanış: `cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check`
   ve tam suite. Docs PR'ında merge öncesi:
   `git diff origin/main -- docs/ | grep '^-## '` → **BOŞ OLMALI**.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 41: RC §6.7 — sıradaki kalem

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 40 merge olmuş OLMALI; olmadıysa DUR.
      İstemdeki ADIM numarasına GÜVENME, `git log --oneline origin/main -8` +
      `gh pr list --state all` ile gerçek son slice'ı bul.)

ÖNCE OKU
  · docs/ADIM40_LANDED_KICKOFF.md (bu belge — REUSE çapaları §2, açık kalemler §4)
  · docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 tablosu + §6.7.8
  · docs/STAGE2_HANDOFF.md §ADIM 40 + §Next

AÇIK KALEMLER (birini seç, HEPSİNİ birden alma)
  · P8-B2  — Create-Package durable admission 200 ↔ diğer dokuz 202.
             BELGE İŞİ DEĞİL: wire contract + ÜRÜN KARARI. doc 06 §-taksonomisini
             ÖNCE oku (bu güne dek hiçbir koşuda okunmadı). Karar gerekiyorsa
             kullanıcıya sor, tek başına adjudicate ETME.
  · P8-B3b — JOBS_AND_EVENTS.md gövdesindeki ~30 `:NN` referansı → sembol adı.
             Her referansı TEK TEK doğrula; toplu sed YAPMA.
  · P11-6b — a11y tab-sırası sondası Tab'a hiç basmıyor (yeni modelleme kararı).
  · P11-8  — Lighthouse bağlı değil.
  · P10-7  — latency ratio gate (5 gecelik baseline gerekiyor).
  AGENT İŞİ DEĞİL: P11-1 (branch protection — repo ayarı), dört blocker.

ÇEKİRDEK İLKE (ADIM 40'tan devralınan, pazarlıksız)
  Bir sayıyı elle güncellemek onu yeniden bayatlatır. Merdiveni sırayla sor:
    1) Zaten repository_facts.md'de üretiliyor mu? → sayıyı SİL, işaret et.
    2) Üretilebilir mi (ucuzsa)? → generate_repository_facts.py'ye ekle.
       Mevcut kural kimliklerini ve regex'lerini BOZMA.
    3) Üretilemiyorsa → bayatlamayacak biçimde yaz (mutlak sayı ve dosya:satır YOK,
       tek kanonik yere referans).
  Satır numarası yazma; sembol adı kullan (`dosya.py::sembol`).
  Yeni modül / yeni dramatiq aktörü eklersen codemap satırı ZORUNLU —
  check_codemap_coverage CI'da kırmızıya çevirir.

TAVİZ VERİLEMEZ
  · Kapı eklersen NEGATİFİNİ kanıtla (kapıyı kıran sentetik ağaç + test).
  · Yeşile zorlama YOK: kapı kırmızıysa BLOCKED yaz.
  · Blocker sayısı DEĞİŞMEZ; verdict BLOCKED KALIR. "READY" YAZMA.
  · Docs PR'ı EN YÜKSEK RİSKLİ tiptir (repoda ÜÇ KEZ kayıt sildi):
      git diff origin/main -- docs/ | grep '^-## '   → BOŞ OLMALI
  · CLAUDE.md §Current position 5–6 satır kalır — slice anlatısı PROJECT_HISTORY.md'ye.

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi.
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  · cd backend && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree>_test uv run pytest
```
