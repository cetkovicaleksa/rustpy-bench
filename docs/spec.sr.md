# 1.1.1 Teme iz računarstva visokih performansi

Potrebno je odabrati neki od problema iz oblasti računarstva visokih performansi (engl. *High Performance Computing*, skr. *HPC*) po ličnom nahođenju. Primeri nekih problema su:

* problem n-tela (engl. *n-body problem*),  
* simulacija dvostrukog klatna (engl. *double pendulum simulation*) \- **maksimalna ocena 6**,  
* Kanonov algoritam za množenje matrica \- **maksimalna ocena 6**,  
* dinamika fluida,  
* *Navier–Stokes* jednačina,  
* parcijalne diferencijalne jednačine,  
* problemi linearne algebre,  
* manipulacija grafovima,  
* celularni automati,  
* itd.

Za izabrani problem, potrebno je uraditi sledeće:

1. (25 poena) **Rešiti problem upotrebom programskog jezika *Python*:**  
   * Implementirati **sekvencijalnu verziju rešenja** upotrebom programskog jezika ***Python***. Rezultat mora biti bar jedna datoteka koja reprezentuje promene stanja modelovanog sistema (po iteracijama, ukoliko je problem rešavan iterativnim metodom).  
   * Implementirati paralelizovanu verziju rešenja upotrebom multiprocessing biblioteke programskog jezika Python. Rezultat mora biti bar jedna datoteka koja reprezentuje promene stanja  modelovanog sistema (po iteracijama, ukoliko je problem rešavan iterativnim metodom).  
2. (26 poena) **Rešiti problem upotrebom programskog jezika *Rust*:**  
   * Implementirati **sekvencijalnu verziju rešenja** upotrebom programskog jezika ***Rust***. Rezultat mora biti bar jedna datoteka koja reprezentuje promene stanja modelovanog sistema (po iteracijama, ukoliko je problem rešavan iterativnim metodom).  
   * Implementirati **paralelizovanu verziju rešenja** uz oslonac na **niti** (engl. *threads*). Rezultat mora biti bar jedna datoteka koja reprezentuje promene stanja modelovanog sistema (po iteracijama, ukoliko je problem rešavan iterativnim metodom).  
3. (9 poena) Uraditi **eksperimente jakog i slabog skaliranja,** koji će uporediti dobijeno **ubrzanje paralelizovane *Python* implementacije** rešenja u odnosu na **sekvencijalnu implementaciju upotrebom istog jezika**.  
4. (10 poena) Uraditi **eksperimente jakog i slabog skaliranja** koji će uporediti dobijeno **ubrzanje paralelizovane *Rust* implementacije** rešenja u odnosu na **sekvencijalnu implementaciju upotrebom istog jezika**.  
5. (10 poena) **Vizualizacija rešenja** (po iteracijama, ukoliko je korišćen iterativni model za rešavanje problema) na osnovu prethodno generisanih datoteka, a uz oslonac na ***Rust*** okruženje. Dozvoljena je upotreba grafičkih biblioteka poput [*Plotters*](https://github.com/plotters-rs/plotters) ili slično.

**Eksperimente jakog i slabog skaliranja** opisati u formi **izveštaja**. Tom prilikom, potrebno je ispoštovati sledeće stavke:

* Navesti tehničke detalje koji se tiču hardverske i softverske arhitekture sistema na kom su rađeni eksperimenti:  
  * model procesora, radni takt, organizacija *cache* memorije, broj fizičkih/logičkih jezgara, broj *NUMA node*\-ova, itd.  
  * tip i količina RAM memorije  
  * Operativni sistem  
  * Dodatne biblioteke koju su korišćene, kao i njihove verzije  
  * ostale informacije koje mogu uticati na rezultate eksperimenata.  
* Odrediti procenat sekvencijalnog dela koda koji se po prirodi problema ne može paralelizovati.  
* Odrediti procenat paralelnog dela koda koji se može paralelizovati.  
* Odrediti teorijske maksimume ubrzanja u skladu sa *Amdalovim*, odnosno *Gustafsonovim* zakonom. Kao veoma koristan izvor informacija može poslužiti [sledeći članak](https://www.kth.se/blogs/pdc/2018/11/scalability-strong-and-weak-scaling/).  
* Neophodno je generisati bar 4 grafika:  
  * jako skaliranje *Python* paralelne implementacije u skladu sa Amdalovim zakonom  
  * jako skaliranje *Rust* paralelne implementacije u skladu sa Amdalovim zakonom  
  * slabo skaliranje *Python* paralelne implementacije u skladu sa Gustafsonovim zakonom  
  * slabo skaliranje *Rust* paralelne implementacije u skladu sa Gustafsonovim zakonom  
* Na svakom od prethodno pomenutih grafika, x-osa predstavlja broj procesorskih jezgara, dok y-osa predstavlja ostvareno ubrzanje. Takođe, na svakom grafiku nacrtati liniju teorijskog maksimuma (idealnog skaliranja) i uporediti je sa dobijenim rezultatima.  
* Kod eksperimenta slabog skaliranja, objasniti na koji način se manipuliše poslom, tj. kako se modifikacijom parametara postiže konstantan posao po procesorskom jezgru.  
* Svaki grafik treba da sledi potporna tabela sa informacijama o srednjem vremenu izvršavanja, standardnoj devijaciji, kao i o eventualnim *outlier*\-ima. Kako bi rezultati bili relevantni, za svaku kombinaciju parametara jakog, odnosno slabog skaliranja (broj procesorskih jezgra, veličina problema iskazana odgovarajućom kombinacijom ulaznih argumenata programa...), ekskluzivno izvršiti programsko rešenje 30-ak puta.  
* Dodatne informacije koje se tiču jakog i slabog skaliranja možete pronaći u [navedenom članku](https://www.kth.se/blogs/pdc/2018/11/scalability-strong-and-weak-scaling/).  

## Izrada projekta za maksimalnu ocenu 6:

Ukoliko se student odluči za olakšanu verziju projekta za maksimalnu ocenu 6, potrebno je da izabere jednu od tema iz računarstva visokih performansi i da odradi Python ili Rust implementaciju po gore navedenim zahtevima (bez eksperimenata skaliranja i vizuelizacije). ***Studenti koji se prijave za ovu opciju nemaju pravo izlaska na test za preostalih 20 poena.***

## Primeri adaptacija predefinisanih tema:

* [Mandelbrot generator](https://github.com/gazdicdanica/mandelbrot_generator)  
* [Fraktalna stabla](https://github.com/fmladenovic/FractalTree),  
* [Računanje determinante matrice primenom Laplasovog razvoja po prvoj vrsti](https://gitlab.com/mihajlokusljic/determinantcalculator),  
* [Analiza serijske i parallelne implementacije algoritama baziranih na Monte-Karlo metodi](https://github.com/DusanStevic/NTP/blob/master/diplomski_rad_dusan_stevic_sw_10_2016.pdf),  
* Kanonov algoritam za množenje matrica (primer jednog projekta na ovu temu možete pronaći na [linku](https://github.com/MicaTravica/ntp/blob/master/Izve%C5%A1taj.pdf)),  
* [Dinamika fluida](https://github.com/Balenko/ntp2019),  
* [2D konvolucija](https://github.com/vujadinovicn/2d-convolution-hpc),  
* [Random Forest](https://github.com/permitt/random-forest),  
* [Huffman Coding Algorithm (ocena 6\)](https://github.com/didulidu/NTP),  
* Itd.