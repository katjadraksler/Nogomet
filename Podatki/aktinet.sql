DROP TABLE IF EXISTS uporabnik CASCADE;
DROP TABLE IF EXISTS objava CASCADE;
DROP TABLE IF EXISTS posta CASCADE;
DROP TABLE IF EXISTS sledilec CASCADE;
DROP TABLE IF EXISTS komentar CASCADE;
DROP TABLE IF EXISTS sporocila CASCADE;
DROP TABLE IF EXISTS tip_aktivnosti CASCADE;
DROP TABLE IF EXISTS udelezba CASCADE;
DROP TABLE IF EXISTS aktivnost CASCADE;
DROP TABLE IF EXISTS dogodek CASCADE;
DROP TABLE IF EXISTS lokacija CASCADE;
DROP TABLE IF EXISTS se_ukvarja CASCADE;

CREATE TABLE posta (
    id SERIAL PRIMARY KEY,
    postna_stevilka TEXT NOT NULL,
    kraj TEXT NOT NULL,
    drzava TEXT NOT NULL,
    UNIQUE (postna_stevilka, drzava)
);

CREATE TABLE lokacija (
    id SERIAL PRIMARY KEY,
    drzava TEXT NOT NULL,
    ulica TEXT NOT NULL,
    hisna_stevilka TEXT NOT NULL,
    kraj TEXT NOT NULL,
    id_posta INTEGER REFERENCES posta(id),
    UNIQUE (drzava, ulica, hisna_stevilka, kraj, id_posta)
);

CREATE TABLE uporabnik (
    id SERIAL PRIMARY KEY,
    ime TEXT NOT NULL,
    priimek TEXT NOT NULL,
    uporabnisko_ime TEXT UNIQUE NOT NULL,
    geslo TEXT NOT NULL,
    spol TEXT,
    datum_rojstva DATE,
    id_lokacija INTEGER REFERENCES lokacija(id)
);

CREATE TABLE tip_aktivnosti (
    id SERIAL PRIMARY KEY,
    tip TEXT NOT NULL
);

CREATE TABLE aktivnost (
    id SERIAL PRIMARY KEY,
    ime TEXT NOT NULL,
    tip INTEGER REFERENCES tip_aktivnosti(id) NOT NULL
);

CREATE TABLE se_ukvarja (
    id_uporabnik INTEGER REFERENCES uporabnik(id),
    id_aktivnost INTEGER REFERENCES aktivnost(id),
    PRIMARY KEY (id_uporabnik, id_aktivnost)
);

CREATE TABLE dogodek (
    id SERIAL PRIMARY KEY,
    id_uporabnik INTEGER REFERENCES uporabnik(id) NOT NULL,
    id_aktivnost INTEGER REFERENCES aktivnost(id) NOT NULL,
    opis TEXT,
    datum DATE NOT NULL,
    cas TIME NOT NULL,
    id_lokacija INTEGER REFERENCES lokacija(id),
    stevilo_udelezencev INTEGER
);

CREATE TABLE objava (
    id SERIAL PRIMARY KEY,
    id_uporabnik INTEGER REFERENCES uporabnik(id) NOT NULL,
    zasebnost BOOLEAN NOT NULL,
    vsebina TEXT,
    cas TIMESTAMP DEFAULT now(),
    id_dogodek INTEGER REFERENCES dogodek(id)
);

CREATE TABLE komentar (
    id SERIAL PRIMARY KEY,
    id_uporabnik INTEGER REFERENCES uporabnik(id) NOT NULL,
    id_objava INTEGER REFERENCES uporabnik(id) NOT NULL,
    vsebina TEXT NOT NULL,
    cas TIMESTAMP DEFAULT now()
);

CREATE TABLE sledilec (
    sledilec INTEGER REFERENCES uporabnik(id) NOT NULL,
    zasledovani INTEGER REFERENCES uporabnik(id) NOT NULL,
    PRIMARY KEY (sledilec,zasledovani),
    CHECK (sledilec <> zasledovani)
);

CREATE TABLE udelezba (
    id_dogodek INTEGER REFERENCES dogodek(id) NOT NULL,
    id_uporabnik INTEGER REFERENCES uporabnik(id) NOT NULL,
    PRIMARY KEY (id_dogodek,id_uporabnik)
);

CREATE TABLE sporocila (
    posiljatelj INTEGER REFERENCES uporabnik(id) NOT NULL,
    prejemnik INTEGER REFERENCES uporabnik(id) NOT NULL,
    vsebina TEXT NOT NULL,
    cas TIMESTAMP DEFAULT now(),
    CHECK (posiljatelj <> prejemnik)
);