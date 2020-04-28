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
<<<<<<< HEAD
=======
    return template(ROOT=ROOT, *largs, **kwargs)

# @get('/static/<filename:path>')
# def static(filename):
#     return static_file(filename, root='static')

@get('/')
def index():
    cur.execute("""
    SELECT uporabnik.id AS id, ime,priimek,uporabnisko_ime,spol,datum_rojstva,ulica, hisna_stevilka, kraj
    FROM uporabnik JOIN lokacija ON id_lokacija = lokacija.id
    """)
    print(cur)
    return rtemplate('uporabniki.html', uporabnik=cur)

# @get('/transakcije/<x:int>/')
# def transakcije(x):
#     cur.execute("SELECT * FROM transakcija WHERE znesek > %s ORDER BY znesek, id", [x])
#     return rtemplate('transakcije.html', x=x, transakcije=cur)

# @get('/dodaj_transakcijo')
# def dodaj_transakcijo():
#     return rtemplate('dodaj_transakcijo.html', znesek='', racun='', opis='', napaka=None)

# @post('/dodaj_transakcijo')
# def dodaj_transakcijo_post():
#     znesek = request.forms.znesek
#     racun = request.forms.racun
#     opis = request.forms.opis
#     try:
#         cur.execute("INSERT INTO transakcija (znesek, racun, opis) VALUES (%s, %s, %s)",
#                     (znesek, racun, opis))
#         cur.execute("INSERT INTO transakcija (znesek, racun, opis) VALUES (%s, 100027, %s)",
#                     (int(znesek) * 0.1, "Provizija za " + opis))
#         conn.commit()
#     except Exception as ex:
#         conn.rollback()
#         return rtemplate('dodaj_transakcijo.html', znesek=znesek, racun=racun, opis=opis,
#                         napaka='Zgodila se je napaka: %s' % ex)
#     redirect(ROOT)
>>>>>>> 5000b66b233d2683a33f4abbd1ef898cabfb1b17

    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
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
    (uporabnik, ime, priimek) = get_user()
    # Morebitno sporočilo za uporabnika
    sporocilo = get_sporocilo()
    # Vrnemo predlogo za glavno stran
    return bottle.template("glavna.html",
                           ime=ime,
                           priimek=priimek,
                           uporabnik=uporabnik,
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
                           username=None,
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
######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password, port=DB_PORT)
#conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# poženemo strežnik na podanih vratih, npr. http://localhost:8080/
<<<<<<< HEAD
bottle.run(host='localhost', port=SERVER_PORT, reloader=RELOADER)
=======
# reloader=RELOADER
run(host='localhost', port=SERVER_PORT)
>>>>>>> 5000b66b233d2683a33f4abbd1ef898cabfb1b17
