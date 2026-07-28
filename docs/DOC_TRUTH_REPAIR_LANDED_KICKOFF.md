# Doc Truth-Repair landed (PR #415) — Kickoff & Resume

> **Authority order:** `CLAUDE.md` §Current position > `docs/STAGE2_HANDOFF.md` §Next > bu doc.
> Her değer **STALE-BY-DEFAULT** — §Session START adım 1'i çalıştırmadan hiçbirine güvenme.
> Bu dosyanın kendisi de o kurala tabidir: aşağıdaki ölçümler `origin/main` @ `f78404f`
> (2026-07-28) içindir.

## Nerede duruyoruz

**PR #415 (docs truth-repair) merged** — `36957ad`. Dört authority dokümanı `origin/main`'e karşı
yeniden ölçüldü ve düzeltildi. Kod, migration, `ENGINE_VERSION` **dokunulmadı**; CI 6/6 yeşil.

**Ama dikkat:** #415 merge olduktan sonra main **14 PR** daha aldı (#416–#429). Yani #415'in
yazdığı §Current position bile bir gün içinde yeniden bayatladı — bu slice'ın en önemli dersi bu.

## Bu slice'ın ampirik bulguları (yeniden kullanılabilir)

Denetimin **kendi promptu da bayattı**. Üç iddia doğrulamada tutmadı:

| İddia | Gerçek |
|---|---|
| CLAUDE.md'de `658db36` + "F-05 (PR bekliyor)" | Bu metin dosyada **hiç yoktu** — o kısım zaten güncelmiş |
| DATA_MODEL "63 → gerçek **100**", gövde 99'u adlandırıyor | Gerçek **102**; gövde **101**'ini adlandırıyordu |
| S-L1 satır kayması `964 → 1034` | Gerçek `964 → **1277**` |

**Ders:** "şu dosyada şu yazıyor, düzelt" biçiminde gelen bir görevde **önce dosyada gerçekten
o metnin olduğunu doğrula**. Prompt, handoff kadar bayatlar.

## Ne bıraktı — reuse anchor'ları

- **`docs/CODEMAPS/DATA_MODEL.md`** — artık **102 tablonun tamamını** adlandırıyor
  (`rationale_family_revision` kendi satırında; eskiden `_root / _revision` kısaltmasının
  arkasında greplenemezdi). İki yeniden-üretme komutu dosyanın içine gömüldü:
  - tablo sayısı: `grep -rh __tablename__ backend/src/entropia/infrastructure/postgres/models/ | sed 's/.*= *//' | tr -d '"' | sort -u | wc -l`
  - FK sayısı: `grep -rh "ForeignKey(" backend/src/entropia/infrastructure/postgres/models/ | wc -l`
- **FK gerçeği düzeltildi:** doküman "yalnızca **8** açık `ForeignKey`" diyordu (altında 9 satır
  listelerken). Gerçek **134 bildirim / 25 model dosyası**. **L1 FK insert-order proof kuralı
  DEĞİŞMEDİ** — gerekçesi değişti: çok sayıda cross-aggregate `*_id` hâlâ DB constraint'siz
  mantıksal bağ olduğu için insert sırası şemadan bütünüyle türetilemiyor.
