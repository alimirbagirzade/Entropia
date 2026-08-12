<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 49 LANDED — P11-1: main'de required status check ruleset'i · sıradaki slice için kickoff

## Neredeyiz

RC §6.7 tablosunun **repo dışı** tek kalemi kapandı. PR #683 (`74bbd70`) hazırlığı
getirdi; **ayarı insan uyguladı** → ruleset `20765617`, `enforcement: active`,
2026-08-12T23:14:40+03:00. Öncesi ölçülmüştü: `GET /rulesets` → `[]`,
`GET /rules/branches/main` → `[]`, `branches/main` → `enforcement_level: "off"`.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** P11-1 bir RC §6.7
tablo kalemiydi, blocker değil. Bu slice A-08'e **dokunmadı**.

## Bu slice ne bıraktı (reuse anchor'ları, tam adlarıyla)

| Anchor | Ne yapar |
|---|---|
| `.github/rulesets/main-required-status-checks.json` | Ruleset gövdesi. 16 context, hepsi `integration_id: 15368`. **GitHub bu yolu otomatik OKUMAZ** — dosya istek gövdesi + ayarın versiyonlanmış kaydıdır. |
| `scripts/required-checks-preflight.sh` | POST öncesi **zorunlu** salt-okuma kapısı. Payload'ı GitHub'ın **ürettiği** check adlarıyla diff'ler; göremediği veya **iki workflow'dan gelen** adı `FATAL` + `exit 1` yapar. `<pr-no>` argümanı alır. |
| `docs/implementation/required_status_checks_setup.md` | Runbook: §2 sınıflandırma · **§2.1 Lighthouse kararı** · §3 komut (alan alan) · §4 arayüz · §5 uyarılar · §6 geri alma · §7 bakım sırası. |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Required check adını ELLE YAZMA.** Ada göre eşleşir ve GitHub adın bir karşılığı
   olduğunu **doğrulamaz**. Karşılığı yoksa check hiç oluşmaz → PR
   `Expected — Waiting for status to be reported` üzerinde **sonsuza kadar** asılı kalır.
   Bu repodaki adlar em dash (`—`), `§`, parantez ve matrix açılımı taşıyor.
   **Payload ölçümden üretilir, `required-checks-preflight.sh` POST'tan önce koşar.**
   Negatifi kanıtlı: em dash yerine tire → `FATAL`; çift üretilen ad → `FATAL`.
2. **`skipped` ≠ "hiç oluşmadı".** `if:` ile atlanan job yine de `skipped` check **yazar**
   (5 nightly/manual job yazdı). Ölümcül olan check'in **hiç oluşmaması**dır: yanlış ad
   ya da PR'da tetiklenmeyen workflow. **Yeni workflow'a `paths:` filtresi eklersen o
   check required listesine GİRMEMELİ** — filtreye uymayan PR'da hiç üretilmez ve kilitler.
   Bugün beş workflow'un hiçbirinde `paths:` yok; kurulumun güvenli olmasının koşulu bu.
3. **Yeni kapı eklerken sıra: önce merge, sonra required.** Adın en az bir kez
   **gerçekten üretildiğini** gör, sonra payload'a ekle ve `PUT …/rulesets/20765617`.
   Ters sıra kilitler. `name:` değiştirirken de aynı sıra — `name:` değişimi **kapıyı
   sessizce açar**.
4. **Lighthouse çırpınırsa taban İNDİRİLMEZ.** Skor `LH_REPEATS` geçişin **medyanı**
   (varsayılan 3) → ilaç **tekrar sayısı**. **`armed: false` + boş `floors` spec'i
   GEÇİRİR** — required olduktan sonra bu bayrak kapının **sessiz kapatma düğmesidir**;
   bir PR'da `false`'a dönüyorsa o bir düzeltme değil, kapının kaldırılmasıdır.
   Tabansız rota (`TARGET_PAGES`'te var, `floors`'ta yok) **FAIL** verir.
5. **`pull_request` kuralı taşıyıcıdır, süs değil.** Required status check'ler yalnız
   **PR merge'ini** kapsar; o kural olmasa `git push origin main` on altısını da atlardı.
   `required_approving_review_count: 0` bilinçli — tek kişilik repoda `1` kalıcı kilittir.

## Kapatılmayan, kapatıldığı iddia EDİLMEYEN

- **A-08** — ekran okuyucu denetimi yapılmadı, defter **boş (0/4)**, #514 kapalı.
  Buradaki hiçbir check A-08 kanıtı **değildir**. Blocker 1, verdict **BLOCKED**.
- **Ruleset drift kapısı YAZILMADI.** Ruleset **repoda değil**; silinirse ya da
  `Disabled` yapılırsa **hiçbir CI kapısı fark etmez**. Tek iz `PROJECT_HISTORY` §ADIM 49.
  Canlı ruleset'i `.github/rulesets/*.json` ile karşılaştıran bir job **açık iştir**
  (`required-checks-preflight.sh` bunun yarısını zaten yapıyor; eksik olan canlı
  ruleset'i çekip diff'leyen bir CI adımı — ama admin token ister, bu da ayrı bir karar).
