<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 111 LANDED — docs kayıt-silme kapısı üretilmiş artefaktlar için daraltıldı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 111. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

> **BU KICKOFF YAZILDIKTAN SONRA ADIM 112 İNDİ (#829).** Ağaçtaki kayıt sırası
> **110 → 112 → 111**'dir: bu slice `111` boşluğunu doldurur. ADIM 112 = #825'in kayıtsız inen
> ritüeli (delta forensics + `G8`/`G14` imza blokları) ve **kickoff'u YOK** (bilerek, ADIM 82/109)
> — bu yüzden canlı devam tohumu **budur**, ama *"sıradaki iş"* bölümünü okurken ADIM 112'nin
> `PROJECT_HISTORY.md` §ADIM 112 kaydını da oku: `## Next:` artık **imzaları** adlandırıyor
> (`G8` #559 · `G14` #544 · Karar 1), *"PR B"* değil.

Taban ADIM 110 (#826). **ÜRÜN KODU DEĞİŞMEDİ** — `backend/src` ve `frontend/src`'te tek satır
yok; diff bir **agent guard betiği**, onun **davranış kapısı** ve `CLAUDE.md` §Conventions.
Migration yok, alembic head `0043_i08_registry_strategy_fks`, `ENGINE_VERSION` ve OpenAPI
değişmedi, kabul borcu tavanları **OYNAMADI** (54/6 · A=1 B=21 C=6 D=32).
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

Kapatılan şey bir kusur değil, bir **yanlış pozitifti**: `guard-git.sh`'in docs kayıt-silme
kapısı düz bir `grep '^-## '` yapıyordu ve **her kabul borcu partisinde** çalıyordu, çünkü
üretilmiş defterlerin bölüm başlıkları **sayı taşır**.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- **`plugins/entropia-maintenance/hooks/guard-git.sh` §1** — kapı artık gömülü bir `python3`
  süzgecinden geçer. Sözleşme: **kök karşılaştırması, dosya başına**. `stem(h)` sondaki
  `(N)` sayacını atar; bir başlık ancak kökü **aynı dosyada** eklenenlerin kökleri arasında
  yoksa silinmiş sayılır. Diff'i `+++`/`---` başlıklarından ayrıştırır (`+++ /dev/null`
  gelirse yolu `---` tarafından alır → dosya silme de bloklanır).
- **`scripts/hook-guard-proof.sh`** — fixture artık **iki** docs dosyası taşır:
  `docs/PROJECT_HISTORY.md` (kayıt taklidi) + **`docs/audit/ledger.md`** (sayı taşıyan
  üretilmiş defter taklidi). Yardımcılar `stage_history` / **`stage_ledger`**; sabitler
  `KEEP` `DROP` **`RENUM`** **`LEDGER`** **`LEDGER_DOWN`** **`LEDGER_UP`** **`LEDGER_STEALS`**.
  Özet satırı artık **`blocks` sayacından türetilir**, elle yazılmaz.
- Ölçüm çapası: gerçek bir diff'i kapıdan geçirmek için
  `git diff <base> <dal> -- docs/ | python3 -c '<guard'ın süzgeci>'` — ADIM 110'un diff'i
  bu yolla doğrulandı.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **HER SEFERİNDE ÇALAN BİR ALARM, KENDİSİNİ SUSTURMAYI ÖĞRETİR.** Kapı "doğru" tarafta
   hata yapıyordu (fail-closed) ama **her** kabul borcu partisinde yanlış pozitif veriyordu;
   ölçüldü — merge edilmiş **#821 (ADIM 107)** ve **#826 (ADIM 110)** birebir aynı şekli
   taşıyor. Bir insanı her partide *"onaylıyorum"* demeye alıştıran kapı, gerçek regresyonu
   yakalayacağı gün de o cevabı alır. Daraltma bir **gevşetme değil**, alarmın anlamını geri
   kazanmasıdır.
2. **BİR KONTROL HARNESS'İ TABANIN COMMIT'Lİ OLDUĞUNU VARSAYAMAZ.** İlk negatif-kontrol
   betiği geri almayı `git checkout -- <guard>` ile yapıyordu; guard **henüz commit
   edilmemişti** ve üç kontrol de çalışmayı **sildi** (üçü de aynı `anchor count 0 != 1` ile
   patladı — kusurun kendisi değil, harness'ın yıkımı). Geri alma **bellekteki anlık
   görüntüye** çevrildi. ADIM 100'ün *"`finally` SIGTERM'de koşmaz"* dersinin kardeşi:
   **geri alma yolunu, koruduğu şeyden bağımsız kur.**
3. **PATH ALLOWLIST'İ DEĞİL KÖK KARŞILAŞTIRMASI** — `docs/generated/*` gibi bir liste her
   yeni üretilmiş dosyada kod değişikliği ister **ve** o dosyaları GERÇEK silmelere karşı
   körleştirir. Kök karşılaştırması hem daha az kırılgan hem **daha dar**: aynı dosyada
   kökü korunan bir sayı değişimi geçer, kaydın silinmesi de yeniden adlandırılması da
   bloklanır.
4. **ELLE YAZILMIŞ ÖZET SAYISI BAYATLAR.** Kapının kendi çıktısı *"6 blocks"* diyordu;
   `origin/main`'de `probe 2` sayıldı → **7**. Kimse fark etmemişti çünkü sayı hiçbir şeyi
   kapılamıyordu. Artık `blocks` sayacından türetiliyor. (Depoda bu dersin üçüncü şekli —
   ADIM 40 katman sayıları, ADIM 60 test collection, şimdi bu.)
5. **TARİHSEL BLOKLARI DÜZELTME.** `CLAUDE.md`'nin ADIM 58 girdisi ve
   `docs/ADIM58_LANDED_KICKOFF.md` hâlâ *"19 beklenti = 6 engelleme + 13 GEÇİŞ"* yazar ve
   **öyle kalmalıdır** — ölçtükleri anı dondururlar (ADIM 65/76 emsali). Güncel gerçek
   §Conventions'ta yaşar, ve oraya da **sayı yazılmadı**.

## Ölçülmüş sınırlar — kapatılmadı, kaydedildi

- **Kapı hâlâ yalnız `## ` (h2) başlıklarını sayar.** `### ` altındaki bir kaydın silinmesi
  görünmez. Bu **daraltmadan önce de böyleydi**, bu slice onu değiştirmedi.
- **Kök kuralının kabul ettiği bir yazım var:** aynı dosyada `## Class B (23)` silinip
  `## Class B (99)` eklenirse geçer. Bu bir **değişikliktir** (herhangi bir okumaya göre),
  ama bir insanın sayıyı kasten şişirmesini kapı görmez — o `--ratchet`'in işidir.
- **`guard-git.sh` hâlâ komut dizesinin tamamında desen arar** (gate 2/3): `feat/main-menu`
  de, bu desenleri *içeren* bir heredoc de bloklanır. **Değiştirilmedi**, bilerek.
- **Plugin hâlâ kurulu değil**; kapı `.claude/settings.json` kaydı sayesinde koşar (ADIM 58).

## Sıradaki iş — ölçülmüş adaylar (yine de KENDİN ÖLÇ)

**Kabul borcu:** testle kapanabilir sınıf-B satır neredeyse tükendi. Kalan 21 sınıf-B
kriterin çoğu kayıtlı **bulgu**dur. ADIM 110'un ölçmediği üç ad: **`TS-07`** · **`TL-14`** ·
**`TR-07`** — üçünü de `acceptance_semantic_map.yaml`'ın `notes` alanından oku ve **ürün
kodunda doğrula** (ADIM 54). Yeni bulgu: **`UM-15.c3` sevk edilmemiş** (sınıf D şekli,
taşınMADI) ve **`CP-03.c4` belirsiz**.

**Muhtemelen daha değerli hat:** defterdeki **on yedi bulgunun** artık bir **adjudication
kalemi** oluşturduğu ADIM 79'da yazılmıştı; sayı büyüdü. B→C/D taşıma tavan yükseltir, yani
bir insan kararıdır — ama *"bu satırların hangileri gerçekten sınıf B"* sorusunu ölçüp imzaya
sunan bir slice, her partide yeniden ölçülen aynı satırları kalıcı olarak kapatırdı.

**Mühendislik hattı:** `## Next:` kıpırdamadı — `C6` (G12 imzası), `F2` (G4), `F3` (Karar 1 /
#552), `C9` (Karar 3 / #559). **İmzasız bir kapının arkasındaki slice'a BAŞLAMA.** A-08 hâlâ
tek blocker ve yalnız bir insan denetçiyle ilerler; devam kartı
`docs/implementation/a11y_screen_reader_audit_runbook.md` **§0**'da hazır.

## Ortam çapaları (bu container'da ölçüldü)

```
bash scripts/hook-guard-proof.sh          # ~1 sn, ağsız, DB'siz; 23 beklenti
node scripts/agent-config-gate.mjs        # kayıt/pin/ayna kapısı
bash -n plugins/entropia-maintenance/hooks/guard-git.sh   # kusurlu betik sözdizimi kontrolü
cd backend && uv sync --all-extras        # üretilmiş olgular + --check için ŞART
uv run python ../scripts/generate_repository_facts.py --root .. --check
python3 docs/audit/acceptance_semantic_scan.py --report --check-generated --ratchet
```

**Bu slice'ta ne backend ne frontend suite'i koşuldu** — ikisinde de sıfır satır var;
otorite CI.

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
Entropia — sıradaki slice (ADIM 112).

DOĞRULA ÖNCE (handoff STALE-BY-DEFAULT):
  git fetch && git log --oneline origin/main -3
  grep -o '^## ADIM [0-9]*' docs/PROJECT_HISTORY.md | grep -o '[0-9]*' | sort -n | tail -1
  açık PR listesi (state=open) — BOŞ liste bir ANLIK GÖRÜNTÜDÜR, garanti değil (ADIM 100/103).
  Çakışma başlıkta değil DOSYA YOLUNDA ölçülür (ADIM 91): açık PR'lar
  docs/ADIM<n>…KICKOFF.md ekliyor mu?
Ölçtüğüm hâl: ADIM 111 sonrası · canlı kickoff docs/ADIM111_LANDED_KICKOFF.md ·
kabul borcu tavanları 54 partial / 6 uncovered · A1 B21 C6 D32 (bu slice OYNATMADI).

İKİ HAT VAR, İKİSİ DE MEŞRU:
  (a) Kabul borcu batch 30 — TS-07 / TL-14 / TR-07'yi ölç (ADIM 54: kriterin adlandırdığı
      davranış ürün kodunda sevk edilmemişse SINIFI YANLIŞTIR → bulgu yaz, B→D TAŞIMA).
  (b) Defterdeki on yedi bulguyu ölçüp adjudication'a hazırlayan bir slice.

YÖNTEM (pazarlıksız, hangi hat olursa olsun):
  - Her assertion için NEGATİF KONTROL: tek noktalı kusur kur, yamanın UYGULANDIĞINI assert
    et (ADIM 88), koş, KIRMIZININ HANGİ ASSERTION'DA olduğunu OKU, geri al, `git status`.
  - GERİ ALMAYI git'ten yapma eğer taban COMMIT'Lİ DEĞİLSE — bellekte anlık görüntü tut
    (ADIM 111: `git checkout --` commit edilmemiş guard'ı sildi, üç kontrol birden patladı).
  - Bir kontrol yalnız HEDEF testi ve yalnız HEDEF assertion'ı düşürmelidir (ADIM 105).
  - Mevcut suite'in kusur altında YEŞİL kalması boşluğun ÖLÇÜMÜDÜR (ADIM 110).
  - Gölge gördüysen KALDIRMAYI dene, kaydetmekle yetinme (ADIM 101).

KAPANIŞ (CLAUDE.md §Session CLOSING, altı madde):
  - Tavanı MERGED ağaçta TAZE ölç, iki freeze'in farkından TÜRETME (ADIM 93/98/100).
  - Test eklediysen üretilmiş olguları tazele (ADIM 60); üretici backend/.venv ister.
  - Kickoff: ADIM112 dosyasını YAZ ve ADIM111'i `historical` yap (ikisi birlikte).
  - A08_COMPLETE mayını: A-08[^\n]{0,80}?(Complete|COMPLETE|PASS|Done|tamamlan|kapandı)
    TEK SATIRDA 80 karakter; kapsam CLAUDE.md + docs/STAGE2_HANDOFF.md + README +
    docs/CODEMAPS/*.md. KURALI DÜZELTME, PROZAYI DÜZELT: satırı ayır, kelimeyi koru.
  - docs kayıt-silme kapısı ARTIK DARALTILDI (ADIM 111): sayı taşıyan üretilmiş başlıkların
    (`## Class B (23)` -> `(21)`) commit'ini bloklamaz. Yine bloklarsa bu GERÇEK bir silmedir
    ya da bir yeniden adlandırmadır — diff'i oku, bypass etme.
  - Dal docs/stage-112-landed → PR → yeşil bekle → merge'ü KULLANICIDAN İSTE (self-merge
    bloklu, auto-merge ARMA). main ilerlediyse REBASE et, "Update branch" KULLANMA.
```
