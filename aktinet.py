#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
import bottle
import hashlib # računanje MD5 kriptografski hash za gesla
from datetime import datetime

# uvozimo ustrezne podatke za povezavo
import auth_public as auth

# uvozimo psycopg2
import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # se znebimo problemov s šumniki

import os
from drzave import drzave

# privzete nastavitve
SERVER_PORT = os.environ.get('BOTTLE_PORT', 8080)
RELOADER = os.environ.get('BOTTLE_RELOADER', True)
ROOT = os.environ.get('BOTTLE_ROOT', '/')
DB_PORT = os.environ.get('POSTGRES_PORT', 5432)


######################################################################
# Konfiguracija

# Vklopi debug, da se bodo predloge same osvežile in da bomo dobivali
# lepa sporočila o napakah.
bottle.debug(True)

# Datoteka, v kateri je baza
baza_datoteka = "fakebook.sqlite"

# Mapa s statičnimi datotekami
static_dir = "./static"

# Skrivnost za kodiranje cookijev
secret = "to skrivnost je zelo tezko uganiti 1094107c907cw982982c42"

######################################################################
# Pomožne funkcije

def password_md5(s):
    """Vrni MD5 hash danega UTF-8 niza. Gesla vedno spravimo v bazo
       kodirana s to funkcijo."""
    if not s:
        # Nočemo imeti praznih nizov za gesla!
        return
    h = hashlib.md5()
    h.update(s.encode('utf-8'))
    return h.hexdigest()

# Funkcija, ki v cookie spravi sporocilo
def set_sporocilo(tip, vsebina):
    bottle.response.set_cookie('message', (tip, vsebina), path='/', secret=secret)

# Funkcija, ki iz cookija dobi sporočilo, če je
def get_sporocilo():
    sporocilo = bottle.request.get_cookie('message', default=None, secret=secret)
    bottle.response.delete_cookie('message')
    return sporocilo

