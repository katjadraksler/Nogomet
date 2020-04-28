# uvozimo ustrezne podatke za povezavo
import auth

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

# uvoziSQL('aktinet')
<<<<<<< HEAD
uvozi_podatke('posta')
=======
# uvozi_podatke('posta')
>>>>>>> 5000b66b233d2683a33f4abbd1ef898cabfb1b17
# uvozi_podatke('lokacija', {0})
# uvozi_podatke('uporabnik', {0})
# uvozi_podatke('tip_aktivnosti', {0})
# uvozi_podatke('aktivnost', {0})
# uvozi_podatke('dogodek', {0})
# uvozi_podatke('objava', {0,4,5})
# uvozi_podatke('sledilec')
# uvozi_podatke('sporocila', {3,4})
# uvozi_podatke('udelezba')
# uvozi_podatke('komentar', {0,4,5})
<<<<<<< HEAD
# uvozi_podatke('se_ukvarja')
=======
uvozi_podatke('se_ukvarja')
>>>>>>> 5000b66b233d2683a33f4abbd1ef898cabfb1b17
