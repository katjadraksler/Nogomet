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
    ulica TEXT NOT NULL,
    hisna_stevilka TEXT,
    id_posta INTEGER REFERENCES posta(id),
    UNIQUE (ulica, hisna_stevilka, id_posta)
);

CREATE TABLE uporabnik (
    uporabnisko_ime TEXT PRIMARY KEY NOT NULL,
    ime TEXT NOT NULL,
    priimek TEXT NOT NULL,
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
    uporabnisko_ime TEXT REFERENCES uporabnik(uporabnisko_ime),
    id_aktivnost INTEGER REFERENCES aktivnost(id),
    PRIMARY KEY (uporabnisko_ime, id_aktivnost)
);

CREATE TABLE dogodek (
    id SERIAL PRIMARY KEY,
    organizator TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    id_aktivnost INTEGER REFERENCES aktivnost(id) NOT NULL,
    opis TEXT,
    datum DATE NOT NULL,
    cas TIME NOT NULL,
    id_lokacija INTEGER REFERENCES lokacija(id),
    stevilo_udelezencev INTEGER
);

CREATE TABLE objava (
    id SERIAL PRIMARY KEY,
    avtor TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    vsebina TEXT,
    cas TIMESTAMP DEFAULT now(),
    id_dogodek INTEGER REFERENCES dogodek(id)
);

CREATE TABLE komentar (
    id SERIAL PRIMARY KEY,
    avtor TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    id_objava INTEGER REFERENCES objava(id) NOT NULL,
    vsebina TEXT NOT NULL,
    cas TIMESTAMP DEFAULT now()
);

CREATE TABLE sledilec (
    sledilec TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    zasledovani TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    PRIMARY KEY (sledilec,zasledovani),
    CHECK (sledilec <> zasledovani)
);

CREATE TABLE udelezba (
    udelezenec TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    id_dogodek INTEGER REFERENCES dogodek(id) NOT NULL,
    PRIMARY KEY (id_dogodek,udelezenec)
);

CREATE TABLE sporocila (
    posiljatelj TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    prejemnik TEXT REFERENCES uporabnik(uporabnisko_ime) NOT NULL,
    vsebina TEXT NOT NULL,
    cas TIMESTAMP DEFAULT now(),
    CHECK (posiljatelj <> prejemnik)
);

GRANT ALL ON DATABASE sem2020_katjad TO katjad;
GRANT ALL ON SCHEMA public TO katjad;
GRANT ALL ON ALL TABLES IN SCHEMA public TO katjad;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO katjad;
GRANT ALL ON DATABASE sem2020_katjad TO gasperm;
GRANT ALL ON SCHEMA public TO gasperm;
GRANT ALL ON ALL TABLES IN SCHEMA public TO gasperm;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO gasperm;
