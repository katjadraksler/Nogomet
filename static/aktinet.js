'use strict'

function isci(stolpci) {
    let vrednost = document.getElementById('isci').value;
    stolpci.forEach(vrstica => {
        if(vrstica.some(stolpec => seUjema(stolpec,vrednost))) {
            document.getElementById(vrstica[0]).classList.remove('d-none');
        } else {
            document.getElementById(vrstica[0]).classList.add('d-none');
        }
    })
}  

function seUjema(vsebina, vrednost) {
    return vsebina.toLocaleLowerCase().indexOf(vrednost.toLocaleLowerCase()) >= 0
}