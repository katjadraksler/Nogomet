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

src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"

$(document).ready(function() {
    $('.header_background').click(function(e) {
      $(this).next('.section').slideToggle('slow');
      var img = $(this).find('img.expand_arrow')[0]; // the actual DOM element for the image
      if (img.src.indexOf('expand-arrow.png') != -1) {
        img.src  = 'images/collapse-arrow.png';
      }
      else {
         img.src = 'images/expand-arrow.png';
      }
    });
  });