# To smo dobili na http://stackoverflow.com/questions/1551382/user-friendly-time-format-in-python
# in predelali v slovenščino. Da se še izboljšati, da bo pravilno delovala dvojina itd.
def pretty_date(time):
    """
    Predelaj čas (v formatu Unix epoch) v opis časa, na primer
    'pred 4 minutami', 'včeraj', 'pred 3 tedni' ipd.
    """
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.utcfromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time 
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days
    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "zdaj"
        if second_diff < 60:
            return "pred " + str(second_diff) + " sekundami"
        if second_diff < 120:
            return  "pred minutko"
        if second_diff < 3600:
            return "pred " + str( second_diff // 60 ) + " minutami"
        if second_diff < 7200:
            return "pred eno uro"
        if second_diff < 86400:
            return "pred " + str( second_diff // 3600 ) + " urami"
    if day_diff == 1:
        return "včeraj"
    if day_diff < 7:
        return "pred " + str(day_diff) + " dnevi"
    if day_diff < 31:
        return "pred " + str(day_diff//7) + " tedni"
    if day_diff < 365:
        return "pred " + str(day_diff//30) + " meseci"
    return "pred " + str(day_diff//365) + " leti"

def get_user(auto_login = True):
    """Poglej cookie in ugotovi, kdo je prijavljeni uporabnik,
       vrni njegov uporabnisko ime, ime in priimek. Če ni prijavljen, presumeri
       na stran za prijavo ali vrni None (advisno od auto_login).
    """
    # Dobimo uporabnisko ime iz piškotka
    uporabnik = bottle.request.get_cookie('uporabnik', secret=secret)
    # Preverimo, ali ta uporabnik obstaja
    if uporabnik is not None:
        cur.execute("SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s",
                  [uporabnik])
        r = cur.fetchone()
        if r is not None:
            # uporabnik obstaja, vrnemo njegove podatke
            return r
    # Če pridemo do sem, uporabnik ni prijavljen, naredimo redirect
    if auto_login:
        bottle.redirect('/prijava/')
    else:
        return None

def objave(limit=10,uporabnik=None):
    """Vrni dano število tračev (privzeto 10). Rezultat je seznam, katerega
       elementi so oblike [trac_id, avtor, ime_avtorja, cas_objave, vsebina, komentarji],
       pri čemer so komentarji seznam elementov oblike [avtor, ime_avtorja, vsebina],
       urejeni po času objave.
    """
    if uporabnik:
        cur.execute(
        """SELECT id, uporabnisko_ime, ime, priimek, extract(epoch from cas AT TIME ZONE 'UTC'), vsebina
            FROM objava JOIN uporabnik ON objava.avtor = uporabnik.uporabnisko_ime
            WHERE objava.avtor = %s
            ORDER BY cas DESC
            LIMIT %s
        """, [uporabnik,limit])
    else:
        cur.execute(
        """SELECT id, uporabnisko_ime, ime, priimek, extract(epoch from cas), vsebina
           FROM objava JOIN uporabnik ON objava.avtor = uporabnik.uporabnisko_ime
           ORDER BY cas DESC
           LIMIT %s
        """, [limit])
    # Rezultat predelamo v nabor.
    objave = tuple(cur)
    # Nabor id-jev tračev, ki jih bomo vrnili
    oids = (objava[0] for objava in objave)
    # Logično bi bilo, da bi zdaj za vsak trač naredili en SELECT za
    # komentarje tega trača. Vendar je drago delati veliko število
    # SELECTOV, zato se raje potrudimo in napišemo en sam SELECT.
    if uporabnik:
        cur.execute(
        """SELECT objava.id, uporabnisko_ime, ime, priimek, komentar.vsebina
        FROM
        (komentar JOIN objava ON komentar.id_objava = objava.id)
        JOIN uporabnik ON uporabnik.uporabnisko_ime = komentar.avtor
        WHERE 
        objava.id IN (SELECT id FROM objava WHERE objava.avtor=%s ORDER BY cas DESC LIMIT %s)
        ORDER BY
        komentar.cas
        """, [uporabnik, limit])
    else:
        cur.execute(
        """SELECT objava.id, uporabnisko_ime, ime, priimek, komentar.vsebina
        FROM
        (komentar JOIN objava ON komentar.id_objava = objava.id)
         JOIN uporabnik ON uporabnik.uporabnisko_ime = komentar.avtor
        WHERE 
        objava.id IN (SELECT id FROM objava ORDER BY cas DESC LIMIT %s)
        ORDER BY
        komentar.cas""", [limit])
    # Rezultat poizvedbe ima nerodno obliko, pretvorimo ga v slovar,
    # ki id trača preslika v seznam pripadajočih komentarjev.
    # Najprej pripravimo slovar, ki vse id-je tračev slika v prazne sezname.
    komentar = { oid : [] for oid in oids }
    # Sedaj prenesemo rezultate poizvedbe v slovar
    for (oid, uporabnisko_ime, ime, priimek, vsebina) in cur:
        komentar[oid].append((uporabnisko_ime, ime, priimek, vsebina))
    # Vrnemo nabor, kot je opisano v dokumentaciji funkcije:
    return ((oid, u, i, p, pretty_date(int(c)), v, komentar[oid])
            for (oid, u, i, p, c, v) in objave)

######################################################################
# Funkcije, ki obdelajo zahteve odjemalcev.

@bottle.route("/static/<filename:path>")
def static(filename):
    """Splošna funkcija, ki servira vse statične datoteke iz naslova
       /static/..."""
    return bottle.static_file(filename, root=static_dir)

@bottle.route("/")
def main():
    """Glavna stran."""
    # Iz cookieja dobimo uporabnika (ali ga preusmerimo na login, če
    # nima cookija)
    (uporabnik_prijavljen, ime, priimek) = get_user()
    # Morebitno sporočilo za uporabnika
    sporocilo = get_sporocilo()
    # Vrnemo predlogo za glavno stran
    return bottle.template("glavna.html",
                           ime=ime,
                           priimek=priimek,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           sporocilo=sporocilo)


@bottle.get("/prijava/")
def login_get():
    """Serviraj formo za prijavo."""
    return bottle.template("prijava.html",
                           napaka=None,
                           uporabnik=None)

@bottle.post("/prijava/")
def login_post():
    """Obdelaj izpolnjeno formo za prijavo"""
    # Uporabniško ime, ki ga je uporabnik vpisal v formo
    uporabnik = bottle.request.forms.uporabnik
    # Izračunamo MD5 has gesla, ki ga bomo spravili
    geslo = password_md5(bottle.request.forms.geslo)
    # Preverimo, ali se je uporabnik pravilno prijavil
    cur.execute("SELECT 1 FROM uporabnik WHERE uporabnisko_ime=%s AND geslo=%s",
              [uporabnik, geslo])

    # Zaradi probavanja!!!
    cur.execute("SELECT 1 FROM uporabnik WHERE uporabnisko_ime=%s and geslo=%s",
              [uporabnik, geslo])

    if cur.fetchone() is None:
        # Uporabnisko ime in geslo se ne ujemata
        return bottle.template("prijava.html",
                               napaka="Nepravilna prijava",
                               uporabnik=uporabnik)
    else:
        # Vse je v redu, nastavimo cookie in preusmerimo na glavno stran
        bottle.response.set_cookie('uporabnik', uporabnik, path='/', secret=secret)
        bottle.redirect("/")


@bottle.get("/odjava/")
def logout():
    """Pobriši cookie in preusmeri na login."""
    bottle.response.delete_cookie('uporabnik')
    bottle.redirect('/prijava/')

@bottle.get("/registracija/")
def login_get():
    """Prikaži formo za registracijo."""
    return bottle.template("registracija.html", 
                           uporabnik=None,
                           ime=None,
                           priimek=None,
                           napaka=None)

@bottle.post("/registracija/")
def register_post():
    """Registriraj novega uporabnika."""
    uporabnik = bottle.request.forms.uporabnik
    ime = bottle.request.forms.ime
    priimek = bottle.request.forms.priimek
    geslo1 = bottle.request.forms.geslo1
    geslo2 = bottle.request.forms.geslo2
    # Ali uporabnik že obstaja?
    cur.execute("SELECT 1 FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    if cur.fetchone():
        # Uporabnik že obstaja
        return bottle.template("registracija.html",
                               uporabnik=uporabnik,
                               ime=ime,
                               priimek=priimek,
                               napaka='To uporabniško ime je že zavzeto')
    elif not geslo1 == geslo2:
        # Geslo se ne ujemata
        return bottle.template("registracija.html",
                               uporabnik=uporabnik,
                               ime=ime,
                               priimek=priimek,
                               napaka='Gesli se ne ujemata')
    else:
        # Vse je v redu, vstavi novega uporabnika v bazo
        geslo = password_md5(geslo1)
        cur.execute("INSERT INTO uporabnik (uporabnisko_ime, ime, priimek, geslo) VALUES (%s, %s, %s, %s)",
                  (uporabnik, ime, priimek, geslo))
        # Daj uporabniku cookie
        conn.commit()
        bottle.response.set_cookie('uporabnik', uporabnik, path='/', secret=secret)
        bottle.redirect("/")

@bottle.route("/uporabnik/<uporabnik>/")
def user_wall(uporabnik):
    """Prikaži stran uporabnika"""
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    # Ime uporabnika (hkrati preverimo, ali uporabnik sploh obstaja)
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    # Seznam zadnjih 10 tračev
    ts = objave(limit=None, uporabnik=uporabnik)
    # Koliko sledilcev ima ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE zasledovani=%s", [uporabnik])
    st_z = cur.fetchone()
    # Koliko sledovanih ima ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE sledilec=%s", [uporabnik])
    st_s = cur.fetchone()
    # Prikažemo predlogo
    return bottle.template("profil.html",
                           profil_ime=ime,
                           profil_priimek=priimek,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           uporabnik=uporabnik,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           traci=ts)

@bottle.get("/uporabnik/<uporabnik>/uredi_profil/")
def profil(uporabnik, sporocila=[]):
    """Prikaži stran, kjer uporabnik uredi svoje podatke"""
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnisko_ime, ime_prijavljen, priimek_prijavljen) = get_user()
    if uporabnisko_ime != uporabnik:
        # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljen dostop do urejanja drugih profilov!")
        return bottle.redirect("/")
    # Ime uporabnika (hkrati preverimo, ali uporabnik sploh obstaja)
    cur.execute("""
    SELECT ime, priimek, spol, datum_rojstva, ulica, hisna_stevilka, kraj, drzava, postna_stevilka 
    FROM uporabnik 
    LEFT JOIN lokacija ON uporabnik.id_lokacija=lokacija.id
    LEFT JOIN posta ON lokacija.id_posta = posta.id
    WHERE uporabnisko_ime=%s
    """, [uporabnik])
    (ime, priimek, spol, datum_rojstva, ulica, hisna_stevilka, kraj, drzava, postna_stevilka) = cur.fetchone()
    # Prikažemo predlogo
    return bottle.template("uredi-profil.html",
                           uporabnik=uporabnik,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           profil_ime=ime_prijavljen,
                           profil_priimek=priimek_prijavljen,
                           uporabnik_prijavljen=uporabnisko_ime,
                           spol=spol,
                           datum_rojstva=datum_rojstva,
                           ulica=ulica,
                           hisna_stevilka=hisna_stevilka,
                           kraj=kraj,
                           drzava=drzava,
                           postna_stevilka=postna_stevilka,
                           sporocila=sporocila,
                           drzave=drzave)


    
@bottle.post("/uporabnik/<uporabnik>/uredi_profil/")
def sprememba(uporabnik):
    """Obdelaj formo za spreminjanje podatkov o uporabniku."""
    # Pridobimo stare podatke
    cur.execute("""
    SELECT ime, priimek, spol, datum_rojstva, ulica, hisna_stevilka, kraj, drzava, postna_stevilka 
    FROM uporabnik 
    LEFT JOIN lokacija ON uporabnik.id_lokacija=lokacija.id
    LEFT JOIN posta ON lokacija.id_posta = posta.id
    WHERE uporabnisko_ime=%s
    """, [uporabnik])
    (ime, priimek, spol, datum_rojstva, ulica, hisna_stevilka, kraj, drzava, postna_stevilka) = cur.fetchone()
    # Novo ime
    ime_novo = bottle.request.forms.ime
    # Nov priimek
    priimek_novo = bottle.request.forms.priimek
    # Staro geslo
    geslo1 = password_md5(bottle.request.forms.geslo1)
    # Novo geslo
    geslo2 = password_md5(bottle.request.forms.geslo2)
    # Potrdilo novega gesla
    geslo3 = password_md5(bottle.request.forms.geslo3)
    # Novo uporabnisko ime
    uporabnisko_novo = bottle.request.forms.uporabnisko_ime
    # "Nov" spol
    spol_nov = bottle.request.forms.spol
    # Nov datum rojstva
    datum_nov = bottle.request.forms.date
    # Nov naslov
    ulica_nova = bottle.request.forms.ulica
    hisna_st_nova = bottle.request.forms.hisna_stevilka
    drzava_nova = bottle.request.forms.drzava
    kraj_nov = bottle.request.forms.kraj
    postna_stevilka_nova = bottle.request.forms.postna_stevilka

    # Pokazali bomo eno ali več sporočil, ki jih naberemo v seznam
    sporocila = []

    # SPREMEMBA IMENA:
    if ime_novo and ime_novo != ime:
        cur.execute("UPDATE uporabnik SET ime=%s WHERE uporabnisko_ime=%s;", [ime_novo, uporabnik])
        sporocila.append(("alert-success", "Spreminili ste si ime."))

    # SPREMEMBA PRIIMKA:
    if priimek_novo and priimek_novo != priimek:
        cur.execute("UPDATE uporabnik SET priimek=%s WHERE uporabnisko_ime=%s;", [priimek_novo, uporabnik])
        sporocila.append(("alert-success", "Spreminili ste si priimek."))
        
    # SPREMEMBA DATUMA:
    if datum_nov and not (str(datum_nov) == str(datum_rojstva)):
        cur.execute("UPDATE uporabnik SET datum_rojstva=%s WHERE uporabnisko_ime=%s;", [datum_nov, uporabnik])
        sporocila.append(("alert-success", "Spreminili ste si datum rojstva."))

    # SPREMEBA GESLA:
    # Preverimo staro geslo
    
    if geslo1:
        cur.execute ("SELECT 1 FROM uporabnik WHERE uporabnisko_ime=%s AND geslo=%s;",
               [uporabnik, geslo1])
        if cur.fetchone():
            # Geslo je ok
            # Ali se ujemata novi gesli?
            if (geslo2 or geslo3) and geslo2 == geslo3:
                cur.execute ("UPDATE uporabnik SET geslo=%s WHERE uporabnisko_ime = %s;", [geslo2, uporabnik])
                sporocila.append(("alert-success", "Spremenili ste geslo."))
            else:
                sporocila.append(("alert-danger", "Gesli se ne ujemata"))
        else:
            sporocila.append(("alert-danger", "Nepravilen vnos starega gesla."))

    
    # NASTAVITEV SPOLA
    if spol_nov and spol_nov != spol:
        cur.execute("UPDATE uporabnik SET spol=%s WHERE uporabnisko_ime = %s", [spol_nov, uporabnik])
        sporocila.append(("alert-success", "Spreminili ste si spol."))
    p1 = ulica_nova != ulica or hisna_st_nova != hisna_st_nova or drzava_nova != drzava or kraj_nov != kraj or postna_stevilka_nova != postna_stevilka
    p2 = ulica_nova or hisna_st_nova or drzava_nova or kraj_nov or postna_stevilka_nova
    if p1 and p2:
        if not(postna_stevilka_nova and kraj_nov and drzava_nova and ulica_nova):
            # Za naslov so potrebna polja postne_st, kraj in drzava
            sporocila.append(("alert-danger", "Za nastavitev naslova je potrebno vnesti Poštno številko, Državo, Kraj in ulico."))
        else:
            # Preverimo, če je pošta že vnešen v bazi
            cur.execute("""SELECT id FROM posta WHERE postna_stevilka=%s AND kraj=%s AND drzava=%s""",[postna_stevilka_nova, kraj_nov, drzava_nova])
            (id_p) =  cur.fetchone()

            if id_p:
                id_p = id_p[0]
                # Ta pošta že obstaja 
                # Ali obstaja lokacija?
                cur.execute("""SELECT id FROM lokacija WHERE ulica=%s AND hisna_stevilka=%s AND id_posta=%s""", [ulica_nova, hisna_st_nova,id_p])
                (id_l) = cur.fetchone()
                if id_l:
                    id_l = id_l[0]
                    # Ta lokacija že obstaja
                    cur.execute ("UPDATE uporabnik SET id_lokacija=%s WHERE uporabnisko_ime = %s;", [id_l, uporabnik])
                else:
                    cur.execute("""INSERT INTO lokacija(ulica,hisna_stevilka,id_posta) VALUES (%s, %s, %s) RETURNING id""", [ulica_nova, hisna_st_nova, id_p])
                    (id_l,) = cur.fetchone()
                    cur.execute ("UPDATE uporabnik SET id_lokacija=%s WHERE uporabnisko_ime = %s;", [id_l, uporabnik])
            else:
                # Najprej vnesemo pošto
                cur.execute("""INSERT INTO posta(postna_stevilka,kraj,drzava) VALUES (%s, %s, %s) RETURNING id""",[postna_stevilka_nova, kraj_nov, drzava_nova])
                (id_p,) = cur.fetchone()
                cur.execute("""INSERT INTO lokacija(ulica,hisna_stevilka,id_posta) VALUES (%s, %s, %s) RETURNING id""", [ulica_nova, hisna_st_nova, id_p])
                (id_l,) = cur.fetchone()
                cur.execute ("UPDATE uporabnik SET id_lokacija=%s WHERE uporabnisko_ime = %s;", [id_l, uporabnik])
            sporocila.append(("alert-success", "Spreminili ste naslov."))

    
    conn.commit()
                
    # Prikažemo stran z uporabnikom, z danimi sporočili. Kot vidimo,
    # lahko kar pokličemo funkcijo, ki servira tako stran
    return bottle.template("uredi-profil.html",
                           uporabnik=uporabnik,
                           ime=ime,
                           priimek=priimek,
                           profil_ime=ime,
                           profil_priimek=priimek,
                           uporabnik_prijavljen=uporabnik,
                           spol=spol_nov,
                           datum_rojstva=datum_nov,
                           ulica=ulica_nova,
                           hisna_stevilka=hisna_st_nova,
                           kraj=kraj_nov,
                           drzava=drzava_nova,
                           postna_stevilka=postna_stevilka_nova,
                           sporocila=sporocila,
                           drzave=drzave)

@bottle.get('/uporabnik/<uporabnik>/sledilci/<limit:int>/')
def pokazi_sledilce(uporabnik, limit):
    """Pokaži stran vseh sledilcev uporabnika"""
    # Kdo je prijavljen?
    (uporabnisko_ime, ime_prijavljen,priimek_prijavljen) = get_user()
    # Dobim vse sledilce iz baze
    cur.execute("""
    SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE 
    uporabnisko_ime IN 
    (SELECT sledilec FROM sledilec WHERE zasledovani=%s) 
    ORDER BY uporabnisko_ime LIMIT %s
    """, (uporabnik, limit))
    sledilci = []
    for (uporabnik_sledilec, ime_sledilec, priimek_sledilec) in cur:
        sledilci.append((uporabnik_sledilec, ime_sledilec, priimek_sledilec))
    # Koliko sledovanih ima ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE zasledovani=%s", [uporabnik])
    (st_s,) = cur.fetchone()
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    return bottle.template("sledilci.html",
                           uporabnik=uporabnik,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           st_p=limit,
                           st_s=st_s,
                           uporabnik_prijavljen=uporabnisko_ime,
                           profil_ime=ime,
                           profil_priimek=priimek,
                           sledilci=sledilci)

@bottle.get('/uporabnik/<uporabnik>/zasledovani/<limit:int>/')
def pokazi_zasledovane(uporabnik, limit):
    """Pokaži stran vseh sledilcev uporabnika"""
    # Kdo je prijavljen?
    (uporabnisko_ime, ime_prijavljen,priimek_prijavljen) = get_user()
    # Dobim vse sledilce iz baze
    cur.execute("""
    SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE 
    uporabnisko_ime IN 
    (SELECT zasledovani FROM sledilec WHERE sledilec=%s) 
    ORDER BY uporabnisko_ime LIMIT %s
    """, (uporabnik, limit))
    zasledovani = []
    for (uporabnik_sledilec, ime_sledilec, priimek_sledilec) in cur:
        zasledovani.append((uporabnik_sledilec, ime_sledilec, priimek_sledilec))
    # Koliko ljudi zasleduje ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE sledilec=%s", [uporabnik])
    (st_z,) = cur.fetchone()
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    return bottle.template("zasledovani.html",
                           uporabnik=uporabnik,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           st_p=limit,
                           st_z=st_z,
                           profil_ime=ime,
                           uporabnik_prijavljen=uporabnisko_ime,
                           profil_priimek=priimek,
                           zasledovani=zasledovani)


######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password, port=DB_PORT)
#conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# poženemo strežnik na podanih vratih, npr. http://localhost:8080/
bottle.run(host='localhost', port=SERVER_PORT, reloader=RELOADER)