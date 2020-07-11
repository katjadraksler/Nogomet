#!/usr/bin/python
# -*- encoding: utf-8 -*-

# uvozimo bottle.py
import bottle
import hashlib # računanje MD5 kriptografski hash za gesla
from datetime import datetime, date

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

# bottle.debug(True)

# Mapa s statičnimi datotekami
static_dir = "./static"

# Skrivnost za kodiranje cookijev
secret = "to skrivnost je zelo tezko uganiti 1094107c907cw982982c42"

######################################################################
# Pomožne funkcije

def rtemplate(*largs, **kwargs):
    """
    Izpis predloge s podajanjem spremenljivke ROOT z osnovnim URL-jem.
    """
    return bottle.template(ROOT=ROOT, *largs, **kwargs)

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
        bottle.redirect(ROOT + 'prijava/')
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

def dobi_dogodke( uporabnik=None):
    cur.execute("""SELECT * FROM pregledni_dogodki 
                    WHERE aktivnost_id IN
                    (SELECT aktivnost.id FROM
                    tip_aktivnosti JOIN (aktivnost JOIN se_ukvarja ON aktivnost.id = se_ukvarja.id_aktivnost)
                    ON tip_aktivnosti.id = aktivnost.tip
                    WHERE se_ukvarja.uporabnisko_ime = %s) 
                    AND NOT pregledni_dogodki.organizator = %s 
                    AND pregledni_dogodki.datum > NOW()
                    ORDER BY datum 
                    LIMIT 10
                    """, [uporabnik, uporabnik])

    dogodki = tuple(cur)
    ids = (dogodek[0] for dogodek in dogodki)
    cur.execute("""SELECT id,  udelezba.udelezenec FROM
            (udelezba JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id)
            WHERE id IN
            (SELECT id FROM pregledni_dogodki 
                            WHERE aktivnost_id IN
                            (SELECT aktivnost.id FROM
                            tip_aktivnosti JOIN (aktivnost JOIN se_ukvarja ON aktivnost.id = se_ukvarja.id_aktivnost)
                            ON tip_aktivnosti.id = aktivnost.tip
                            WHERE se_ukvarja.uporabnisko_ime = %s) 
                            AND NOT pregledni_dogodki.organizator = %s 
                            AND pregledni_dogodki.datum > NOW()
                            ORDER BY datum
                            LIMIT 10) """, 
                            [uporabnik, uporabnik])

    udelezenec = {id : [] for id in ids }

    for (id, udel) in cur:
        udelezenec[id].append((udel))

    return ((id,b,c,d,e,f,g,h,i,j,k,l,m,n,o,(udelezenec[id]))
            for (id,b,c,d,e,f,g,h,i,j,k,l,m,n,o) in dogodki)

def dogodki_organizira (uporabnik = None):
    cur.execute("""SELECT * FROM pregledni_dogodki 
                    WHERE pregledni_dogodki.datum > NOW()
                    AND pregledni_dogodki.organizator = %s
                    ORDER BY datum 
                    LIMIT 10""", [uporabnik])

    dogodki = tuple(cur)
    ids = (dogodek[0] for dogodek in dogodki)
    cur.execute("""SELECT id, udelezba.udelezenec FROM
            (udelezba JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id)
            WHERE id IN
                (SELECT id FROM pregledni_dogodki
                WHERE pregledni_dogodki.datum > NOW()
                AND pregledni_dogodki.organizator = %s
                ORDER BY datum 
                LIMIT 10)""", [uporabnik])

    udelezenec = {id : [] for id in ids }

    for (id, udel) in cur:
        udelezenec[id].append((udel))

    return ((id,b,c,d,e,f,g,h,i,j,k,l,m,n,o,(udelezenec[id]))
            for (id,b,c,d,e,f,g,h,i,j,k,l,m,n,o) in dogodki)

def dogodki_udelezi (uporabnik = None):
    cur.execute("""SELECT id,aktivnost_id, ime_aktivnosti, tip_aktivnosti, organizator,
                    ime_organizator, priimek_organizator, stevilo_udelezencev, datum, cas, 
                    hisna_stevilka, ulica, postna_stevilka, kraj, opis 
                    FROM 
                    (udelezba LEFT JOIN uporabnik ON udelezba.udelezenec = uporabnik.uporabnisko_ime)
                    RIGHT JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id
                    WHERE pregledni_dogodki.datum > NOW()
                    AND uporabnik.uporabnisko_ime = %s
                    ORDER BY datum 
                    LIMIT 10""", [uporabnik])

    dogodki = tuple(cur)
    nepodvojeni_dogodki = []
    ids = []
    for dogodek in dogodki:
        if dogodek[0] not in ids:
            ids.append(dogodek[0])
            nepodvojeni_dogodki.append(dogodek)
    nepodvojeni_dogodki = tuple(nepodvojeni_dogodki)

    cur.execute("""SELECT id, udelezba.udelezenec FROM
            (udelezba JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id)
            WHERE id IN
                (SELECT id FROM 
                    (udelezba LEFT JOIN uporabnik ON udelezba.udelezenec = uporabnik.uporabnisko_ime)
                    RIGHT JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id
                    WHERE pregledni_dogodki.datum > NOW()
                    AND uporabnik.uporabnisko_ime = %s
                    ORDER BY datum 
                    LIMIT 10)""", [uporabnik])

    udelezenec = {id : [] for id in ids }

    for (id, udel) in cur:
        udelezenec[id].append((udel))

    return ((id,b,c,d,e,f,g,h,i,j,k,l,m,n,o,(udelezenec[id]))
            for (id,b,c,d,e,f,g,h,i,j,k,l,m,n,o) in nepodvojeni_dogodki)

