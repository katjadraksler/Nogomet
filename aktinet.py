#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
import bottle
import datetime
import hashlib # računanje MD5 kriptografski hash za gesla
from datetime import datetime

# uvozimo ustrezne podatke za povezavo
import auth_katja as auth

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
    bottle.response.delete_cookie('message', path="/")
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
        """SELECT id, uporabnisko_ime, ime, priimek, cas, vsebina
            FROM objava JOIN uporabnik ON objava.avtor = uporabnik.uporabnisko_ime
            WHERE objava.avtor = %s
            ORDER BY cas DESC
            LIMIT %s
        """, [uporabnik,limit])
    else:
        cur.execute(
        """SELECT id, uporabnisko_ime, ime, priimek, cas, vsebina
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
        """SELECT objava.id, uporabnisko_ime, ime, priimek, komentar.vsebina, komentar.cas, komentar.id
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
        """SELECT objava.id, uporabnisko_ime, ime, priimek, komentar.vsebina, komentar.cas, komentar.id
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
    for (oid, uporabnisko_ime, ime, priimek, vsebina, kc, kid) in cur:
        komentar[oid].append((uporabnisko_ime, ime, priimek, vsebina, pretty_date(kc), kid))
    # Vrnemo nabor, kot je opisano v dokumentaciji funkcije:
    return ((oid, u, i, p, pretty_date(c), v, komentar[oid])
            for (oid, u, i, p, c, v) in objave)

def objave_prijateljev( uporabnik=None):
    """Vrni dano število tračev od oseb, ki jih slediš (privzeto 5). Rezultat je seznam, katerega
       elementi so oblike [trac_id, avtor, ime_avtorja, cas_objave, vsebina, komentarji],
       pri čemer so komentarji seznam elementov oblike [avtor, ime_avtorja, vsebina],
       urejeni po času objave.
    """
    cur.execute(
    """SELECT id,uporabnisko_ime, ime, priimek, extract(epoch from objava.cas), vsebina 
        FROM uporabnik JOIN (objava JOIN sledilec ON objava.avtor = sledilec.zasledovani) 
        ON uporabnik.uporabnisko_ime = sledilec.zasledovani
        WHERE sledilec = %s 
        ORDER BY objava.cas DESC
        LIMIT 6
    """, [uporabnik])
    
    # Rezultat predelamo v nabor.
    objave = tuple(cur)
    # Nabor id-jev tračev, ki jih bomo vrnili
    oids = (objava[0] for objava in objave)
    # Logično bi bilo, da bi zdaj za vsak trač naredili en SELECT za
    # komentarje tega trača. Vendar je drago delati veliko število
    # SELECTOV, zato se raje potrudimo in napišemo en sam SELECT.
    
    cur.execute(
    """SELECT objava.id, uporabnisko_ime, ime, priimek, komentar.vsebina, extract(epoch from komentar.cas)
    FROM
    (komentar JOIN objava ON komentar.id_objava = objava.id)
    JOIN uporabnik ON uporabnik.uporabnisko_ime = komentar.avtor
    WHERE
    objava.id IN
    (SELECT objava.id FROM uporabnik JOIN (objava JOIN sledilec ON objava.avtor = sledilec.zasledovani) 
    ON uporabnik.uporabnisko_ime = sledilec.zasledovani
    WHERE sledilec = %s
    ORDER BY objava.cas DESC
    LIMIT 6)
    ORDER BY komentar.cas DESC
    LIMIT 3
    """, [uporabnik])

    # Rezultat poizvedbe ima nerodno obliko, pretvorimo ga v slovar,
    # ki id trača preslika v seznam pripadajočih komentarjev.
    # Najprej pripravimo slovar, ki vse id-je tračev slika v prazne sezname.
    komentar = { oid : [] for oid in oids }
    # Sedaj prenesemo rezultate poizvedbe v slovar
    for (oid, uporabnisko_ime, ime, priimek, vsebina, kc) in cur:
        komentar[oid].append((uporabnisko_ime, ime, priimek, vsebina, pretty_date(int(kc))))
    # Vrnemo nabor, kot je opisano v dokumentaciji funkcije:
    return ((oid, u, i, p, pretty_date(int(c)), v, komentar[oid])
            for (oid, u, i, p, c, v) in objave)

def upravljaj_sledilca(uporabnik, hoce_slediti):
    """Prijavljen uporabnik bo zacel oz. nehal slediti uporabniku."""
    (uporabnik_prijavljen,ime, priimek) = get_user()
    if hoce_slediti:
        cur.execute("INSERT INTO sledilec VALUES (%s, %s)",[uporabnik_prijavljen, uporabnik])
    else:
        cur.execute("DELETE FROM sledilec WHERE sledilec=%s AND zasledovani=%s",[uporabnik_prijavljen, uporabnik])
    conn.commit()
    return uporabnik_prijavljen

def dobi_zasledovane(uporabnik):
    # Dobim vse zasledovane iz baze
    cur.execute("""
    SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE 
    uporabnisko_ime IN 
    (SELECT zasledovani FROM sledilec WHERE sledilec=%s)
    ORDER BY ime ASC, priimek ASC 
    """, [uporabnik])
    return cur.fetchall()

######################################################################
# Funkcije, ki obdelajo zahteve odjemalcev.

@bottle.get("/static/<filename:path>")
def static(filename):
    """Splošna funkcija, ki servira vse statične datoteke iz naslova
       /static/..."""
    return bottle.static_file(filename, root=static_dir)

@bottle.get("/")
def main():
    """Glavna stran."""
    # Iz cookieja dobimo uporabnika (ali ga preusmerimo na login, če
    # nima cookija)
    (uporabnik_prijavljen, ime, priimek) = get_user()
    # Morebitno sporočilo za uporabnika
    sporocilo = get_sporocilo()
    # Vrnemo predlogo za glavno stran

    
    #Najnovejše objave oseb, ki jih uporabnik sledi
    ts = objave_prijateljev(uporabnik=str(uporabnik_prijavljen))

    #Dogodki, ki bi glede na zanimanje zanimali uporabnika
    
    cur.execute("""SELECT uporabnik.ime, uporabnik.priimek, 
                    REPLACE(aktivnost.ime, '_', ' ') as aktivnost, dogodek.datum,posta.kraj
                    FROM
                    (((dogodek LEFT JOIN aktivnost ON dogodek.id_aktivnost = aktivnost.id)
                    LEFT JOIN
                    uporabnik ON dogodek.organizator = uporabnik.uporabnisko_ime)
                    LEFT JOIN lokacija ON dogodek.id_lokacija = lokacija.id)
                    LEFT JOIN posta ON lokacija.id_posta = posta.id
                    WHERE aktivnost.id IN
                    (SELECT aktivnost.id FROM
                    tip_aktivnosti JOIN (aktivnost JOIN se_ukvarja ON aktivnost.id = se_ukvarja.id_aktivnost)
                    ON tip_aktivnosti.id = aktivnost.tip
                    WHERE se_ukvarja.uporabnisko_ime = %s) AND NOT dogodek.organizator = %s
                    LIMIT 10
                    """, [uporabnik_prijavljen, uporabnik_prijavljen])

    return bottle.template("glavna.html",
                            dogodki = cur,
                            traci=ts,
                            ime=ime,
                            priimek=priimek,
                            uporabnik_prijavljen=uporabnik_prijavljen,
                            sporocilo=sporocilo)

@bottle.get("/uporabnik/<uporabnik>/dodaj_dogodek/")
def nov_dogodek(uporabnik):
    """Glavna stran."""
    # Iz cookieja dobimo uporabnika (ali ga preusmerimo na login, če
    # nima cookija)

    (uporabnik_prijavljen, ime, priimek) = get_user()

    if uporabnik_prijavljen != uporabnik:
    # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljena objava dogodka z drugim uporabniskim imenom!")
        return bottle.redirect("/")
    
    cur.execute("SELECT REPLACE(aktivnost.ime, '_', ' ') FROM aktivnost ORDER BY aktivnost.ime")

    return bottle.template("dodaj_dogodek.html",
                           ime=ime,
                           priimek=priimek,
                           aktivnosti = cur,
                           uporabnik_prijavljen=uporabnik_prijavljen)

@bottle.post("/uporabnik/<uporabnik>/dodaj_dogodek/")
def dodaj_dogodek(uporabnik):

    #Uporabnik, ki je prijavljen
    (uporabnik_prijavljen, ime, priimek) = get_user()

    aktivnost = bottle.request.forms.aktivnost
    datum = bottle.request.forms.datum
    cas = bottle.request.forms.cas
    stevilo_udelezencev = bottle.request.forms.stevilo_udelezencev
    opis = bottle.request.forms.opis
    ulica = bottle.request.forms.ulica
    hisna_stevilka = bottle.request.forms.hisna_stevilka
    postna_stevilka = bottle.request.forms.postna_stevilka
    kraj = bottle.request.forms.kraj
    drzava = bottle.request.forms.drzava

    #ČAS - preoblikujemo
    if cas:
        cas = cas + ':00'
    else:
        set_sporocilo("alert-danger", "Čas je obvezen argument")
        return bottle.redirect("/")
    
    #DATUM
    if not datum:
        set_sporocilo("alert-danger", "Datum je obvezen argument")
        return bottle.redirect("/")

    #AKTIVNOST - Zamenjemo aktivnost_ime z aktivnost_id
    if not aktivnost:
        set_sporocilo("alert-danger", "Aktivnost je obvezen argument")
        return bottle.redirect("/")
    else:
        cur.execute("SELECT aktivnost.id FROM aktivnost WHERE aktivnost.ime = REPLACE(%s, ' ', '_')",
                            [aktivnost])          
        (aktivnost,) = cur.fetchone()

    #LOKACIJA
    #Potrebni podatki, da sploh imamo lokacijo
    if ulica and hisna_stevilka and postna_stevilka and  kraj and drzava:
        # Najprej poiščemo pošto v bazi
        cur.execute("SELECT posta.id FROM posta WHERE postna_stevilka = %s AND kraj = %s AND drzava = %s",
                                [postna_stevilka, kraj, drzava])
        #Pošta je v bazi
        if cur.fetchone():
            cur.execute("SELECT posta.id FROM posta WHERE postna_stevilka = %s AND kraj = %s AND drzava = %s",
                                [postna_stevilka, kraj, drzava])
            (id_posta,) = cur.fetchone()
            print('POŠTA JE V BAZI. Id pošte', id_posta)

            #Poiščemo lokacijo
            cur.execute("SELECT lokacija.id FROM lokacija WHERE ulica = %s AND hisna_stevilka = %s AND id_posta = %s",
                                [ulica, hisna_stevilka, id_posta])
            
            #Lokcaija je v bazi
            if cur.fetchone():
                cur.execute("SELECT lokacija.id FROM lokacija WHERE ulica = %s AND hisna_stevilka = %s AND id_posta = %s",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()
                print('LOKACIJA JE V BAZI. Id lokacije', id_lokacija)

            #Lokacije ni v bazi. Jo dodamo
            else:
                cur.execute("INSERT INTO lokacija (ulica,hisna_stevilka, id_posta) VALUES (%s, %s, %s) RETURNING id",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()
                print('LOKACIJO SMO DODALI V BAZO. Id lokacije', id_lokacija)

        #Pošte ni v bazi => Lokacije ni v bazi. Ju dodamo
        else:
            #Pogledamo ali pošto sploh lahko dodamo v bazo
            cur.execute("SELECT 1 FROM posta WHERE postna_stevilka = %s AND drzava = %s",
                      [postna_stevilka,drzava])

            #Poste ne moremo dodati ((stevilka,drzava) je UNIQUE)
            if cur.fetchone():
                set_sporocilo("alert-danger", "Ta pošta ne obstaja")
                return bottle.redirect("/")
            #Posto lahko dodamo
            else:
                cur.execute("INSERT INTO posta (postna_stevilka, kraj, drzava) VALUES (%s, %s, %s) RETURNING id",
                                [postna_stevilka, kraj, drzava])
                (id_posta,) = cur.fetchone()
                print('POSTO SMO DODALI V BAZO. Id poste', id_posta)
                
                #Dodamo lokacijo
                cur.execute("INSERT INTO lokacija (ulica,hisna_stevilka, id_posta) VALUES (%s, %s, %s) RETURNING id",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()
                print('LOKACIJO SMO DODALI V BAZO. Id lokacije', id_lokacija)

    #Ni dovolj podatkov, da bi dodali lokacijo
    else:
        id_lokacija = None
    
    #Vstavimo podatke v dogodek
    print('STEVILO UDELEZENCEV', stevilo_udelezencev)
    cur.execute("""INSERT INTO dogodek (organizator,id_aktivnost,opis,datum, cas, id_lokacija, stevilo_udelezencev) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [uporabnik_prijavljen,aktivnost,opis, datum, cas, id_lokacija, stevilo_udelezencev])
    print(uporabnik_prijavljen,aktivnost,opis,datum,cas,id_lokacija)

    conn.commit()
    

    set_sporocilo("alert-success", "Uspešno si dodal dogodek")
    return bottle.redirect("/")
 


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

    # # Zaradi probavanja!!!
    # cur.execute("SELECT 1 FROM uporabnik WHERE uporabnisko_ime=%s",
    #           [uporabnik])

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
    bottle.response.delete_cookie('uporabnik', path='/')
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

