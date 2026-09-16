// =================================================================
// GÖKTUNGU — LİSANSI YENİLE (v2.4.201)
// -----------------------------------------------------------------
// Kullanici bildirimi: merkezde M50 yetkisi acildigi halde yerel
// `merkez_lisans.json` eski kaldigi icin Elektro-Optik menusu
// gorunmuyordu; tek yol belgeyi elle indirip degistirmekti. Bu panel
// merkezden guncel belgeyi indirtir; sunucu imzayi dogrulayip diske
// yazar ve yeni yetki ozetini doner. Menu gorunurlugu aninda tazelenir.
// Sifre yalnizca istekte tasinir; ekranda ve yerelde saklanmaz.
// =================================================================
"use strict";
(function lisansYenilePaneli(){
  const adres = document.getElementById("lsAdres");
  const eposta = document.getElementById("lsEposta");
  const sifre = document.getElementById("lsSifre");
  const durum = document.getElementById("lsDurum");
  const ozetEl = document.getElementById("lsOzet");
  const yenile = document.getElementById("btnLsYenile");
  const iptal = document.getElementById("btnLsIptal");
  if (!yenile) return;
  const T = () => (typeof D === "function" ? D() : {}) || {};
  const kapat = () => { const p = document.getElementById("yzLisans"); if (p) p.classList.add("yuzen-gizli"); if (sifre) sifre.value = ""; };
  function ozetYaz(o){
    if (!ozetEl) return;
    if (!o || typeof o !== "object"){ ozetEl.textContent = ""; return; }
    const e = v => v ? "✓" : "✗";
    ozetEl.textContent = (o.firma_unvan || "") + "  ·  radar " + e(o.radar) +
      "  elektro-optik " + e(o.m50) + "  yapay zekâ " + e(o.ai) + "  gccdual " + e(o.gccdual);
  }
  const mb = document.getElementById("mbLisansYenile");
  if (mb) mb.addEventListener("click", () => {
    if (typeof window.lisansOzetiAl === "function") ozetYaz(window.lisansOzetiAl());
    if (durum) durum.textContent = "";
    if (eposta && !eposta.value && typeof oturum !== "undefined" && oturum && oturum.eposta)
      eposta.value = oturum.eposta;
  });
  yenile.addEventListener("click", () => {
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1){
      if (durum) durum.textContent = T().wsKoptu || "Sunucu bağlantısı yok.";
      return;
    }
    yenile.disabled = true;
    if (durum) durum.textContent = T().lsBekleniyor || "Merkezden lisans belgesi alınıyor…";
    ws.send(JSON.stringify({tip: "lisans_yenile", adres: adres.value.trim(),
                            eposta: eposta.value.trim(), sifre: sifre.value}));
    sifre.value = "";
  });
  if (iptal) iptal.addEventListener("click", kapat);
  window.lisansYenileSonuc = function(m){
    yenile.disabled = false;
    if (!m) return;
    if (m.basarili){
      if (durum) durum.textContent = T().lsTamam || "Lisans yenilendi; yetkiler güncellendi.";
      ozetYaz(m.lisans);
      if (typeof window.lisansOzetiSunucudan === "function") window.lisansOzetiSunucudan(m.lisans || null);
    } else {
      if (durum) durum.textContent = (T().lsHata || "Lisans yenilenemedi: ") + (m.hata || "");
    }
  };
})();