def dobi_dogodke_parametri (aktivnost, tip, datum_od, datum_do, ulica, kraj, organizator,
                    ime_organizator, priimek_organizator, udelezenec, ime_udelezenec, priimek_udelezenec, 
                    aktivnost_BOOL = True, tip_BOOL = True, datum_od_BOOL = True, datum_do_BOOL = True,
                    ulica_BOOL = True, kraj_BOOL = True, organizator_BOOL = True, ime_organizator_BOOL = True, 
                    priimek_organizator_BOOL = True, udelezenec_BOOL = True, ime_udelezenec_BOOL = True, 
                    priimek_udelezenec_BOOL = True):

    if aktivnost:
        aktivnost_BOOL = False
    if tip:
        tip_BOOL = False
    if datum_od:
        datum_od_BOOL = False
    else:
        datum_od = None
    if datum_do:
        datum_do_BOOL = False
    else:
        datum_do = None
    if ulica:
        ulica_BOOL = False
    if kraj:
        kraj_BOOL = False
    if organizator:
        organizator_BOOL = False
    if ime_organizator:
        ime_organizator_BOOL = False
    if priimek_organizator:
        priimek_organizator_BOOL = False
    if udelezenec:
        udelezenec_BOOL = False
    if ime_udelezenec:
        ime_udelezenec_BOOL = False
    if priimek_udelezenec:
        priimek_udelezenec_BOOL = False

    cur.execute("""
        SELECT id,aktivnost_id, ime_aktivnosti, tip_aktivnosti, organizator,
                ime_organizator, priimek_organizator, stevilo_udelezencev, datum, cas, 
                    hisna_stevilka, ulica, postna_stevilka, kraj, opis 
                FROM
                (udelezba LEFT JOIN uporabnik ON udelezba.udelezenec = uporabnik.uporabnisko_ime)
                RIGHT JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id
                WHERE (ime_aktivnosti = %s OR %s)
                AND (tip_aktivnosti = %s OR %s)
                AND (datum > %s OR %s)
                AND (datum < %s OR %s)
                AND (ulica = %s OR %s)
                AND (kraj = %s OR %s)
                AND (organizator = %s OR %s)
                AND (ime_organizator = %s OR %s)
                AND (priimek_organizator = %s OR %s)
                AND (uporabnik.uporabnisko_ime = %s OR %s)
                AND (uporabnik.ime = %s OR %s)
                AND (uporabnik.priimek = %s OR %s)
                ORDER BY datum 
                """,
                [aktivnost, aktivnost_BOOL, tip, tip_BOOL, datum_od, datum_od_BOOL, datum_do, 
                datum_do_BOOL, ulica, ulica_BOOL, kraj, kraj_BOOL, organizator, organizator_BOOL, 
                ime_organizator, ime_organizator_BOOL, priimek_organizator, priimek_organizator_BOOL,
                udelezenec, udelezenec_BOOL, ime_udelezenec, ime_udelezenec_BOOL,
                priimek_udelezenec, priimek_udelezenec_BOOL])
                
    dogodki = tuple(cur)
    nepodvojeni_dogodki = []
    ids = []
    for dogodek in dogodki:
        if dogodek[0] not in ids:
            ids.append(dogodek[0])
            nepodvojeni_dogodki.append(dogodek)
    nepodvojeni_dogodki = tuple(nepodvojeni_dogodki)

    cur.execute("""SELECT pregledni_dogodki.id, udelezba.udelezenec FROM
            ((udelezba JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id)
            LEFT JOIN uporabnik ON udelezba.udelezenec = uporabnik.uporabnisko_ime)
            WHERE pregledni_dogodki.id IN
                (SELECT id FROM
                    (udelezba LEFT JOIN uporabnik ON udelezba.udelezenec = uporabnik.uporabnisko_ime)
                    RIGHT JOIN pregledni_dogodki ON udelezba.id_dogodek = pregledni_dogodki.id
                    WHERE (ime_aktivnosti = %s OR %s)
                    AND (tip_aktivnosti = %s OR %s)
                    AND (datum > %s OR %s)
                    AND (datum < %s OR %s)
                    AND (ulica = %s OR %s)
                    AND (kraj = %s OR %s)
                    AND (organizator = %s OR %s)
                    AND (ime_organizator = %s OR %s)
                    AND (priimek_organizator = %s OR %s)
                    AND (uporabnik.uporabnisko_ime = %s OR %s)
                    AND (uporabnik.ime = %s OR %s)
                    AND (uporabnik.priimek = %s OR %s)
                    ORDER BY datum)

                    
                """, 
                    [aktivnost, aktivnost_BOOL, tip, tip_BOOL, datum_od, datum_od_BOOL, datum_do, 
                    datum_do_BOOL, ulica, ulica_BOOL, kraj, kraj_BOOL, organizator, organizator_BOOL, 
                    ime_organizator, ime_organizator_BOOL, priimek_organizator, priimek_organizator_BOOL,
                    udelezenec, udelezenec_BOOL, ime_udelezenec, ime_udelezenec_BOOL,
                    priimek_udelezenec, priimek_udelezenec_BOOL])

    udelezenec = {id : [] for id in ids }

    for (id, udel) in cur:
        udelezenec[id].append((udel))

    return ((id,b,c,d,e,f,g,h,i,j,k,l,m,n,o,(udelezenec[id]))
            for (id,b,c,d,e,f,g,h,i,j,k,l,m,n,o) in nepodvojeni_dogodki)

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