@bottle.get("/uporabnik/<uporabnik>/")
def uporabnik_profil(uporabnik):
    """Prikaži stran uporabnika"""
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    # Ime uporabnika (hkrati preverimo, ali uporabnik sploh obstaja)
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    # Ali prijavljen uporabnik sledi uporabniku iz profila
    cur.execute("SELECT 1 FROM sledilec WHERE sledilec=%s AND zasledovani=%s",[uporabnik_prijavljen,uporabnik])
    ali_sledi = (True if cur.fetchone() else False)
    # Seznam zadnjih 10 tračev
    os = objave(limit=None, uporabnik=uporabnik)
    # Koliko sledilcev ima ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE zasledovani=%s", [uporabnik])
    st_z = cur.fetchone()
    # Koliko sledovanih ima ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE sledilec=%s", [uporabnik])
    st_s = cur.fetchone()
    # Pogledamo, če imamo kakšna sporočila za uporabnika
    sporocilo = get_sporocilo()
    # Prikažemo predlog
    return bottle.template("profil.html",
                           profil_ime=ime,
                           profil_priimek=priimek,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           uporabnik=uporabnik,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           objave=os,
                           ali_sledi=ali_sledi,
                           sporocilo=sporocilo)

@bottle.get("/uporabnik/<uporabnik>/uredi_profil/")
def uredi_profil(uporabnik, sporocila=[]):
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
                           profil_ime=ime_novo,
                           profil_priimek=priimek_novo,
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

