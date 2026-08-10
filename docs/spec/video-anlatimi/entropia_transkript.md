0:02 saniye Entropia arayüzünün anlatımına başlıyorum.

0:06 saniye Eee, şimdi şu anda karşımızda iki tane ekran görünüyor. Sağ
tarafta bizim entropia arayüzünü tasarlarken ürettiğimiz prototip.

0:13 saniye Sol tarafta ise bu prototip ve anlatım sonrasında
oluşturulan kodlanmış yapı.

0:30 saniye Kodlanmış yapıda önemli eksiklikler var. Hatta çok büyük
eksiklikler var.

0:38 saniye Neredeyse hiçbir şey tamamlanmamış diyebiliriz. Şöyle
hızlıca nelerin eksik olduğunu yüzeysel de olsa değinelim ve sonra biraz
detayına girmeye çalışalım.

0:48 saniye Prototipte önce kurduğumuz önemli yapılardan birisi Add
Strategy yapısı. Mainboard'un açılır menüsünde bulunuyor. Göründüğü
gibi.

0:55 saniye Add Strategy'ye tıkladığımızda karşımıza bu şekilde bir
yatay ince dikdörtgen geliyor.

1:10 Bu stratejinin kapalı bir yapı olarak bulunmasını sağlıyor bize.

1:17 Yanında bulunan aşağı yönlü oka tıkladığımızda bu stratejinin
ayarlanma detaylarını görüyoruz.

1:32 Nedir mesela stratejinin adı?

1:35 Rational Family diye tanımladığımız bu arayüze ait bir tanımlama,
hangi markette olduğu, data ve uygulamanın nasıl yapılacağı, data
source'un seçilmesi, backtestin hangi aralıklarda gerçekleşeceği...

2:08 Pozisyona girme mantığı, signal block yapısı, indicator block
yapısı, condition block yapısı, pozisyondan çıkma mantığı, stop yapısı
vesaire...

2:25 Strategic Details altında bütün ayarlamaları yapabiliyoruz.

2:33 Bunları yaptıktan sonra çalıştıra basıp backtesti
gerçekleştirebiliriz.

2:43 Mainboard'da strateji ve yatay dikdörtgenle eklemenin temel mantığı
şu: Entropia dediğimiz kavram bir strateji evreni.

2:52 Ben burada birden fazla strateji barındırıp bunların birlikte nasıl
çalıştığını, tek başına nasıl çalıştığını analiz edebilmeliyim.

3:08 Hatta bizim buraya eklediğimiz Add Outsource Signal diye bir
seçenek var.

3:13 Biz burada Trade Log ekleyebiliyoruz.

3:18 Trade Log eklediğimiz zaman bunun strateji evrenine nasıl katkı
sunduğunu görebiliriz.

3:27 Örneğin son 10 yılda gerçekleşmiş ve belli bir kâr oranına sahip
bir stratejinin bütün trade'lerini sisteme ekleyebiliriz.

3:35 Bunların toplam strateji evrenine nasıl katkı sunduğunu, entropiyi
nasıl değiştirdiğini görebiliriz.

3:50 O yüzden bu yatay dikdörtgen ve açılır yapı Entropia arayüzünün
çekirdeğini oluşturmaktadır. Buna Entropia Core diyebiliriz.

4:08 Kodlama kısmına geldiğimizde Mainboard açılır menü tamam. Ancak Add
Strategy butonuna tıkladığımızda ne olduğunu anlayamadığımız bir yapı
çıkıyor.

4:31 Öncelikle Create Strategy diye bir seçenek var.

4:36 Ben bu iki kelimeyi bu arayüzde yan yana kullandığımızı
hatırlamıyorum.

4:42 Böyle bir şey olmayacak. Create Strategy diye bir kavram yok.
Create Package diye bir kavramımız var.

4:53 My Drafts. Draft nedir? Asla stratejiyle ilgili draft kelimesini
yan yana getirmedik.

5:02 Attached Strategies... Bunlar konunun çok uzağında.

5:10 Kesinlikle backtest arayüzünün çekirdeğini anlayamamış görünüyor bu
kodlamayı yapan AI aracı.

5:27 Rational Families'e gelelim.

5:40 Add Family diyerek yeni bir Rational Family tanımlayabiliyoruz.

5:49 Eklediğimiz package türlerini bu strateji aileleriyle
ilişkilendirebiliyoruz.

6:04 Save Assignment ile yaptığımız değişiklikleri kaydedebiliriz.

6:17 Kodlanan Rational Families sayfası yeterli görünmüyor.

6:42 Buradaki yapı çok sade. Add diyoruz, direkt ekliyor. Daha sonra
Edit diyerek yapıyı kurabiliyoruz.

7:16 Portfolio Equity Allocation kısmına gelelim.

7:23 Başta önemsemediğim bir alandı ama prototipin sonlarına doğru
önemli olduğunu fark ettim.

7:32 Çünkü strateji evreni kuruyorsak stratejilerin toplam portföyü
nasıl paylaşacağını üst seviyede tanımlamamız gerekiyor.

7:59 O yüzden Mainboard kısmına Portfolio Equity Allocation butonu
ekledik.

8:17 Use Allocation Backtest diyoruz.

8:25 Yapacağımız backtest analizinde bu sayfadaki allocation sistemini
kullan diyoruz.

8:31 Seçili olduğunda bütün stratejiler, trading signal, trade log gibi
yapılar buradan allocate ediliyor.

8:54 Strategy 1, Strategy 2, Trade 1, Trade Log 1 şeklinde devam ediyor
ve alacakları paylar burada belirleniyor.

9:02 Kodlanan yapıda ise böyle bir yapı göremiyoruz.

9:13 Herhangi bir ekleme seçeneği de sunmuyor.

9:24 Market Data kısmına gelelim.

10:15 Market Data backtestte kullanılacak özel bir data.

10:30 Ortak bir yapıdan yüklenmesini sağlıyoruz ve Strategic Details
içinden seçiliyor.

10:49 Kodlanan yapıda Add Market Dataset kısmı çalıştırılamaz gibi
duruyor.

11:00 Çünkü veri upload edemiyoruz.

11:08 Örneğin Binance historical data indirip buraya upload edeceğim.

11:16 Bu yüklenen datanın Entropia'nın kullanabileceği standart yapıya
dönüşmesini sağlayacağım.

11:32 Add Market Dataset diyerek süreç başlıyor.

11:43 Raw Source File / Browse File.

11:50 Ham kaynak dosyayı yüklüyoruz.

11:57 Dataset adını, market türünü, timeframe'i ve diğer bilgileri
giriyoruz.

12:07 Yapıda eksiklik var mı diye analiz ediliyor.

12:14 Eğer yapı uygunsa Create Dataset ya da Approve for Use seçiliyor.

12:24 Backtest ekranında kullanılabilir hale geliyor.

12:30 Bütün süreç bu şekilde işleyecek.

12:37 Ama burada süreci başlatacak olan ham kaynak dosya yükleme
seçeneği maalesef yok.
