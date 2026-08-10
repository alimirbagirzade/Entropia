<!-- doc-status: current -->
# P6-ek + P6-6 — harness fail-fast dayanıklılığı (ADIM 34, 2026-08-10)

Kanonik kayıt: `docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` **§6.7.3**.
Bu dosya o bölümün ham kanıtını toplar.

| Dosya | İçerik |
|---|---|
| `p6ff_measurements.txt` | sağlıklı host'ta probe gecikmeleri (eşiklerin kalibrasyonu) · `bounded_run` semantiği · preflight'ın üç negatifi · `backup-verify` exit-code matrisi |
| `p6ff_tests_before_fix.txt` | regresyon testleri **düzeltme geri alınmış** ağaçta: **5 failed / 7 passed**, 369s |
| `p6ff_tests_after_fix.txt` | aynı testler düzeltilmiş ağaçta: **12 passed**, 23.3s |

## Ne kanıtlandı

**1. İki kusur da yeniden üretildi** (rapor iddiası körü körüne kabul edilmedi).

* **P6-ek** — PATH'e cevap vermeyen bir `docker` konarak `scripts/e2e-acceptance.sh session`
  koşuldu: **25s sonra hâlâ koşuyordu**. `FATAL … exit 2` dalı probe'un hemen altındadır ama
  probe hiç dönmediği için alınamaz.
* **P6-6** iki ayrı biçimde:
  (a) takılmış `dropdb` → script süresiz asılı;
  (b) `dropdb` **başarısız** → `|| true` yuttu → artık scratch DB yüzünden `createdb`
  patladı → **`exit 1`**. Yani **hiç okunmamış, sağlam bir yedek** "geri yüklenmiyor" diye
  raporlandı. Bu, raporun tarif ettiği yanlış-negatifin tam olarak kendisidir.

**2. Düzeltmeden sonra üç durum üç ayrı kodla ayrışıyor.**

```
e2e-acceptance.sh   0 = her adım geçti · 1 = bir adım düştü · 2 = harness hiç koşamadı
backup-verify.sh    0 = geri yükleniyor · 1 = geri yüklenmiyor (YEDEK hakkında karar)
                    3 = doğrulanamadı (ORTAM hakkında karar)
```

Ölçülen matris (sınırlar teste 3s verilerek):

| Senaryo | rc | süre |
|---|---|---|
| docker CLI tamamen takılı | **2** | 3.0s |
| yalnız `docker version` takılı | **2** | 3.0s |
| daemon anında reddediyor (kontrol) | **2** | 0.0s — mesaj "not reachable", "HUNG" **değil** |
| `dropdb` takılı | **3** | 6.1s |
| artık scratch DB (eski yanlış-negatif) | **3** | 0.0s |
| `pg_restore` takılı | **3** | 3.1s |
| dump gerçekten tutarsız (kontrol) | **1** | 0.1s |
| **sağlam yedek** (kontrol) | **0** | 0.1s |

Son iki satır bilerek buradadır: "sağlam yedeği başarısız raporlama" düzeltmesi, **bozuk
yedeği sağlam raporlamaya** dönüşemez. İkisi de teste bağlandı.

**3. Eşikler ölçüme dayanıyor.** Sağlıklı host: `docker version` 1.44s ·
`docker compose version` 0.16s · `dropdb` (mevcut DB) **4.83s** · `createdb` 0.92s ·
`psql` 0.13s. Varsayılanlar: docker probe **20s** (~14×), pg kontrol düzlemi **60s** (~12×),
`pg_restore` **1800s** (süresi dump'la ölçeklendiği için ayrı eksen). `dc up --build`,
`exec`, `logs` **bilerek sınırsız** — dürüst süreleri dakikalardır.

**4. Testler ısırıyor.** `git stash` ile yalnız iki script düzeltmeden önceki hâline
döndürülüp aynı testler koşuldu: **5 failed** — dördü `pytest.fail("… STILL RUNNING after
90s")`, biri `assert 1 == 3` (P6-6'nın yanlış-negatifi). Düzeltmeyle **12 passed**.
Geçen 7 kontrolün 3'ü `bounded_run`'ın kendi semantiğidir; o dosya bu slice'ta doğduğu için
"öncesi" ölçümünde de mevcuttu — bu üçü için "önce kırmızıydı" **iddia edilmiyor**.

## Bu slice'ın KAPATMADIĞI şeyler

* **Blocker sayısı değişmedi (üç); verdict BLOCKED kalır.**
* `flows` hâlâ **bir CI kapısı değildir** — §6.2'nin açık ekseni, ADIM 30'a aittir.
* **"Docker düzeldi" denmiyor.** Daemon'a dokunulmadı; ölçüm günü zaten normal cevap
  veriyordu. Değişen tek şey, bir sonraki takılmanın **kendini bildirecek** olması.
* Ürün kodu değişmedi (harness/script slice'ı).
* Aynı kusur sınıfı **yalnız bu iki script içinde** tarandı; başka script'lere süpürülmedi.