@bottle.get('/uporabnik/<uporabnik>/sledilci/')
def pokazi_sledilce(uporabnik):
    """Pokaži stran vseh sledilcev uporabnika"""
    # Kdo je prijavljen?
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    zasledovani_prijavljenega = [z[0] for z in dobi_zasledovane(uporabnik=uporabnik_prijavljen)]
    # Dobim vse sledilce iz baze
    cur.execute("""
    SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE 
    uporabnisko_ime IN 
    (SELECT sledilec FROM sledilec WHERE zasledovani=%s) 
    ORDER BY ime ASC, priimek ASC 
    """, [uporabnik])
    sledilci = cur.fetchall()
    # Koliko sledilcev ima ta uporabnik?
    st_s = len(sledilci)
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    return bottle.template("sledilci.html",
                           uporabnik=uporabnik,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           zasledovani_prijavljenega=zasledovani_prijavljenega,
                           st_s=st_s,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           profil_ime=ime,
                           profil_priimek=priimek,
                           sledilci=sledilci)

@bottle.get('/uporabnik/<uporabnik>/zasledovani/')
def pokazi_zasledovane(uporabnik):
    """Pokaži stran vseh, katerim uporabnik sledi"""
    # Kdo je prijavljen?
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    zasledovani = dobi_zasledovane(uporabnik=uporabnik)
    if uporabnik_prijavljen == uporabnik:
        zasledovani_prijavljenega = [z[0] for z in zasledovani]
    else:
        zas = dobi_zasledovane(uporabnik=uporabnik_prijavljen)
        zasledovani_prijavljenega = [z[0] for z in zas]
    # Koliko ljudi zasleduje ta uporabnik?
    cur.execute("SELECT COUNT(*) FROM sledilec WHERE sledilec=%s", [uporabnik])
    (st_z,) = cur.fetchone()
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    (ime,priimek) = cur.fetchone()
    return bottle.template("zasledovani.html",
                           uporabnik=uporabnik,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           st_z=st_z,
                           profil_ime=ime,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           zasledovani_prijavljenega=zasledovani_prijavljenega,
                           profil_priimek=priimek,
                           zasledovani=zasledovani)

