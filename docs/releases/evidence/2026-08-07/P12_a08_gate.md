<!-- doc-status: current -->
# P12 — A-08 insan kabul kapısı: karar

**Tarih:** 2026-08-07 · **Dal:** `claude/a08-human-gate-assessment-2c93f7`
**Base SHA:** `1f243915377a8b8ac9b698cac9739138354f4705` (`1f24391`, `docs(v18-rc): record P1 repository truth gate evidence (#632)`) — `origin/main` ile aynı.
**Kapsam:** yalnız **ölçüm + karar**. Kod, test, CI, denetim defteri ve GitHub issue durumu **değişmedi**.

> **Bu adımda bilerek YAPILMAYANLAR** (hepsi insan yetkisi):
> #514 açılmadı da kapatılmadı (`human-only` etiketi) · hiçbir imza yazılmadı ·
> `a11y_screen_reader_audit_results.md` §0/§1/§2/§3/§5 **hiç düzenlenmedi** ·
> otomatik kanıt (axe ratchet / precheck / keyboard spec) §1 veya §2'ye **transkribe edilmedi**.

---

## 0. Karar: **BLOCKED** (A-08 ekseni)

| Kapı | Gerekli | Ölçülen | Sonuç |
|---|---|---|---|
| Dört çıkış kriteri (§5) | 4 / 4 ☑ | **0 / 4** — dördü de ☐ | **DÜŞTÜ** |
| A-08 için imzalı kalıcı sapma | var **veya** yok+denetim yapılmış | **YOK** | **DÜŞTÜ** |

**Blocker adı: `A-08-HUMAN-GATE-UNMET`** — *insan ekran okuyucu kabul denetimi
koşulmadı ve yerine geçecek imzalı kalıcı sapma da yok.*

Bu iki koşulun ikisi de düştüğü için A-08 ekseninde verdict **BLOCKED**'dır.
Hiçbir RC belgesi A-08'i `Complete` / `PASS` / `Done` gösteremez — denetim defterinin
kendisi de dahil (§5, `:293-294`).

> **"Kural 13" hakkında dürüst not.** Operatörün adlandırdığı *kural 13* metni bu
> repository'de yok (`grep -rn 'kural 13\|rule 13' docs/ .claude/` → **0 hit**). Karar
> repo-içi eşdeğer otoriteye dayandırıldı:
> `docs/audit/a11y_screen_reader_audit_results.md` §5 — *"Until all four are ☑, no
> document may show A-08 as `Complete` or `PASS` — including this one."* İkisi aynı
> kapıyı tarif ediyor; aşağıdaki ölçümler her iki okumada da aynı sonucu verir.

---

## 1. Ölçüm — GitHub #514

```bash
gh issue view 514 --json state,closedAt,stateReason,labels
```

| Alan | Değer |
|---|---|
| `number` | 514 |
| `title` | *A-08: Complete human NVDA/Firefox + VoiceOver/Safari acceptance audit* |
| `state` | **CLOSED** |
| `closedAt` | `2026-08-07T03:52:03Z` |
| `stateReason` | `COMPLETED` |
| `labels` | `human-only` — *"Sadece insan kapatabilir; kanitsiz kapatma yasak"* |
| `updatedAt` | `2026-08-07T03:52:03Z` |