- **`bypass_actors` bağımsız doğrulanamadı** — GET yanıtı salt-okuma token'ına bu alanı
  vermiyor. Kanıt POST yanıtındaki `[]` + `current_user_can_bypass: "never"`.
- **Çıplak `CodeQL` required DEĞİL** (Tier 2). Farklı app (`57789`), PR-only, alert
  triage semantiği. Deterministik kapı isteniyorsa ayrı bir karar gerekir.
- **RC §6.7'de kalanlar:** P11-6b · P11-3b · P8-B3b · P4-3 · P10-B6 · P1-Gate3 ·
  P10-B3/B4/B5. **P11 hâlâ KAPANMADI** — P11-1 kapandı, P11-6b ve P11-3b açık.
- **Memory checkpoint YAZILAMADI** — `ecc`/`claude-mem` remote ortamda **kayıtlı değil**
  (#690 ölçtü; sorun oturum değil **ortam**). Borç **ADIM 47 + 48 + 49**, üç oturum.
  **İçerik hazır bekliyor:** `docs/memory/PENDING_CHECKPOINTS.md` — üç entity + üç
  observation, yapıştırmak yeterli, yeniden türetme. O dosya **kendini tüketir**:
  yazıldığında silinir. Kalıcı çözüm **insan kararı** (bkz. o dosyanın son maddesi).
- **`ADIM 48` numarası iki slice tarafından kullanıldı** (K-6b odak halkası **ve** kabul
  borcu sınıf B parti 01). `ADIM48_LANDED_KICKOFF.md` içinde iki H1 yan yana; CLAUDE.md'de
  iki "Son dalga — ADIM 48" bloğu; `STAGE2_HANDOFF.md` Next bloğunda tekrarlanmış bir satır.
  Bu slice **49** alarak çakışmayı büyütmedi. **Ayrıştırma insan kararıdır** — CLAUDE.md'nin
  kuralı: numaralar yeniden atanmaz, **başlık ekiyle** ayrılır.

## Bu slice'tan sonra çalışma şekli DEĞİŞTİ

- **main'e doğrudan push kapalı.** Docs PR'ları dâhil her şey PR'dan geçer.
- **Her PR 16 yeşil check ister**, `strict: true` yüzünden dal main ile güncel olmalı.
  `Backend — lint, type, test` **~48 dakika** (ölçüldü) → seri merge pahalı. Bu bilinçli
  bir bedel; gerekçesi (üç kez yaşanan bayat-base docs regresyonu) ve tek alanı çeviren
  komut runbook §3'te. **Dürüst sınır:** `strict` o regresyonu tek başına yakalamaz —
  hiçbir kapı `docs/` okumaz, `git show <sha> -- docs/ | grep '^-## '` kuralı yürürlükte.
- **Muafiyet yok, sahibi dâhil.** Kurtarma bypass aramak değil: ruleset `20765617` →
  `Disabled` ya da sil.

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice.

Session START protokolünü uygula: önce `git fetch` + `git log --oneline origin/main -6`
ile NE LANDED olduğunu doğrula (handoff STALE-BY-DEFAULT). Sonra sırayla oku:
docs/ADIM49_LANDED_KICKOFF.md (bu dosya) → docs/STAGE2_HANDOFF.md (§ADIM 49 + Next) →
docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*.

DURUM: P11-1 ADIM 49'da KAPANDI — main'de ruleset 20765617 aktif, 16 required check.
Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. RC §6.7'de kalanlar: P11-6b, P11-3b,
P8-B3b, P4-3, P10-B6, P1-Gate3, P10-B3/B4/B5.

ÇALIŞMA ŞEKLİ ARTIK FARKLI — bunu bilerek başla:
- main'e doğrudan push YOK. Her şey PR'dan geçer.
- Her PR 16 yeşil check ister ve dal main ile GÜNCEL olmalı (strict). Backend ~48 dk.
- Yeni bir CI job'ı eklersen: önce merge et, adın gerçekten üretildiğini gör, SONRA
  scripts/required-checks-preflight.sh <pr> koş ve
  gh api --method PUT /repos/alimirbagirzade/Entropia/rulesets/20765617 --input <payload>.
  TERS SIRA TÜM MERGE'LERİ KİLİTLER. Bir job'ın name: alanını değiştirmek de aynı sıra.
- Yeni workflow'a paths: filtresi eklersen o check required listesine GİRMEMELİ.

İLK İŞ (borç, üç oturumdur birikiyor): ecc + claude-mem bağlıysa ADIM 47, 48 ve 49 için
memory checkpoint yaz. Bağlı değilse bunu YAZILAMADI diye kaydet, "atlandı" deme.

Sonra sıradaki kalemi seç. Öneri: P11-6b veya P4-3 (ikisi de repo içi, ölçülebilir).
A-08'i kapatmaya çalışma — ekran okuyucu denetimi insan işidir; agent #514'ü kapatamaz.

Kod yazmadan önce: dokunacağın alanın docs/CODEMAPS/ haritasını oku, sonra
codebase-memory-mcp ile sembolleri bul. Kapanışta ritüelin ALTI maddesini de yap.
```