@bottle.post("/uporabnik/<uporabnik>/")
def upravljaj_profil(uporabnik):
    gumb = bottle.request.forms.gumb_sledi
    upravljaj_sledilca(uporabnik,gumb[0] == "S")
    return uporabnik_profil(uporabnik)

@bottle.get("/<uporabnik_profil>/<uporabnisko_ime_zasledovani>/<polozaj>/<sprememba>")
def sporocila(uporabnik_profil, uporabnisko_ime_zasledovani, polozaj, sprememba):
    upravljaj_sledilca(uporabnisko_ime_zasledovani,sprememba=="pricni")
    return bottle.redirect("/uporabnik/{}/{}/".format(uporabnik_profil,polozaj))

@bottle.get("/isci/")
def isci_uporabnike():
    iskanje = bottle.request.query.isci
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    zasledovani_prijavljenega = [z[0] for z in dobi_zasledovane(uporabnik=uporabnik_prijavljen)]
    cur.execute("SELECT uporabnisko_ime, ime, priimek FROM uporabnik")
    vsi_uporabniki = cur.fetchall()
    zadetki = []
    for (up, i, p) in vsi_uporabniki:
        if iskanje.lower() in i.lower() + ' ' + p.lower() or iskanje.lower() in up.lower():
            zadetki.append((up,i,p))
    return bottle.template("isci.html",
                           iskanje=iskanje,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           zadetki=zadetki,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           zasledovani_prijavljenega=zasledovani_prijavljenega)

