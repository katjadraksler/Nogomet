#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
from bottle import get, post, run, request, template, redirect, static_file

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

# odkomentiraj, če želiš sporočila o napakah
# debug(True)

def rtemplate(*largs, **kwargs):
    """
    Izpis predloge s podajanjem spremenljivke ROOT z osnovnim URL-jem.
    """
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

######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password, port=DB_PORT)
#conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# poženemo strežnik na podanih vratih, npr. http://localhost:8080/
# reloader=RELOADER
run(host='localhost', port=SERVER_PORT)