`stateReason: COMPLETED` bir **iddiadır, kanıt değildir**. Aynı issue daha önce de
kanıtsız kapatılmıştı (`2026-07-30T19:05:32Z`, 2026-08-03'te yeniden açıldı); bu
**ikinci** kanıtsız kapatmadır ve yine tek bir sonuç satırı üretmemiştir.

**Bu adımda issue'ya dokunulmadı** — ne `gh issue reopen`, ne `gh issue close`,
ne yorum. `human-only` etiketi agent'a her iki yönü de yasaklar.

---

## 2. Ölçüm — denetim defteri (`docs/audit/a11y_screen_reader_audit_results.md`, 346 satır)

| § | Ne olması gerekiyor | Ölçülen | Satır |
|---|---|---|---|
| **§0** Session header | 2 blok (SR-1 NVDA/Firefox/Windows, SR-2 VoiceOver/Safari/macOS), her biri 11 alan | **Denetçi adı `—`, tarih `—`, SR sürümü `—`, tarayıcı sürümü `—`, stack commit `—`, kayıt yolu `—`.** İki blokta da tek bir doldurulmuş alan yok (yalnız sabit seed flag'leri yazılı) | `:61-96` |
| **§1** Section A | 23 rota × 2 kombinasyon = **46 koşu**, her rota için A-1..A-8 | **SR-1: 0 / 23 rota · SR-2: 0 / 23 rota.** Tüm hücreler `—` (= koşulmadı) | `:100-181` |
| **§2** Section B | 10 kritik akış × 2 kombinasyon = **20 koşu** | **SR-1: 0 / 10 akış · SR-2: 0 / 10 akış.** Tüm `Result` hücreleri `—` | `:184-221` |
| **§3** Findings register | bulgu başına bir satır, 16 zorunlu kolon | **Tek satır, o da yer tutucu:** `*(none recorded — audit not run)*` | `:233-235` |
| **§5** Exit criteria | 4 kriterin dördü de ☑ | **0 / 4** (aşağıda) | `:282-300` |

### §5 — dört çıkış kriteri, birebir

| # | Kriter | İşaret |
|---:|---|---|
| 1 | Hem SR-1 hem SR-2 koşuldu | **☐** (0 / 2) |
| 2 | Section A 23 rotanın hepsinde, Section B 10 akışın hepsinde, iki kombinasyon için tam | **☐** (0 / 46 rota, 0 / 20 akış) |
| 3 | Her bulgu `FIX` veya `PO-APPROVE` taşıyor | **☐** |
| 4 | Her `FIX` ya landed ya PO-imzalı sapmaya dönüşmüş | **☐** |

**0 / 4.** Defterin kendi cümlesi (`:296-300`): *"Closing the tracking issue satisfies
none of the four."* Kapı bu tablodur, issue'nun durumu değil.

---

## 3. Ölçüm — `SR-BULGU` taraması (şablon ≠ bulgu)

```bash
grep -rn "SR-BULGU" docs/
```

**Toplam 8 hit. Gerçek bulgu kaydı: 0.** Ayrım:

| Sınıf | Adet | Dosya:satır | Ne olduğu |
|---|---:|---|---|
| **Şablon / biçim tanımı** | 2 | `docs/audit/a11y_screen_reader_audit_results.md:241` | Kolon sözleşmesi: *"`ID` \| `SR-BULGU-nn`, allocated in order, never reused"* — biçim kuralı |
| | | `docs/implementation/a11y_screen_reader_audit_checklist.md:102` | "Bulgu kayıt şablonu" kod bloğunun ilk satırı — doldurulacak boş form |
| **Yokluğu ifade eden meta-atıf** | 6 | `docs/PROJECT_HISTORY.md:1785` | *"…tek bir `SR-BULGU` kaydı **yok**"* |
| | | `docs/audit/current_main_ground_truth_2026-08-03.md:648` | *"tek hit, o da `SR-BULGU-nn` şablon satırı"* |
| | | `docs/implementation/v18_final_acceptance.md:244` | *"…ne de tek bir `SR-BULGU` kaydı var"* |
| | | `docs/implementation/entropia_v18_remediation_status.md:107,108,116` | Aynı yokluğun üç yerde tekrarı |
| **Gerçek bulgu kaydı** | **0** | — | Doldurulmuş `SR-BULGU-01`, `-02`, … **hiç yok** |

Yani tarama, denetimin koşulmadığını **bağımsız olarak** doğruluyor: bir denetim
koşulsaydı en az bir doldurulmuş `SR-BULGU-nn` satırı üretirdi — ya bulgu olarak,
ya da "sıfır bulgu" iddiası §1/§2'de `PASS` hücreleri olarak görünürdü. İkisi de yok.

---

## 4. Ölçüm — `docs/implementation/v18_visual_deviations.md`: A-08 için imzalı sapma **VAR MI?**

**HAYIR.**

| Kontrol | Komut | Sonuç |
|---|---|---|
| Dosyada A-08 geçiyor mu? | `grep -in 'a-08\|a08' docs/implementation/v18_visual_deviations.md` | **0 hit** |
| Ekran okuyucu / NVDA / VoiceOver geçiyor mu? | `grep -in 'screen.reader\|ekran okuyucu\|NVDA\|VoiceOver'` | **0 hit** |
| Dosyadaki sapma kimlikleri | `grep -o 'D-[0-9]\+' … \| sort -u` | yalnız **`D-1`** |

Dosyanın sapma sözlüğü `FIX(R2-xx)` / `PO-APPROVE` / `SIGNED-DEVIATION (D-1)`
üçlüsünden ibaret ve tamamı **görsel/yapısal** R2-13 kalemlerine ait (route farkları,
metadata superset'leri, yoğunluk farkları). A-08 ekseninde **tek satır yok**.

Defterin kendi ifadesi bunu zaten yazıyor (`:50`):
> *"**No signer has been supplied, so no such record exists**, and none may be written
> on an agent's initiative."*

**Bu adımda böyle bir kayıt yazılmadı** — imzalayan adı, ISO tarih ve kapsam
verilmediği için yazılamaz; verilseydi bile yazma yetkisi agent'ta değildir.

### Yan bulgu P12-B1 — sapma işaretçisi yanlış dosyayı gösteriyor (düzeltilmedi)

Defter iki yerde (`:50` ve `:258-259`) imzalı sapmanın *"`v18_visual_deviations.md`'de,
D-10 gibi"* kaydedildiğini söylüyor. Ama **`D-10` o dosyada yok** (yukarıdaki
`sort -u` → yalnız `D-1`). D-10 gerçekte şurada kayıtlı:

- `docs/audit/current_main_ground_truth_2026-08-03.md:450` — *"D-10 — 45 accent-mavi düğüm (A11Y-01), **İMZALI KALICI SAPMA**"*, kapsam `33 × #ffffff on #00a9e8` + `12 × #00a9e8 on #ffffff`, hepsi 2.67:1
- `docs/implementation/a11y_ci_ratchet_and_adjudication.md:206-221` — karar tablosu + imza bloğu metni

Etki: **kararı değiştirmez, güçlendirir.** İşaretçi yanlış olsa da hem işaret edilen
dosyada hem gerçek D-10 kayıt yerlerinde A-08 için sapma **yok**. Düzeltilmedi —
P12 belge değiştirmez; ayrı bir docs slice'ına ait.

> D-10'un kendisi **ayrı eksendir** ve A-08'i kapatmaz: düşük-görüş (kontrast, WCAG
> 1.4.3) ekseni, ekran okuyucu ekseni değil. Defter bunu K-1 satırında açıkça yazıyor
> (`:329`): *"It is a low-vision axis, not a screen-reader one."* D-10 sürüyor →
> **WCAG 2.2 AA 1.4.3 karşılanmıyor**, ürün bu ölçüt için uyumlu sayılamaz.

---

## 5. Karar gerekçesi

Üç bağımsız ölçüm aynı yere çıkıyor:

1. **Defter boş** — §0'da denetçi yok, §1/§2'de 66 koşunun 66'sı `—`, §3'te yer tutucu satır.
2. **`SR-BULGU` taraması** doldurulmuş tek bir kayıt bulmuyor (8 hit'in 2'si şablon, 6'sı yokluk beyanı).
3. **İmzalı sapma yok** — ne `v18_visual_deviations.md`'de, ne D-10'un gerçek kayıt yerlerinde.

Kapının iki geçerli kapanış yolu vardı; **ikisi de kapalı**:

| Yol | Durum |
|---|---|
| Denetim koşulmuş ve dört kriter ☑ | **HAYIR** — 0 / 4 |
| Denetim koşulmamış ama imzalı kalıcı sapma kabul edilmiş | **HAYIR** — imzalayan verilmedi, kayıt yok |

`#514`'ün `CLOSED / COMPLETED` olması hiçbirini karşılamaz: kapatma issue'nun
durumunu değiştirdi, defterin içeriğini değil — ne denetçi, ne sürüm dizesi,
ne bulgu ekledi.

**→ `A-08-HUMAN-GATE-UNMET` — BLOCKED.**

---

## 6. Blocker kaydı (RC kabul listesine taşınacak)

```
BLOCKER : A-08-HUMAN-GATE-UNMET
Eksen   : Erişilebilirlik — insan ekran okuyucu kabul denetimi (A-08)
Durum   : BLOCKED
Ölçüm   : çıkış kriterleri 0 / 4 (defter §5) · 0 / 46 rota · 0 / 20 akış ·
          0 doldurulmuş SR-BULGU kaydı · A-08 için imzalı kalıcı sapma YOK
İzleme  : GitHub #514 — CLOSED 2026-08-07T03:52:03Z (COMPLETED), label human-only.
          İkinci kanıtsız kapatma; ilki 2026-07-30, 2026-08-03'te geri alınmıştı.
Etki    : Hiçbir belge A-08'i Complete / PASS / Done gösteremez (defter §5:293-294).
          RC bu eksende kabul edilemez.
Çözüm   : insan işi — aşağıdaki iki yoldan biri. Agent hiçbirini yapamaz.
```

### İki insan çözüm yolu

| | Yol | Somut adımlar | Neden agent yapamaz |
|---|---|---|---|
| **(A)** | **Denetimi koştur** | 1. `scripts/a11y-audit-stack.sh up` (seed: `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1`) · 2. §0'daki **iki** bloğu doldur (NVDA/Firefox/Windows **ve** VoiceOver/Safari/macOS — tek kombinasyon A-08'i karşılamaz) · 3. §1'de 23 rota × A-1..A-8, §2'de 10 akış — her iki kombinasyon için · 4. Her `FAIL` §3'e `SR-BULGU-nn` olarak, `.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml` ile issue açarak · 5. Her `FIX` için §4 retest listesi · 6. Dört kriter ☑ olunca **insan** #514'ü kapatır | Denetim *duymayı* gerektirir. DOM ölçümü ekran okuyucu sonucu değildir (defter §6): axe/precheck/keyboard spec'lerin üçü de "duyuruldu mu" sorusunu yanıtlamaz, precheck kendi kaydına `screen_reader_verified: false` damgalar. |
| **(B)** | **İmzalı kalıcı sapma** | D-10 biçiminde bir kayıt: **adı verilmiş imzalayan** + **ISO tarih** + **açık kapsam** ("A-08 insan denetimi koşulmadan sevkiyat kabul edildi"). Kabul edilenin bir *sonuç* değil, denetimin **yokluğu** olduğu yazıya geçmeli. | İmza bir insan taahhüdüdür. İmzalayan verilmedi; agent kendi inisiyatifiyle imza üretemez (defter `:50`). |

**Üçüncü bir yol yok.** Özellikle: #514'ü kapalı bırakmak bir çözüm değildir — kapalı
issue ile boş defter arasındaki ayrışma o zaman da sürer, sadece görünmez olur.
(B) seçilirse #514 kapalı kalabilir ama kapanışın dayanağı imza olur, `COMPLETED` değil;
(A) seçilirse #514'ün insan eliyle **yeniden açılması** gerekir — aksi halde denetim
kapalı bir issue altında koşulur ve sonuçlarının izleneceği yer kalmaz.

---

## 7. P12 sonucu

**BLOCKED.** Bu, P1'in yeşil olmasıyla çelişmez: P1 repository'nin kendi sayıları
hakkında doğru yazdığını kanıtladı, ürün kabulünü değil. A-08 tam olarak P1'in
kapatamayacağı sınıftan bir açık sınırdır ve P1 raporu (`P1_repository_truth.md` §5)
bunu sonraki adımlara devretmişti — P12 onu **adıyla bir blocker'a** bağladı.

**Bu adımda değişen hiçbir şey yok:** issue durumu aynı, defter aynı (346 satır, boş),
imza yazılmadı, otomatik kanıt transkribe edilmedi. Üretilen tek dosya bu rapordur.

| Dosya | İçerik |
|---|---|
| `P12_a08_gate.md` | bu dosya — ölçüm + `A-08-HUMAN-GATE-UNMET` blocker kaydı |
