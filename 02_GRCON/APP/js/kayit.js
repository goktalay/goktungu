// =================================================================
// GOKTUNGU - RADAR VERI KAYDI & TEKRAR OYNATMA
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// --- RADAR VERI KAYDI & TEKRAR OYNATMA ---
function gonder(mesaj){
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(mesaj));
}
const btnKayit = document.getElementById("btnKayit");
const kayitNokta = document.getElementById("kayitNokta");
const btnKayitYazi = document.getElementById("btnKayitYazi");
const kayitBilgi = document.getElementById("kayitBilgi");
const btnKayitListeAc = document.getElementById("btnKayitListeAc");
const kayitListeKutu = document.getElementById("kayitListeKutu");
const replayKontrol = document.getElementById("replayKontrol");
const btnReplayDurdur = document.getElementById("btnReplayDurdur");
const replayHizSec = document.getElementById("replayHiz");
const replayBar = document.getElementById("replayBar");
const replayYazi = document.getElementById("replayYazi");
let kayitAktif = false;
let replayAktif = false;
let replayDosya = "";          // oynatilan kayit dosyasi (etiketleme icin)
let etiketler = {};            // {iz_id: etiket} — aktif replay dosyasinin etiketleri
let kayitListeAcik = false;

function kayitDurumGuncelle(k){
  kayitAktif = !!k.aktif;
  const t = D();
  btnKayit.classList.toggle("kayitta", kayitAktif);
  btnKayitYazi.textContent = kayitAktif ?
    (t.btnKayitDurdur || "KAYDI DURDUR") : (t.btnKayitBaslat || "KAYIT BA\u015eLAT");
  if (kayitAktif){
    kayitBilgi.style.display = "";
    kayitBilgi.textContent = "\u25cf REC " + sureBicimle(k.sure || 0) +
      " \u00b7 " + (k.kare || 0) + " kare \u00b7 " + (k.dosya || "");
  } else {
    kayitBilgi.style.display = "none";
  }
}

btnKayit.addEventListener("click", () => {
  gonder({tip: kayitAktif ? "kayit_durdur" : "kayit_baslat"});
});

btnKayitListeAc.addEventListener("click", () => {
  kayitListeAcik = !kayitListeAcik;
  kayitListeKutu.style.display = kayitListeAcik ? "" : "none";
  if (kayitListeAcik) gonder({tip: "kayit_liste"});
});

function kayitListeCiz(kayitlar){
  const t = D();
  kayitListeKutu.innerHTML = "";
  if (!kayitlar.length){
    const bos = document.createElement("div");
    bos.className = "ipucu";
    bos.textContent = t.kayitYok || "Hen\u00fcz kay\u0131t yok.";
    kayitListeKutu.appendChild(bos);
    return;
  }
  for (const ky of kayitlar){
    const sat = document.createElement("div");
    sat.className = "kayit-satir";
    const ad = document.createElement("div");
    ad.className = "kayit-ad";
    ad.textContent = ky.ad;
    const meta = document.createElement("div");
    meta.className = "kayit-meta";
    meta.textContent = sureBicimle(ky.sure || 0) + " \u00b7 " +
      (ky.kare || 0) + " kare \u00b7 " + ((ky.boyut || 0) / 1024).toFixed(0) + " KB";
    const dgm = document.createElement("div");
    dgm.className = "kayit-dugmeler";
    const oynat = document.createElement("button");
    oynat.innerHTML = '<i class="fa-solid fa-play"></i>';
    oynat.title = t.btnOynat || "Oynat";
    oynat.disabled = !!ky.aktif;
    oynat.addEventListener("click", () => {
      gonder({tip: "replay_baslat", dosya: ky.ad,
              hiz: parseFloat(replayHizSec.value) || 1});
    });
    const sil = document.createElement("button");
    sil.innerHTML = '<i class="fa-solid fa-trash"></i>';
    sil.title = t.btnSil || "Sil";
    sil.disabled = !!ky.aktif;
    sil.addEventListener("click", () => {
      gonder({tip: "kayit_sil", dosya: ky.ad});
    });
    dgm.appendChild(oynat); dgm.appendChild(sil);
    const solK = document.createElement("div");
    solK.style.flex = "1"; solK.style.minWidth = "0";
    solK.appendChild(ad); solK.appendChild(meta);
    sat.appendChild(solK); sat.appendChild(dgm);
    kayitListeKutu.appendChild(sat);
  }
}

function replayDurumGuncelle(rp){
  const oncekiAktif = replayAktif;
  replayAktif = !!rp.aktif;
  if (replayAktif && rp.dosya && rp.dosya !== replayDosya){
    replayDosya = rp.dosya;
    etiketler = {};
    gonder({tip: "etiket_liste", dosya: replayDosya});
  }
  if (!replayAktif && oncekiAktif){ replayDosya = ""; etiketler = {}; }
  replayKontrol.style.display = replayAktif ? "" : "none";
  const rozet = document.getElementById("replayRozet");
  if (replayAktif){
    const t = D();
    const toplam = rp.sure || 0;
    const konum = rp.konum || 0;
    replayBar.style.width = toplam > 0 ?
      Math.min(100, konum / toplam * 100).toFixed(1) + "%" : "0%";
    replayYazi.textContent = (rp.dosya || "") + " \u2014 " +
      sureBicimle(konum) + " / " + sureBicimle(toplam) +
      " (" + (rp.hiz || 1) + "x)";
    if (rozet){
      rozet.style.display = "";
      rozet.textContent = "\u25b6 " + (t.replayOynatiliyor || "KAYIT OYNATILIYOR") +
        " \u2014 " + (rp.dosya || "");
    }
    if (replayHizSec.value !== String(rp.hiz) &&
        document.activeElement !== replayHizSec){
      const v = String(rp.hiz);
      if ([...replayHizSec.options].some(o => o.value === v)) replayHizSec.value = v;
    }
  } else {
    if (rozet) rozet.style.display = "none";
    if (oncekiAktif){
      // Replay bitti: harita canli veriye doner, listeyi tazele
      if (kayitListeAcik) gonder({tip: "kayit_liste"});
    }
  }
}

btnReplayDurdur.addEventListener("click", () => gonder({tip: "replay_durdur"}));
replayHizSec.addEventListener("change", () => {
  if (replayAktif) gonder({tip: "replay_hiz", hiz: parseFloat(replayHizSec.value) || 1});
});