def dobi_aktivnosti(uporabnik):
    """Iz baze dobim vse aktivnosti, ki zanimajo uporabnika, zapisane v slovar razporejen po tipu aktivnosti"""
    cur.execute("""
    SELECT aktivnost.ime, tip_aktivnosti.tip FROM se_ukvarja
    LEFT JOIN aktivnost ON aktivnost.id = se_ukvarja.id_aktivnost
    LEFT JOIN tip_aktivnosti ON aktivnost.tip = tip_aktivnosti.id
    WHERE se_ukvarja.uporabnisko_ime=%s
    """,[uporabnik])
    k = {}
    for akt, tip in cur.fetchall():
        a = k.get(tip,set())
        a.add(akt)
        k[tip] = a
    return k

def dobi_ime(uporabnik):
    cur.execute("SELECT ime, priimek FROM uporabnik WHERE uporabnisko_ime=%s", [uporabnik])
    try:
        return cur.fetchone()
    except:
        return

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
    dogodki = dobi_dogodke(uporabnik = str(uporabnik_prijavljen))

    return rtemplate("glavna.html",
                            stran = 'glavna',
                            traci=ts,
                            dogodki = dogodki,
                            ime=ime,
                            priimek=priimek,
                            uporabnik_prijavljen=uporabnik_prijavljen,
                            uporabnik = uporabnik_prijavljen,
                            sporocilo=sporocilo)

