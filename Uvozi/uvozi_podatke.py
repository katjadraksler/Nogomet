# uvozimo ustrezne podatke za povezavo
import auth
import time

# uvozimo psycopg2
import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # se znebimo problemov s šumniki

import csv

def uvoziSQL(datoteka):
    with open("podatki/{}.sql".format(datoteka)) as f:
        koda = f.read()
        cur.execute(koda)
    conn.commit()

def uvozi_podatke(tabela, izpusti=set()):
    with open("podatki/{}.csv".format(tabela), encoding="UTF-8") as f:
        rd = csv.reader(f)
        gl = next(rd)
        glava = [x for i, x in enumerate(gl) if i not in izpusti]
        n = len(gl)
        for r in rd:
            r = [None if x in ('', '-') else x for i, x in enumerate(r) if i not in izpusti]
            cur.execute("""
                INSERT INTO {0}
                ({1})
                VALUES ({2})
            """.format(
                tabela, ",".join(glava), ",".join(['%s']*len(glava))
            ), r)
    conn.commit()
    print("koncal {}".format(tabela))

conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

uvoziSQL('aktinet')
uvozi_podatke('posta')
uvozi_podatke('lokacija')
uvozi_podatke('uporabnik')
uvozi_podatke('tip_aktivnosti', {0})
uvozi_podatke('aktivnost', {0})
uvozi_podatke('dogodek')
uvozi_podatke('objava')
uvozi_podatke('sledilec')
uvozi_podatke('sporocila')
uvozi_podatke('udelezba')
uvozi_podatke('komentar')
uvozi_podatke('se_ukvarja')