@bottle.get("/isci/<iskanje>/<uporabnik>/<sprememba>/")
def dodaj_pri_iskanju(iskanje,uporabnik,sprememba):
    upravljaj_sledilca(uporabnik,sprememba=="pricni")
    return bottle.redirect("/isci/?isci={}".format(iskanje))

@bottle.get("/uporabnik/<uporabnik>/sporocila/")
def sporocila_uporabnik(uporabnik):
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    if uporabnik_prijavljen != uporabnik:
        # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljen dostop do sporočil drugih profilov!")
        return bottle.redirect("/")
    cur.execute("""
    SELECT prejemnik, posiljatelj, vsebina, cas
    FROM sporocila WHERE posiljatelj=%s OR prejemnik=%s ORDER BY cas DESC""", [uporabnik_prijavljen,uporabnik_prijavljen])
    (prejemnik, posiljatelj, vsebina, cas) = cur.fetchone()
    return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik_prijavljen,(posiljatelj if prejemnik == uporabnik_prijavljen else prejemnik)))

@bottle.get("/uporabnik/<uporabnik>/sporocila/<sogovornik>/")
def sporocila_uporabnika(uporabnik, sogovornik):
    """Prikaži stran uporabnika"""
    # Morebitno sporočilo za uporabnika
    sporocilo = get_sporocilo()
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    if uporabnik_prijavljen != uporabnik:
        # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljen dostop do sporočil drugih profilov!")
        return bottle.redirect("/")
    # Dobim vsa sporocila
    cur.execute("""
    SELECT prejemnik, posiljatelj, vsebina, cas
    FROM sporocila WHERE posiljatelj=%s OR prejemnik=%s ORDER BY cas DESC""", [uporabnik_prijavljen,uporabnik_prijavljen])
    pogovori = {}
    osebe = []
    for (prejemnik, posiljatelj, vsebina, cas) in cur:
        if prejemnik == uporabnik_prijavljen:
            if posiljatelj not in osebe:
                osebe.append(posiljatelj)
            a = pogovori.get(posiljatelj, [])
            a.append((1,vsebina,pretty_date(cas)))
            pogovori[posiljatelj] = a
        else:
            if prejemnik not in osebe:
                osebe.append(prejemnik)
            b = pogovori.get(prejemnik, [])
            b.append((0,vsebina,pretty_date(cas)))
            pogovori[prejemnik] = b
    return bottle.template("sporocila.html",
                           profil_ime=ime_prijavljen,
                           profil_priimek=priimek_prijavljen,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           uporabnik=uporabnik,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           pogovori=pogovori,
                           osebe=osebe,
                           odprt_pogovor=sogovornik,
                           sporocilo=sporocilo)