@bottle.get("/uporabnik/<uporabnik>/dodaj_dogodek/")
def nov_dogodek(uporabnik):
    """Glavna stran."""
    # Iz cookieja dobimo uporabnika (ali ga preusmerimo na login, če
    # nima cookija)

    (uporabnik_prijavljen, ime, priimek) = get_user()
    sporocilo = get_sporocilo()

    if uporabnik_prijavljen != uporabnik:
    # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljena objava dogodka z drugim uporabniskim imenom!")
        return bottle.redirect(ROOT)
    
    cur.execute("SELECT aktivnost.ime FROM aktivnost ORDER BY aktivnost.ime")

    return rtemplate("dodaj_dogodek.html",
                           ime=ime,
                           priimek=priimek,
                           aktivnosti = cur,
                           uporabnik = uporabnik_prijavljen,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           sporocilo = sporocilo)

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
        return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))
    
    #DATUM
    if not datum:
        set_sporocilo("alert-danger", "Datum je obvezen argument")
        return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))
    today = date.today()
    today = today.strftime("%Y-%m-%d")
    time = datetime.now().time()
    time = time.strftime('%H:%M:%S')
    if today > datum:
        set_sporocilo("alert-danger", "Datum ne ustreza.")
        return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))
    elif today == datum and cas < time:
        set_sporocilo("alert-danger", "Datum ne ustreza.")
        return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))

    #AKTIVNOST - Zamenjemo aktivnost_ime z aktivnost_id
    if not aktivnost:
        set_sporocilo("alert-danger", "Aktivnost je obvezen argument")
        return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))
    else:
        cur.execute("SELECT aktivnost.id FROM aktivnost WHERE aktivnost.ime = %s",
                            [aktivnost])          
        (aktivnost,) = cur.fetchone()

    #LOKACIJA
    #Potrebni podatki, da sploh imamo lokacijo
    if ulica and postna_stevilka and  kraj and drzava and hisna_stevilka:
        # Najprej poiščemo pošto v bazi
        cur.execute("SELECT posta.id FROM posta WHERE postna_stevilka = %s AND kraj = %s AND drzava = %s",
                                [postna_stevilka, kraj, drzava])
        #Pošta je v bazi
        if cur.fetchone():
            cur.execute("SELECT posta.id FROM posta WHERE postna_stevilka = %s AND kraj = %s AND drzava = %s",
                                [postna_stevilka, kraj, drzava])
            (id_posta,) = cur.fetchone()

            #Poiščemo lokacijo
            cur.execute("""SELECT lokacija.id FROM lokacija WHERE ulica = %s AND (hisna_stevilka = %s OR hisna_stevilka = NULL)
                            AND id_posta = %s""",
                                [ulica, hisna_stevilka, id_posta])
            
            #Lokcaija je v bazi
            if cur.fetchone():
                cur.execute("""SELECT lokacija.id FROM lokacija WHERE ulica = %s AND hisna_stevilka = %s 
                                AND id_posta = %s""",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()

            #Lokacije ni v bazi. Jo dodamo
            else:
                cur.execute("INSERT INTO lokacija (ulica,hisna_stevilka, id_posta) VALUES (%s, %s, %s) RETURNING id",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()

        #Pošte ni v bazi => Lokacije ni v bazi. Ju dodamo
        else:
            #Pogledamo ali pošto sploh lahko dodamo v bazo
            cur.execute("SELECT 1 FROM posta WHERE postna_stevilka = %s AND drzava = %s",
                      [postna_stevilka,drzava])

            #Poste ne moremo dodati ((stevilka,drzava) je UNIQUE)
            if cur.fetchone():
                set_sporocilo("alert-danger", "Ta pošta ne obstaja")
                return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))
            #Posto lahko dodamo
            else:
                cur.execute("INSERT INTO posta (postna_stevilka, kraj, drzava) VALUES (%s, %s, %s) RETURNING id",
                                [postna_stevilka, kraj, drzava])
                (id_posta,) = cur.fetchone()
                
                #Dodamo lokacijo
                cur.execute("INSERT INTO lokacija (ulica,hisna_stevilka, id_posta) VALUES (%s, %s, %s) RETURNING id",
                                [ulica, hisna_stevilka, id_posta])
                (id_lokacija,) = cur.fetchone()

    #Ni dovolj podatkov, da bi dodali lokacijo
    else:
        id_lokacija = None

    if not stevilo_udelezencev:
        stevilo_udelezencev = None
    
    #Vstavimo podatke v dogodek
    cur.execute("""INSERT INTO dogodek (organizator,id_aktivnost,opis,datum, cas, id_lokacija, stevilo_udelezencev) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [uporabnik_prijavljen,aktivnost,opis, datum, cas, id_lokacija, stevilo_udelezencev])

    conn.commit()
    
    set_sporocilo("alert-success", "Uspešno si dodal dogodek")
    return bottle.redirect(ROOT + "uporabnik/{}/dodaj_dogodek/".format(uporabnik))

@bottle.get("/uporabnik/<uporabnik>/poisci_dogodke/")
def poisci_dogodek(uporabnik):
    """Glavna stran."""
    # Iz cookieja dobimo uporabnika (ali ga preusmerimo na login, če
    # nima cookija)

    (uporabnik_prijavljen, ime, priimek) = get_user()
    sporocilo = get_sporocilo()

    if uporabnik_prijavljen != uporabnik:
    # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljena objava dogodka z drugim uporabniskim imenom!")
        return bottle.redirect(ROOT)
    
    cur.execute("SELECT aktivnost.ime FROM aktivnost ORDER BY aktivnost.ime")
    aktivnosti = cur.fetchall()
    cur.execute("SELECT tip_aktivnosti.tip FROM tip_aktivnosti ORDER BY tip_aktivnosti.tip")
    tipi = cur.fetchall()

    return rtemplate("poisci-dogodke.html",
                           stran = 'poisci',
                           ime=ime,
                           priimek=priimek,
                           aktivnosti = aktivnosti,
                           tipi = tipi,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           uporabnik = uporabnik_prijavljen,
                           dogodki=[],
                           sporocilo=sporocilo)

@bottle.post("/uporabnik/<uporabnik>/poisci_dogodke/")
def vrni_dogodke(uporabnik):

    (uporabnik_prijavljen, ime, priimek) = get_user()
    sporocilo = get_sporocilo()

    aktivnost = bottle.request.forms.aktivnost
    tip = bottle.request.forms.tip
    datum_od = bottle.request.forms.datum_od
    datum_do = bottle.request.forms.datum_do
    ulica = bottle.request.forms.ulica
    kraj = bottle.request.forms.kraj
    organizator = bottle.request.forms.organizator
    ime_organizator = bottle.request.forms.ime_organizator
    priimek_organizator = bottle.request.forms.priimek_organizator
    udelezenec = bottle.request.forms.udelezenec
    ime_udelezenec = bottle.request.forms.ime_udelezenec
    priimek_udelezenec = bottle.request.forms.priimek_udelezenec

    dogodki = dobi_dogodke_parametri (aktivnost, tip, datum_od, datum_do, ulica, kraj, organizator,
                    ime_organizator, priimek_organizator, udelezenec, ime_udelezenec, priimek_udelezenec)

    cur.execute("SELECT aktivnost.ime FROM aktivnost ORDER BY aktivnost.ime")
    aktivnosti = cur.fetchall()
    cur.execute("SELECT tip_aktivnosti.tip FROM tip_aktivnosti ORDER BY tip_aktivnosti.tip")
    tipi = cur.fetchall()

    return rtemplate("poisci-dogodke.html",
                           stran = 'poisci',
                           ime=ime,
                           priimek=priimek,
                           aktivnosti = aktivnosti,
                           tipi = tipi,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           uporabnik=uporabnik_prijavljen,
                           dogodki = dogodki,
                           sporocilo=sporocilo)

@bottle.get("/uporabnik/<uporabnik>/<dogodek>/pridruzi_se/<stran>/")
def pridruzi_se(uporabnik, dogodek, stran):

    """Preverimo koliko je že udeležencev v dogodku"""
    cur.execute(""" SELECT COUNT(udelezenec) FROM udelezba WHERE id_dogodek = %s""",[dogodek])
    (trenutno_st_udelezencev,) = cur.fetchone()
    """Koliko udeležencev ima lahko dogodek največ"""
    cur.execute("""SELECT (stevilo_udelezencev) FROM dogodek WHERE id = %s""", [dogodek])
    (max_st_udelezencev,) = cur.fetchone()

    if max_st_udelezencev == None:
        max_st_udelezencev = 0
    if trenutno_st_udelezencev == None:
        trenutno_st_udelezencev = 0

    st_prostih_mest = max_st_udelezencev - trenutno_st_udelezencev

    """Ali je uporabnik že udeležen v tem dogodku"""
    cur.execute(""" SELECT (udelezenec, id_dogodek) FROM udelezba
    WHERE id_dogodek = %s AND udelezenec = %s """, [dogodek, uporabnik])
    c=cur.fetchall()
    
    if c != []:
        set_sporocilo("alert-danger", "Temu dogodku ste že pridruženi!")
        if stran == 'glavna':
            return bottle.redirect(ROOT)
        elif stran == 'poisci':
            return bottle.redirect(ROOT + "uporabnik/{}/poisci_dogodke/".format(uporabnik))
        else:
            return bottle.redirect(ROOT + "uporabnik/{}/moji_dogodki/".format(uporabnik))

    if st_prostih_mest <= 0:
        set_sporocilo("alert-danger", "Vsa mesta so že zasedena!")
        if stran == 'glavna':
            return bottle.redirect(ROOT)
        elif stran == 'poisci':
            return bottle.redirect(ROOT + "uporabnik/{}/poisci_dogodke/".format(uporabnik))
        else:
            return bottle.redirect(ROOT + "uporabnik/{}/moji_dogodki/".format(uporabnik))
    cur.execute("""
        INSERT INTO udelezba (udelezenec, id_dogodek) VALUES (%s, %s)
            """, [uporabnik, dogodek])
    set_sporocilo("alert-success", "Uspešno ste se pridružili dogodku!")
    conn.commit()

    if stran == 'glavna':
        return bottle.redirect(ROOT)
    elif stran == 'poisci':
            return bottle.redirect(ROOT)
    else:
        return bottle.redirect(ROOT + "uporabnik/{}/moji_dogodki/".format(uporabnik))


@bottle.get("/uporabnik/<uporabnik>/<dogodek>/odstrani_dogodek/<stran>/")
def odstrani_dogodek(uporabnik, dogodek,stran):

    (uporabnik_prijavljen, ime, priimek) = get_user()

    if uporabnik != uporabnik_prijavljen:
        set_sporocilo("alert-danger", "Ne morete brisati dogodkov, ki jih ne organizirate!")

    """Najprej moramo zbrisati vse udelezence, saj se navezujejo na dogodek"""
    cur.execute("""DELETE FROM udelezba WHERE udelezba.id_dogodek = %s""",[dogodek])

    """Izbrišemo dogodek"""
    cur.execute("""DELETE FROM dogodek WHERE dogodek.id = %s""",[dogodek])

    set_sporocilo("alert-success", "Uspešno ste odstranili dogodek!")
    conn.commit()
    if stran == 'glavna':
        return bottle.redirect(ROOT)
    elif stran == 'poisci':
        return bottle.redirect(ROOT)
    else:
        return bottle.redirect(ROOT + "uporabnik/{}/moji_dogodki/".format(uporabnik))

@bottle.get("/uporabnik/<uporabnik>/<dogodek>/zapusti_dogodek/<stran>/")
def zapusti_dogodek(uporabnik, dogodek, stran):

    (uporabnik_prijavljen, ime, priimek) = get_user()

    """Zapustimo dogodek"""
    cur.execute("""DELETE FROM udelezba WHERE udelezba.udelezenec = %s AND udelezba.id_dogodek = %s""",[uporabnik,dogodek])
    set_sporocilo("alert-success", "Uspešno ste zapustili dogodek!")
    conn.commit()

    if stran == 'glavna':
        return bottle.redirect(ROOT)
    elif stran == 'poisci':
        return bottle.redirect(ROOT)
    else:
        return bottle.redirect(ROOT + "uporabnik/{}/moji_dogodki/".format(uporabnik))

@bottle.get("/prijava/")
def login_get():
    """Serviraj formo za prijavo."""
    return rtemplate("prijava.html",
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
        return rtemplate("prijava.html",
                               napaka="Nepravilna prijava",
                               uporabnik=uporabnik)
    else:
        # Vse je v redu, nastavimo cookie in preusmerimo na glavno stran
        bottle.response.set_cookie('uporabnik', uporabnik, path='/', secret=secret)
        bottle.redirect(ROOT)

@bottle.get("/odjava/")
def logout():
    """Pobriši cookie in preusmeri na login."""
    bottle.response.delete_cookie('uporabnik', path='/')
    bottle.redirect(ROOT + 'prijava/')

@bottle.get("/registracija/")
def login_get():
    """Prikaži formo za registracijo."""
    return rtemplate("registracija.html", 
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
        return rtemplate("registracija.html",
                               uporabnik=uporabnik,
                               ime=ime,
                               priimek=priimek,
                               napaka='To uporabniško ime je že zavzeto')
    elif not geslo1 == geslo2:
        # Geslo se ne ujemata
        return rtemplate("registracija.html",
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
        bottle.redirect(ROOT)

@bottle.get("/uporabnik/<uporabnik>/")
def uporabnik_profil(uporabnik):
    """Prikaži stran uporabnika"""
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    # Ime uporabnika (hkrati preverimo, ali uporabnik sploh obstaja)
    (ime,priimek) = dobi_ime(uporabnik)
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
    return rtemplate("profil.html",
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
        return bottle.redirect(ROOT)
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
    return rtemplate("uredi-profil.html",
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
    return rtemplate("uredi-profil.html",
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
    (ime,priimek) = dobi_ime(uporabnik)
    return rtemplate("sledilci.html",
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
    (ime,priimek) = dobi_ime(uporabnik)
    return rtemplate("zasledovani.html",
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
    return bottle.redirect(ROOT + "uporabnik/{}/{}/".format(uporabnik_profil,polozaj))

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
    return rtemplate("isci.html",
                           iskanje=iskanje,
                           ime=ime_prijavljen,
                           priimek=priimek_prijavljen,
                           zadetki=zadetki,
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           zasledovani_prijavljenega=zasledovani_prijavljenega)

@bottle.get("/isci/<iskanje>/<uporabnik>/<sprememba>/")
def dodaj_pri_iskanju(iskanje,uporabnik,sprememba):
    upravljaj_sledilca(uporabnik,sprememba=="pricni")
    return bottle.redirect(ROOT + "isci/?isci={}".format(iskanje))

@bottle.get("/uporabnik/<uporabnik>/sporocila/")
def sporocila_uporabnik(uporabnik):
    # Kdo je prijavljeni uporabnik? (Ni nujno isti kot username.)
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    if uporabnik_prijavljen != uporabnik:
        # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Nedovoljen dostop do sporočil drugih profilov!")
        return bottle.redirect(ROOT)
    cur.execute("""
    SELECT prejemnik, posiljatelj, vsebina, cas
    FROM sporocila WHERE posiljatelj=%s OR prejemnik=%s ORDER BY cas DESC""", [uporabnik_prijavljen,uporabnik_prijavljen])
    try:
        (prejemnik, posiljatelj, vsebina, cas) = cur.fetchone()
    except:
        (prejemnik, posiljatelj, vsebina, cas) = (None, None, None, None)
    return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/".format(uporabnik_prijavljen,(posiljatelj if prejemnik == uporabnik_prijavljen else prejemnik)))

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
        return bottle.redirect(ROOT)
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
    return rtemplate("sporocila.html",
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
    return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/#text-polje".format(uporabnik, sogovornik))

@bottle.post("/uporabnik/<uporabnik>/sporocila/<uporabnik_aktiven>/isci/")
def poslji_sporocilo(uporabnik,uporabnik_aktiven):
    isci = bottle.request.forms.isci_uporabnika
    if isci:
        cur.execute("SELECT uporabnisko_ime, ime, priimek FROM uporabnik WHERE uporabnisko_ime <> %s",[uporabnik])
        vsi = cur.fetchall()
        zacasen = None
        for (ui, i, p) in vsi:
            if ui.lower() == isci.lower():
                return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/#text-polje".format(uporabnik,ui))
            elif isci.lower() == i.lower() + ' ' + p.lower() and zacasen:
                # uporabnikov s tem imenom in priimkom je več
                set_sporocilo("alert-danger", "Zaznanih je bilo več uporabnikov s tem imenom in priimkom. Prosimo da vnesete uporabniško ime.")
                return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))
            elif isci.lower() == i.lower() + ' ' + p.lower():
                zacasen = ui
        if zacasen:
            return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/#text-polje".format(uporabnik, zacasen))
        else:
            set_sporocilo("alert-danger", """
            V bazi ni nobenega uporabnika, katerega uporabniski ime oziroma polno ime in priimek bi se ujemalo z \"{}\".
            """.format(isci))
            return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))
    set_sporocilo("alert-danger", "V iskalno polje vnesite uporabnisko ime ali poln ime in priimek")
    return bottle.redirect(ROOT + "uporabnik/{}/sporocila/{}/".format(uporabnik, uporabnik_aktiven))

@bottle.post("/uporabnik/<uporabnik>/objavi")
def nova_objava(uporabnik):
    vsebina = bottle.request.forms.objava
    if vsebina:
        cur.execute("INSERT INTO objava(avtor,vsebina) VALUES (%s, %s)",[uporabnik, vsebina])
        conn.commit()
        set_sporocilo("alert-success", "Uspešno ste delili objavo!")
    else:
        set_sporocilo("alert-danger", "Hoteli ste objaviti prazno sporočilo. Zakaj?! ಠ_ಠ")
    return bottle.redirect(ROOT + "uporabnik/{}/".format(uporabnik))

@bottle.post("/uporabnik/<uporabnik>/komentiraj/<oid>/")
def komentiraj_na_zidu(uporabnik,oid):
    """ Komentiraj objavo na zidu danega uporabnika """
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    komentar = bottle.request.forms.komentar
    if komentar:
        cur.execute("INSERT INTO komentar(avtor,id_objava,vsebina) VALUES (%s, %s, %s)", [uporabnik_prijavljen, oid, komentar])
        conn.commit()
    return bottle.redirect(ROOT + "uporabnik/{}/#objava-{}".format(uporabnik, oid))

@bottle.post("/komentiraj/<oid>/")
def komentiraj(oid):
    """ Komentiraj objavo na glavni strani prijavljenega uporabnika """
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    komentar = bottle.request.forms.komentar
    if komentar:
        cur.execute("INSERT INTO komentar(avtor,id_objava,vsebina) VALUES (%s, %s, %s)", [uporabnik_prijavljen, oid, komentar])
        conn.commit()
    return bottle.redirect(ROOT + "#trac-{}".format(oid))
    
@bottle.get("/uporabnik/<uporabnik>/komentar/<oid>/<kid>/brisi/")
def brisi_komentar_na_zidu(uporabnik, oid, kid):
    """ Briši komentar na uporabnikovem zidu pri objavi """
    cur.execute("DELETE FROM komentar WHERE id=%s",[kid])
    set_sporocilo("alert-success", "Uspešno ste zbrisali komentar!")
    conn.commit()
    return bottle.redirect(ROOT + "uporabnik/{}/#objava-{}".format(uporabnik, oid))

@bottle.get("/uporabnik/<uporabnik>/objava/<oid>/brisi/")
def brisi_komentar_na_zidu(uporabnik, oid):
    """ Briši komentar na uporabnikovem zidu pri objavi """
    cur.execute("""DELETE FROM komentar 
    WHERE id_objava IN (SELECT id from objava WHERE id=%s)""",[oid])
    cur.execute("DELETE FROM objava WHERE id=%s",[oid])
    set_sporocilo("alert-success", "Uspešno ste zbrisali objavo!")
    conn.commit()
    return bottle.redirect(ROOT + "uporabnik/{}/".format(uporabnik, oid))

@bottle.get("/uporabnik/<uporabnik>/moji_dogodki/")
def moji_dogodki(uporabnik):
    sporocilo = get_sporocilo()
    (uporabnik_prijavljen, ime_prijavljen, priimek_prijavljen) = get_user()
    (ime,priimek)=dobi_ime(uporabnik)
    if uporabnik_prijavljen != uporabnik:
        # Ne dovolimo dostopa urejanju podatkov drugim uporabnikom
        set_sporocilo("alert-danger", "Ne moreš gledati profila drugega uporabnika!")
        return bottle.redirect(ROOT)

    if uporabnik_prijavljen != uporabnik:
        dogodki_jih_organizira = dogodki_organizira(uporabnik = str(uporabnik))
        dogodki_se_udelezi = dogodki_udelezi(uporabnik = str(uporabnik))
    else:
        dogodki_jih_organizira = dogodki_organizira(uporabnik = str(uporabnik_prijavljen))
        dogodki_se_udelezi = dogodki_udelezi(uporabnik = str(uporabnik_prijavljen))
    
    return rtemplate("moji_dogodki.html",
                            dogodki_jih_organizira=dogodki_jih_organizira,
                            dogodki_se_udelezi=dogodki_se_udelezi,
                            ime=ime_prijavljen,
                            priimek=priimek_prijavljen,
                            sporocilo=sporocilo,
                            uporabnik = uporabnik,
                            profil_ime = ime,
                            profil_priimek = priimek,
                            stran = 'moji_dogodki',
                            uporabnik_prijavljen=uporabnik_prijavljen)


@bottle.get('/uporabnik/<uporabnik>/aktivnosti/')
def pokazi_aktivnost(uporabnik):
    """Pokaži stran vseh aktivnostmi, ki zanimajo uporabnika"""
    # Kdo je prijavljen?
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    aktivnosti_uporabnika = dobi_aktivnosti(uporabnik)
    ap = (aktivnosti_uporabnika if uporabnik_prijavljen == uporabnik else dobi_aktivnosti(uporabnik_prijavljen))
    aktivnosti_prijavljenega = set()
    for v in ap.values():
        b = aktivnosti_prijavljenega.union(v)
        aktivnosti_prijavljenega = b
    ime_profil, priimek_profil = dobi_ime(uporabnik)
    sporocilo = get_sporocilo()
    vse_aktivnosti = []
    if uporabnik == uporabnik_prijavljen:
        # V tem primeru bomo potrebovali listo vseh aktivnosti
        cur.execute("""SELECT ime FROM aktivnost ORDER BY ime""")
        for a in cur:
            vse_aktivnosti.append(a[0])
    return rtemplate("aktivnosti.html",
                           uporabnik_prijavljen=uporabnik_prijavljen,
                           ime=ime_prijavljen,
                           aktivnosti=aktivnosti_uporabnika,
                           aktivnosti_prijavljenega=aktivnosti_prijavljenega,
                           priimek=priimek_prijavljen,
                           uporabnik=uporabnik,
                           profil_ime=ime_profil,
                           profil_priimek=priimek_profil,
                           sporocilo=sporocilo,
                           vse_aktivnosti=vse_aktivnosti)

@bottle.get('/<uporabnik>/<aktivnost>/odstrani/')
def odstrani_aktivnost(uporabnik, aktivnost):
    """Odstranimo aktivnost s seznama aktivnosti, ki zanimajo upoorabnika"""
    # Kdo je prijavljen?
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    cur.execute("""
    DELETE FROM se_ukvarja 
    WHERE uporabnisko_ime=%s AND se_ukvarja.id_aktivnost IN
    (SELECT id FROM aktivnost WHERE aktivnost.ime=%s)
    """, [uporabnik_prijavljen, aktivnost])
    set_sporocilo("alert-success", "Uspešno ste zbrisali aktivnost!")
    conn.commit()
    return bottle.redirect(ROOT + 'uporabnik/{}/aktivnosti/#{}'.format(uporabnik,aktivnost))

@bottle.get('/<uporabnik>/<aktivnost>/dodaj/')
def odstrani_aktivnost(uporabnik, aktivnost):
    """Dodamo aktivnost v seznama aktivnosti, ki zanimajo upoorabnika"""
    # Kdo je prijavljen?
    (uporabnik_prijavljen, ime_prijavljen,priimek_prijavljen) = get_user()
    cur.execute("""
    INSERT INTO se_ukvarja SELECT %s, id FROM aktivnost WHERE ime=%s
    """, [uporabnik_prijavljen, aktivnost])
    set_sporocilo("alert-success", "Uspešno ste dodali aktivnost!")
    conn.commit()
    return bottle.redirect(ROOT +  'uporabnik/{}/aktivnosti/#{}'.format(uporabnik,aktivnost))

@bottle.post('/uporabnik/<uporabnik>/aktivnosti/')
def dodaj_aktivnost(uporabnik):
    aktivnost = bottle.request.forms.izbrana_aktivnost
    cur.execute("""
    INSERT INTO se_ukvarja SELECT %s, id FROM aktivnost WHERE ime=%s
    """, [uporabnik, aktivnost])
    set_sporocilo("alert-success", "Uspešno ste dodali aktivnost!")
    conn.commit()
    return bottle.redirect(ROOT + 'uporabnik/{}/aktivnosti/'.format(uporabnik,aktivnost))
######################################################################
# Glavni program

# priklopimo se na bazo
conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password, port=DB_PORT)
#conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT) # onemogočimo transakcije
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# poženemo strežnik na podanih vratih, npr. http://localhost:8080/
bottle.run(host='localhost', port=SERVER_PORT, reloader=RELOADER)
