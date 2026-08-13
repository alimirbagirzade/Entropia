<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge canlı slice kickoff'u DEĞİLDİR.** Aşağıdaki ölçüm
> 2026-08-12'de main `7dd1dfe` üzerinde alınmıştır; check adları, sayılar ve süreler
> o ana aittir. Güncel otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` ile kapılı).
> **Yordam yürürlüktedir, ölçüm bayatlayabilir:** POST'tan önce §3'ün ön kontrolünü
> koşun — bir job adı değiştiyse buradaki liste sizi kilitler, script durdurur.

# main — required status check kurulumu (RC §6.7 / P11-1)

> **UYGULANDI — 2026-08-12.** Ruleset **`20765617`** kuruldu (`enforcement: active`,
> `23:14:40+03:00`) ve doğrulandı: 16 ad + `integration_id` **sıra dâhil birebir**,
> `/rules/branches/main` **4 kuralı da etkin** gösteriyor, `strict: true`,
> `current_user_can_bypass: "never"`, **üretilmemiş ad YOK**. §1'in "main korumasız"
> ölçümü **artık tarihseldir** — POST öncesi durumu kaydeder, bugünkü durumu değil.
> Kurtarma/geri alma §6'da; **bakım sırası §7'de ve bağlayıcıdır**.
> Tam kayıt: `PROJECT_HISTORY.md` §ADIM 49.
>
> **BU BELGE HAZIRLIK OLARAK YAZILDI.** Repo ayarı değiştirmek agent yetkisinde
> değildir (bu oturumun token'ı `branches/main/protection` üzerinde `403` alıyor);
> aşağıdaki komutu **insan çalıştırdı**.

**Ölçüm tarihi:** 2026-08-12 · **Ölçülen commit:** `7dd1dfe` (main HEAD, PR #682) ·
**Payload:** `.github/rulesets/main-required-status-checks.json` ·
**Ön kontrol:** `scripts/required-checks-preflight.sh`

---

## 1. ÖLÇÜM — bugün main'de ne var

Üç sorunun ölçülmüş cevabı:

| Sorgu | Sonuç |
|---|---|
| `GET /repos/:owner/:repo/branches/main/protection` | **`403 Resource not accessible by integration`** — bu oturumun token'ı okuyamıyor |
| `GET /repos/:owner/:repo/branches/main` → `.protection` | **`enabled: false`**, `required_status_checks.enforcement_level: "off"`, `contexts: []` |
| `GET /repos/:owner/:repo/rulesets` | **`[]`** (boş) |

Beklenen `404` yerine `403` geldi — ama `branches/main` yanıtındaki `protection`
bloğu aynı gerçeği **doğrudan** söylüyor: `main` korumasız. Ruleset listesi de boş.
**Bugün main'e giden hiçbir şey engellenmiyor:** kırmızı CI ile merge edilebilir,
main'e doğrudan push edilebilir, main silinebilir.

Kontrol yüzeyi (ölçülen, elle yazılmamış): **5 workflow → PR'da 22 check**.
Beşinin de tetiği `push:[main] + pull_request:[main]` ve **hiçbirinde `paths:` /
`paths-ignore:` filtresi yok** (`grep -nE "paths|paths-ignore" .github/workflows/*.yml`
→ yalnız bir yorum satırı eşleşti). Bu, aşağıdaki kurulumun güvenli olmasının
**temel koşuludur**: path filtresi olan bir workflow, filtreye uymayan bir PR'da
check'i hiç üretmez ve required yapılmışsa o PR sonsuza kadar bekler. Bu repoda o
tuzak yok — ama yeni bir workflow'a `paths:` eklenirse **required listesine
girmemelidir** (bkz. §7).

---

## 2. SINIFLANDIRMA — hangisi merge'i durdurmalı

### Tier 1 — ZORUNLU (16 check)

Ölçütü tek: **readiness raporunda bloklayıcı diye kaydedilmiş bir kapıyı taşıyor mu,
ve kararı deterministik mi?** Kapıların çoğu ayrı bir check değil, bir job'ın
**adımı** — o yüzden sütun "hangi kapıyı taşıyor" diye okunmalı.

| Check adı (ölçülen) | Taşıdığı bloklayıcı kapı |
|---|---|
| `Backend — lint, type, test` | **coverage** (`pytest` + `--cov-fail-under=90`) · **docs-truth** (`generate_repository_facts.py --check`) · **şema paritesi** (`schema_parity_gate.py`, ADIM 34) · OpenAPI drift guard · acceptance traceability ratchet (ADIM 42) · **güvenlik** (`pip-audit`) · ruff + mypy |
| `Frontend — lint, typecheck, build, test` | **coverage** (`npm run coverage`, eşikler `vite.config.ts`) · **visual baseline platform gate** (ADIM 38 / P11-3) · **güvenlik** (`npm-audit-gate.mjs` + `security-allowlist.json`, ADIM 44) · lint + typecheck + build |
| `E2E — real browser vs. Docker Compose stack (F-23)` | **visual regression** — `npm run visual`, 23 rota (ADIM 39 / P11-2). **Ayrı bir check DEĞİL**, bu job'ın içinde koşuyor; görsel kapının bloklayıcı olması bu satıra bağlı |
| `A11Y — axe-core scan vs. the seeded stack (R2-14)` | **axe-core ratchet** |
| `Acceptance flows (a)-(e) — … (RC §6.2)` | **flows** — ADIM 45'te CI'ya bağlandı; "required status check olmadan bu kapı merge'i DURDURAMAZ" notu **tam olarak bu satırla** kapanıyor |
| `E2E — dev-auth acceptance (X-Actor-Id, no login)` | dev-auth kabul yolu |
| `Lighthouse — score ratchet vs. the seeded stack (RC P11-8)` | **Lighthouse ratchet**, 23/23 rota (ADIM 43). **İnsan kararıyla zorunlu (2026-08-12)** — aşağıdaki §2.1'e bakın |
| `Migration + provisioning acceptance` | migration + provisioning |
| `Fresh install from empty volumes` | boş hacimden kurulum |
| `Alert rules and notification path` | RC blocker 3 — fail-closed bildirim yolu (ADIM 31) |
| `Docker — build images` | iki imaj derleniyor; E2E/install job'ları aynı Dockerfile'lara dayanıyor |
| `CodeQL — python` | **güvenlik** (SAST, matrix bacağı) |
| `CodeQL — javascript-typescript` | **güvenlik** (SAST, matrix bacağı) |
| `Secret scan (gitleaks)` | **güvenlik** |
| `Container scan + SBOM` | **güvenlik** |
| `Load smoke — every scenario answers (PR gate)` | adı zaten "PR gate"; `if:` koşulu PR/push'ta koşacak şekilde yazılmış |

### 2.1 Lighthouse — kayda geçmiş karar (2026-08-12)

Lighthouse ilk taslakta Tier 2'ye ayrılmıştı; gerekçe **ölçüm varyansıydı**:
CLAUDE.md'nin kendi kaydı `panel-management` tabanının "98'de KALMALI (ölçülmüş
98–100 varyansı; 100'e sıkılaştırmak çırpınan kapı verir)" diyor, tarayıcı skoru
runner yüküne bağlı, ve donmuş kusurları (#677) hâlâ açık.

**İnsan kararı bunu zorunlu yaptı** — kalem Tier 1'e taşındı. Karar kaydedildi,
yeniden tartışılmaz. Kaydın taşıdığı asıl bilgi **çırpınma anında ne YAPILMAYACAĞI**:

- **Taban indirilmez, tolerans genişletilmez.** Bu CLAUDE.md'de zaten yazılı bir
  kuraldır (ADIM 43): "gürültü → `LH_REPEATS`/warm-up". Required olduktan sonra bu
  kuralın maliyeti artar — kırmızı artık merge'i durdurur, yani tabanı düşürme
  baskısı da artar. **Kapıyı gevşetmek, kapıyı kaldırmaktan daha kötüdür:** yeşil
  görünen ama hiçbir şey ölçmeyen bir kapı bırakır.
- **Gürültünün doğru ilacı `LH_REPEATS`.** Raporlanan skor `LH_REPEATS` geçişin
  **medyanı**dır (`21-lighthouse.spec.ts`, varsayılan `3`); tek bir gürültülü geçiş
  zaten medyanda erir. Çırpınma varsa **tekrar sayısını artır**, tabanı düşürme.
- **`armed: false` bu kapının sessiz kapatma düğmesidir — required olduktan sonra
  asıl risk budur.** `lighthouse-baseline.json` `armed: false` ve `floors` boşken
  spec **uyarı basıp geçer** (bootstrap durumu). Yani çırpınan bir kapıyı "kapatmanın"
  en kolay yolu, required check'i **yeşil** bırakırken hiçbir şey ölçmemesini
  sağlamaktır. Bir PR'da `armed`'ın `false`'a döndüğünü görürseniz bu bir düzeltme
  değil, kapının kaldırılmasıdır.
- **Tabansız rota da kırmızıdır.** `screenshotMatrix.ts::TARGET_PAGES` içinde olup
  `floors`'ta olmayan rota **FAIL** verir — "unbaselined route is a hole, not a pass".
  Yeni bir sayfa eklerken tabanını da ekleyin, yoksa merge'iniz durur.
- **`panel-management` performance tabanı 98'de kalır.** 100'e sıkılaştırma, artık
  merge'i durduran bir kapıda çırpınma üretir.
- **A11y kategorisi ASLA açılmaz** (axe otoritedir) ve Lighthouse'un hiçbir çıktısı
  A-08 kanıtı değildir. Required olması bunu değiştirmez.

Çırpınma gerçekten yaşanırsa doğru sıra: önce `LH_REPEATS`/warm-up ile gürültüyü
azalt; olmuyorsa §6'daki yolla ruleset'i **durdur** ve kalemi yeniden karara aç —
tabanı düşürerek yeşile boyama.

### Tier 2 — AYIRILDI, ayrı karar gerektiriyor (1 check)

| Check | Neden required listesinde değil |
|---|---|
| `CodeQL` (çıplak ad, app `github-advanced-security` / id `57789`) | **Farklı bir app üretiyor** (diğer 21'inin hepsi `github-actions` / `15368`) ve **yalnız PR'da** var — main'e push'ta hiç görünmüyor (ölçüm: main commit'inde 21, PR head'inde 22 check). Semantiği de deterministik kapı değil, **alert triage**: çıktısı `"No new alerts in code changed by this pull request"`. Merge bloğunu deterministik tutmak için dışarıda; taramanın **gerçekten koştuğu** zaten `CodeQL — python` + `CodeQL — javascript-typescript` ile garanti. |

### Tier 3 — ZORUNLU DEĞİL, gürültü (5 check)

Hepsi PR'da `skipped` sonuçlanıyor (ölçüldü) — job düzeyinde `if:` ile kapalılar:

| Check | `if:` koşulu |
|---|---|
| `Legacy upgrade (heavy — nightly/manual)` | `schedule \|\| workflow_dispatch` |
| `Backup / restore acceptance (heavy — nightly/manual)` | `schedule \|\| workflow_dispatch` |
| `Load full — Compose stack baseline (nightly / manual)` | `schedule \|\| workflow_dispatch` |
| `Nightly failure notice` **(iki workflow'dan da geliyor)** | `always() && schedule && …failure` |

`Nightly failure notice` ayrıca **ad çakışması** taşıyor: hem
`install-acceptance.yml` hem `performance.yml` aynı adı üretiyor. Required yapılan
bir ad iki workflow'a düşerse **ikisinin de** rapor etmesi gerekir ve hiçbir dosya
diğerinden haberdar değildir — ön kontrol scripti bunu `FATAL` sayar.

**Dependabot hakkında dürüst not:** görev tanımı "Dependabot/CodeQL bump job'larını
ayır" diyor, ama **ölçümde Dependabot'un ürettiği hiçbir check yok**.
`.github/dependabot.yml` var; Dependabot PR'ları **aynı 22 check'i** koşar, ayrı bir
job üretmez. Yani ayrılacak bir Dependabot gürültüsü bu repoda mevcut değil —
ayrılanlar yukarıdaki Tier 2 + Tier 3.

---

## 3. UYGULAMA — insanın çalıştıracağı tek komut

### Önce ön kontrol (zorunlu, salt-okuma)

```bash
scripts/required-checks-preflight.sh 682     # son merge edilmiş PR numarası
```

Payload'daki 16 adı, GitHub'ın o PR'da **gerçekten ürettiği** check listesiyle
karşılaştırır. Üretilmemiş bir ad varsa `FATAL` verip `exit 1` yapar — §5'teki
kilitlenme oraya varmadan durur. Negatifi kanıtlı: em dash yerine tire yazılmış
`Backend - lint, type, test` ve çift üretilen `Nightly failure notice` denendi,
ikisi de `FATAL` ile reddedildi.

### Sonra tek komut

```bash
gh api --method POST /repos/alimirbagirzade/Entropia/rulesets \
  --input .github/rulesets/main-required-status-checks.json
```

`201` döner ve yanıtta ruleset'in `id`'si gelir — **not edin**, geri alma için gerekir.

> **`.github/rulesets/` GitHub tarafından otomatik OKUNMAZ.** Repo'da durması ayarı
> yürürlüğe koymaz; dosya yalnız yukarıdaki komutun `--input` gövdesidir ve ayarın
> versiyonlanmış/gözden geçirilebilir kaydıdır. Yürürlüğe koyan tek şey POST'tur.

### Komut ne yapıyor — satır satır

Payload (`.github/rulesets/main-required-status-checks.json`) **elle yazılmadı**;
ölçülen check-run yanıtından üretildi, o yüzden 16 adın tamamı karakteri karakterine
GitHub'ın ürettiği adlardır (em dash `—`, `§`, parantezler dâhil).

| Alan | Değer | Ne yapıyor |
|---|---|---|
| `name` | `main — required status checks (RC P11-1)` | Ruleset'in görünen adı |
| `target` | `branch` | Dal hedefli kural seti |
| `enforcement` | `active` | Kural **uygulanıyor** (raporlamakla kalmıyor) |
| `conditions.ref_name.include` | `["~DEFAULT_BRANCH"]` | Yalnız varsayılan dal. `"main"` yazmak yerine bu simge kullanıldı: dal bir gün yeniden adlandırılırsa kural **kendiliğinden** takip eder, sessizce boşa düşmez |
| `bypass_actors` | `[]` | **Kimseye muafiyet yok — admin dâhil.** Gerekçe §5'te |
| `rules[0]` | `deletion` | `main` silinemez |
| `rules[1]` | `non_fast_forward` | `main`'e force-push yasak |
| `rules[2]` | `pull_request`, `required_approving_review_count: 0` | **Merge yalnız PR üzerinden.** Bu kural olmadan diğer her şey kâğıt üstünde kalır: required status check'ler **sadece PR merge'ini** kapsar, `git push origin main` onları tamamen atlar. `0` onay bilinçli: repo tek kişilik, kendi PR'ınızı onaylayamazsınız → `1` yazmak kalıcı kilit demektir |
| `rules[3]` | `required_status_checks` | 16 check, hepsi `integration_id: 15368` ile **GitHub Actions app'ine sabitli** (ölçüldü). Sabitleme, aynı adı üreten üçüncü bir app'in kapıyı sahte-yeşil geçmesini engeller |
| `strict_required_status_checks_policy` | `true` | Merge'den önce dalın main ile **güncel** olmasını zorunlu kılar |

**`strict: true` bir karardır, bedeli var.** Lehine: CLAUDE.md'nin kaydettiği
"docs regresyonu ÜÇ KEZ oldu — bayat base'li docs PR'ları `PROJECT_HISTORY.md`'den
kayıt sildi (#590, #604)" vakası tam olarak **bayat base** vakasıdır; `strict`
dalı merge öncesi main'e güncellemeye zorlar ve CI'yı birleşmiş içerik üzerinde
yeniden koşturur. Aleyhine: her merge sonrası açık PR'lar güncellenmeli ve
`Backend — lint, type, test` **~48 dakika** sürüyor (ölçüm: `16:01:24 → 16:49:18`),
yani sıralı merge'ler pahalı. **Dürüst sınır:** `strict` o regresyonu tek başına
yakalamaz — hiçbir CI kapısı `docs/` okumaz; CLAUDE.md'nin
`git show <sha> -- docs/ | grep '^-## '` kuralı **yürürlükte kalır**.
Bedel ağır gelirse tek alan değiştirin:

```bash
gh api --method PUT /repos/alimirbagirzade/Entropia/rulesets/<id> \
  --input <(python3 -c "import json;p=json.load(open('.github/rulesets/main-required-status-checks.json'));[r['parameters'].__setitem__('strict_required_status_checks_policy',False) for r in p['rules'] if r['type']=='required_status_checks'];print(json.dumps(p))")
```

---

## 4. Alternatif — GitHub arayüzü

1. **Settings → Rules → Rulesets → New ruleset → New branch ruleset**
2. **Ruleset Name:** `main — required status checks (RC P11-1)`
3. **Enforcement status:** `Active`
4. **Target branches → Add target → Include default branch**
5. **Bypass list:** boş bırakın (§5)
6. **Rules** — şu üçünü işaretleyin:
   - `Restrict deletions`
   - `Block force pushes`
   - `Require a pull request before merging` → **Required approvals: `0`**
7. `Require status checks to pass` işaretleyin, `Require branches to be up to date
   before merging` kutusunu **işaretleyin** (= `strict: true`)
8. **Add checks** → arama kutusuna yazın ve **açılan listeden seçin, elle yazıp
   Enter'a BASMAYIN.** Arayüz son koşulardan gerçek adları önerir; serbest metin
   girişi §5'teki kilidin ta kendisidir. Seçilecek 16 ad §2 Tier 1 tablosunda.
   Her birinin yanında kaynak app `GitHub Actions` görünmeli.
9. **Create**

Arayüz `integration_id`'yi seçilen öneriden kendisi doldurur — bu yüzden 8. adımda
**seçmek** ile **yazmak** arasındaki fark güvenlik farkıdır.

---

## 5. UYARILAR

**(a) Var olmayan bir ad TÜM merge'leri kilitler.** Required check ada göre eşleşir
ve GitHub adın bir şeye karşılık geldiğini **doğrulamaz**. Karşılığı yoksa check hiç
oluşmaz; PR'da `Expected — Waiting for status to be reported` satırı asılı kalır ve
**hiçbir zaman** çözülmez. Bu repodaki adlar elle yazmaya düşman: em dash (`—`),
`§`, parantez, matrix açılımı (`CodeQL — python`). Bu yüzden payload ölçümden
**üretildi** ve `scripts/required-checks-preflight.sh` POST öncesi zorunlu adımdır.

**(b) `skipped` ile "hiç oluşmadı" aynı şey değil.** `if:` ile atlanan bir job yine
de `skipped` sonuçlu bir check-run **yazar** (ölçüldü: Tier 3'ün 5'i de yazdı).
Ölümcül olan, check'in hiç **oluşmaması**dır: yanlış ad, ya da PR'da tetiklenmeyen
bir workflow (`paths:` filtresi, `branches:` uyuşmazlığı). Bugün bu repoda `paths:`
filtresi yok — bu kurulumun güvenli olmasının koşulu bu.

**(c) `bypass_actors: []` = admin de muaf değil.** Ruleset'lerde admin
**otomatik muaf DEĞİLDİR**. Bir kapı çırpınırsa ve muafiyet yoksa, kurtarma yolu
muafiyet aramak değil, ruleset'i **durdurmaktır** (§6). Bilerek böyle: tahmin edilmiş
bir `actor_id` yazmak, kapıyı sessizce delik bırakma riski taşır. Kalıcı bir muafiyet
istiyorsanız arayüzden ekleyin (orada id yazılmaz, listeden seçilir).

**(d) `required_approving_review_count: 0` bilinçli.** Repo tek kişilik ve GitHub
kendi PR'ınızı onaylamanıza izin vermez → `1` yazmak her PR'ı kalıcı kilitler.
CLAUDE.md'nin "self-merge is blocked → ask the user to merge" kuralı **sosyal** bir
kuraldır, bu ayarla çakışmaz.

**(e) Bu ruleset A-08'i kapatmaz.** Ekran okuyucu denetimi hâlâ yapılmadı, defter
boş. Buradaki hiçbir check onun kanıtı değildir.

---

## 6. Geri alma / kurtarma

```bash
gh api /repos/alimirbagirzade/Entropia/rulesets                       # id'yi bul
gh api --method DELETE /repos/alimirbagirzade/Entropia/rulesets/<id>  # tamamen kaldır
```

Kaldırmadan **geçici** durdurmak (tercih edilen): arayüzde
**Settings → Rules → Rulesets → <ruleset> → Enforcement status: `Disabled`**.
Kural ve listesi durur, ayar kaybolmaz.

---

## 7. Bakım — bir job adı değişirse

`name:` alanını değiştirmek **kapıyı sessizce açar**: eski ad artık üretilmez,
required check ebediyen bekler; ya da kural kaldırılır ve kapı hiç kalmaz. Sıra:

1. `.github/workflows/*.yml` içinde `name:` değiştir
2. `.github/rulesets/main-required-status-checks.json` içinde **aynı** adı güncelle
3. PR merge edilip yeni ad **en az bir kez üretildikten sonra**
   `scripts/required-checks-preflight.sh <pr>` koş
4. `gh api --method PUT /repos/:owner/:repo/rulesets/<id> --input <payload>`

**Yeni bir bloklayıcı kapı eklediğinde** (yeni job): önce merge et, adının gerçekten
üretildiğini gör, sonra payload'a ekle ve PUT et. Ters sıra kilitler.
`scripts/required-checks-preflight.sh` çıktısındaki "Produced but NOT required"
bölümü bu adımın hatırlatıcısıdır: orada Tier 2/Tier 3 dışında bir ad görürsen,
bloklayıcı bir kapı merge bloğuna bağlanmadan landed olmuş demektir.
