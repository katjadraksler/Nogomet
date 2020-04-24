# uvozimo ustrezne podatke za povezavo
import auth

# uvozimo psycopg2
import psycopg2, psycopg2.extensions, psycopg2.extras
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE) # se znebimo problemov s šumniki

import csv

def uvozi_podatke():
    with open("podatki/posta.csv", encoding="UTF-8") as f:
        rd = csv.reader(f)
        next(rd) # izpusti naslovno vrstico
        for r in rd:
            r = [None if x in ('', '-') else x for x in r]
            cur.execute("""
                INSERT INTO posta
                (postna_stevilka, kraj, drzava)
                VALUES (%s, %s, %s)
                RETURNING id
            """, r)
            rid, = cur.fetchone()
            print("Uvožena pošta %s z ID-jem %d" % (r[0], rid))
    conn.commit()

conn = psycopg2.connect(database=auth.db, host=auth.host, user=auth.user, password=auth.password)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 

uvozi_podatke()