@bottle.post("/uporabnik/<uporabnik>/sporocila/<sogovornik>/")
def poslji_sporocilo(uporabnik, sogovornik):
    """Uporabnik posilja sporocilo sogovorniku"""
    vsebina = bottle.request.forms.novo_sporocilo
    if vsebina:
        cur.execute("INSERT INTO sporocila(posiljatelj, prejemnik, vsebina) VALUES (%s,%s,%s)",[uporabnik, sogovornik, vsebina])
        conn.commit()
    return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik, sogovornik))

@bottle.post("/uporabnik/<uporabnik>/sporocila/<uporabnik_aktiven>/isci/")
def poslji_sporocilo(uporabnik,uporabnik_aktiven):
    isci = bottle.request.forms.isci_uporabnika
    if isci:
        cur.execute("SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE uporabnisko_ime <> %s",[uporabnik])
        vsi = cur.fetchall()
        zacasen = None
        for (ui, i, p) in vsi:
            if ui.lower() == isci.lower():
                return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik,ui))
            elif isci.lower() == i.lower() + ' ' + p.lower() and zacasen:
                # uporabnikov s tem imenom in priimkom je več
                set_sporocilo("alert-danger", "Zaznanih je bilo več uporabnikov s tem imenom in priimkom. Prosimo da vnesete uporabniško ime.")
                return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))
            elif isci.lower() == i.lower() + ' ' + p.lower():
                zacasen = ui
        if zacasen:
            return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik, zacasen))
        else:
            set_sporocilo("alert-danger", """
            V bazi ni nobenega uporabnika, katerega uporabniski ime oziroma polno ime in priimek bi se ujemalo z \"{}\".
            """.format(isci))
            return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))
    set_sporocilo("alert-danger", "V iskalno polje vnesite uporabnisko ime ali poln ime in priimek")
    return bottle.redirect("/uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))

@bottle.post("/uporabnik/<uporabnik>/objavi")
def nova_objava(uporabnik):
    vsebina = bottle.request.forms.objava
    if vsebina:
        cur.execute("INSERT INTO objava(avtor,vsebina) VALUES (%s, %s)",[uporabnik, vsebina])
        conn.commit()
        set_sporocilo("alert-success", "Uspešno ste delili objavo!")
    else:
        set_sporocilo("alert-danger", "Hoteli ste objaviti prazno sporočilo. Zakaj?! ಠ_ಠ")
    return bottle.redirect("/uporabnik/{}/".format(uporabnik))

@bottle.post("/uporabnik/<uporabnik>/komentiraj/<oid>/")
def komentiraj_na_zidu(uporabnik,oid):
    """ Komentiraj objavo na zidu danega uporabnika """
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    komentar = bottle.request.forms.komentar
    if komentar:
        cur.execute("INSERT INTO komentar(avtor,id_objava,vsebina) VALUES (%s, %s, %s)", [uporabnik_prijavljen, oid, komentar])
        conn.commit()
    return bottle.redirect("/uporabnik/{}/#objava-{}".format(uporabnik, oid))
    
@bottle.get("/uporabnik/<uporabnik>/komentar/<oid>/<kid>/brisi/")
def brisi_komentar_na_zidu(uporabnik, oid, kid):
    """ Briši komentar na uporabnikovem zidu pri objavi """
    cur.execute("DELETE FROM komentar WHERE id=%s",[kid])
    set_sporocilo("alert-success", "Uspešno ste zbrisali komentar!")
    conn.commit()
    return bottle.redirect("/uporabnik/{}/#objava-{}".format(uporabnik, oid))

@bottle.get("/uporabnik/<uporabnik>/objava/<oid>/brisi/")
def brisi_komentar_na_zidu(uporabnik, oid):
    """ Briši komentar na uporabnikovem zidu pri objavi """
    cur.execute("""DELETE FROM komentar 
    WHERE id_objava IN (SELECT id from objava WHERE id=%s)""",[oid])
    cur.execute("DELETE FROM objava WHERE id=%s",[oid])
    set_sporocilo("alert-success", "Uspešno ste zbrisali objavo!")
    conn.commit()
    return bottle.redirect("/uporabnik/{}/".format(uporabnik, oid))
######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password, port=DB_PORT)
#conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# poženemo strežnik na podanih vratih, npr. http://localhost:8080/
bottle.run(host='localhost', port=SERVER_PORT, reloader=RELOADER)
