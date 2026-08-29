# Használat

A G5EC napló frissítése Google Docsból, elejétől a végéig. A miértekért lásd a
[README.md](README.md)-t, az egyes scriptek részleteiért a
[gdoc_import](gdoc_import/README.md) és az [autolink](autolink/README.md) saját
leírását.

## Egyszeri teendő a gépen

`python3` és `pandoc` kell, semmi más — minden script kizárólag a standard
library-t használja, így nincs virtuális környezet és pip sem kell hozzá.

```bash
sudo apt install pandoc              # vagy: brew install pandoc
```

## A négy futtatás

Mindegyik a repo gyökeréből indítható, mert az alapértelmezéseik a scripthez
képest relatívak, nem a munkakönyvtárhoz:

```bash
python3 tools/gdoc_import/fetch_gdoc.py        # letöltés + konverzió  -> build/out/
python3 tools/gdoc_import/split_notes.py       # fülönként egy jegyzet -> build/notes/   (8)
python3 tools/gdoc_import/split_sessions.py    # a napló fül sessionönként -> build/sessions/ (69)
python3 tools/autolink/autolink.py --scope-root tools/gdoc_import/build/sessions
```

A negyedik alapból csak megmutatja, mit írna. Ha rendben van a lista, ugyanaz
`--apply`-jal:

```bash
python3 tools/autolink/autolink.py --scope-root tools/gdoc_import/build/sessions --apply
```

Eddig a pontig semmi nem nyúlt a wikihez, a `build/` eldobható és bármikor
újragenerálható.

## Utána a másolás

Ez a kézi lépés, átnézés után:

```bash
cp tools/gdoc_import/build/notes/*.md      content/G5eC/log/
cp tools/gdoc_import/build/sessions/*.md   content/G5eC/log/
cp tools/gdoc_import/build/sessions/pics/* content/G5eC/log/pics/
```

A napló mappájában 8 fül-jegyzet van (köztük a teljes `G5EC party log.md`,
szándékosan duplikátumként), 69 session és a `pics/`, tehát a másolás pont
ezeket írja felül. Mivel a linkelés már megtörtént, a másolat kész linkekkel
érkezik — ezért nem tud elromlani a sorrend.

## Ellenőrzés

```bash
python3 tools/autolink/autolink.py
```

`--scope-root` nélkül a wikire néz. Ha „Would write 0 links” a válasz, minden
link átjött a másolással. Ha nem nullát mond, akkor valami mégis lemaradt, és
ugyanez `--apply`-jal helyrerakja.

## Amit alkalmanként érdemes

Ha csak a feldolgozáson állítasz és nem akarsz újra letölteni, a
`fetch_gdoc.py --skip-download` a korábbi letöltést használja újra.

Ha új jegyzetek vagy címsorok kerültek a wikibe, a `autolink.py --scan`
felsorolja az új linkelhető címsorjelölteket az `autolink.ini`-be kikapcsolva.

## A munkalista

Melyik kiemelt név mögött nincs még jegyzet:

```bash
python3 tools/autolink/autolink.py --missing
```

Ez írja a [missing.md](autolink/missing.md)-t — a fájl generált, nem kézzel
karbantartott, és a `--report` mondja meg, hova kerül, alapból pont oda. A
linkeket nem bántja, mert az írásukhoz `--apply` kell, a reportot viszont
előnézetben is felülírja.

Időbélyeg nincs benne, szándékosan: az újrafuttatás csak akkor jelenik meg
változásként a gitben, ha tényleg változott a napló vagy a wiki. Ezért van
commitolva is, így a munkalista futtatás nélkül olvasható a repóban.

A report abból készül, ami épp hatókörben van, tehát `--scope-root`-tal a friss
darabolásról szól, anélkül a wikiben lévő naplókról.