- **`docs/STAGE_R3_KICKOFF.md`** — **SUPERSEDED banner**'lı. Authority order'da 1. sırada
  okunuyordu ve merged beş kalemi (#375–#379) "sıradaki iş" diye listeliyordu. §"Working-loop
  method" bölümü **korundu** (hâlâ geçerli); §"Paste-ready resume prompt" **yapıştırma** olarak
  işaretlendi (bayat `0035_portfolio_rules` + `-capability-matrix` beklentileri).
- **`docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md`** — §DURUM TAZELEME tablosu: **8 madde landed**
  (S9/S1/S8/S4/S6/S2/S3/S7), **gerçekten açık** olanlar ayrıldı: **S5 (a/b/c/d)** + **S-L1…S-L6**.
  S-L7 fix değil **karar** olarak kapandı (`nav.test.tsx:95-96` yokluğu pinliyor).

## Dürüst sınır

`docs/audit/audit_report.md` **yok** — çalışma ağacında da git geçmişinin tamamında da
(`git log --all --diff-filter=A -- 'docs/audit/*'` boş). `STAGE2_HANDOFF.md` §O-03 zaten
yokluğunu kaydetmişti. Her düzeltme bu yüzden yeniden üretilebilir bir **komuta, PR numarasına
veya `file:line`'a** dayandırıldı. Denetimin "25+ kod" iddiasının #415 ile ilgisi yok.

## Sıradaki iş

1. **F-07 §4.4** — 4 yüzey backend display-DTO bekliyor (`v18_visual_traceability.md §4.4`).
   F-07 bütün olarak Complete DEĞİL.
2. **R2 banner kapanışı (docs işi):** `entropia_v18_remediation_status.md`'deki RE-OPENING
   banner'ının koşulu sağlandı (PO imzası 2026-07-22 + FIX(R3) hepsi landed) → banner'ı kaldır,
   UI satırlarını evidence'lı Complete yap.
3. **O-03 kalıntısı:** 5 ölü error sınıfı (`KNOWN_UNRAISED`).
4. **Round-3 backlog:** S5 (a/b/c/d) + S-L1…S-L6.

## Working-loop method

- **Her bulguyu ÖNCE ampirik doğrula** — hem kodda hem promptta. Bu slice'ta promptun 3 iddiası
  yanlış çıktı.
- Doküman slice'ında **kod DEĞİŞTİRME**; kapanışta `git diff --name-only | grep -v '\.md$'`
  boş olmalı.
- Bir sayı düzeltirken **yeniden üretme komutunu dosyanın içine göm** — sonraki oturum ölçümü
  tekrarlayabilsin, sana güvenmek zorunda kalmasın.
- Bir dokümanı "bayat" ilan ederken **hangi bölümünün hâlâ geçerli olduğunu da söyle**
  (R3 kickoff'ta working-loop korundu) — komple çöpe atmak bilgi kaybettirir.
- GateGuard: YENİ dosya heredoc ile → gate-free; mevcut dosyaya EDIT → 4-fact preamble.

## Paste-ready resume prompt

```
Entropia — doc truth-repair (PR #415) landed. Devam.

1) ÖNCE doğrula (bu prompt STALE-BY-DEFAULT): git fetch;
   git log --oneline origin/main -6; gh pr list --state all -L 10.
   Beklenen referans: main @ f78404f, alembic head 0039_backtest_run_cancellation (39),
   ENGINE_VERSION=backtest-engine-v18-funding-step-order, 102 tablo.
   BU DEĞERLER MUHTEMELEN DEĞİŞMİŞTİR — #415'ten sonra bir günde 14 PR indi.
2) OKU (authority order): CLAUDE.md §Current position + §Next, sonra
   docs/STAGE2_HANDOFF.md §Next, sonra dokunacağın alanın docs/CODEMAPS/ haritası.
   docs/STAGE_R3_KICKOFF.md SUPERSEDED — iş listesi olarak KULLANMA.
3) Sıradaki iş (öncelik sırasıyla):
   (a) F-07 §4.4 — 4 yüzey backend display-DTO (v18_visual_traceability.md §4.4);
   (b) R2 banner kapanışı — entropia_v18_remediation_status.md (PO imzası 2026-07-22'de
       atıldı, FIX(R3) hepsi landed, banner koşulu sağlandı);
   (c) O-03 kalıntısı: 5 ölü error sınıfı (KNOWN_UNRAISED);
   (d) POST_V1_SPEC_GAP_BACKLOG_ROUND3 §DURUM TAZELEME'deki açıklar: S5 (a/b/c/d) + S-L1…S-L6.
4) Sayı/satır referansı olan her iddiayı yapıştırmadan ÖNCE ampirik doğrula.
   docs/audit/audit_report.md YOK — kaynak diye referans verme.
5) Her slice: güncel main'den kendi branch'i + ayrı PR (base=main) + tam verify.
   Local Postgres :5432 (entropia/entropia); TEST_DATABASE_URL ile izole DB kullan.
```
