(() => {
  "use strict";

  const tracks = [...document.querySelectorAll(".album-card, .recent-item")];
  const uniqueTracks = [];
  const seenTracks = new Set();
  for (const item of tracks) {
    const key = `${item.dataset.track}|${item.dataset.artist}`;
    if (!seenTracks.has(key)) {
      seenTracks.add(key);
      uniqueTracks.push({
        title: item.dataset.track,
        artist: item.dataset.artist,
        source: item.dataset.source,
        cover: item.dataset.cover,
      });
    }
  }

  const viewLabels = {
    start: "Start",
    music: "Musik",
    spotify: "Spotify",
    playlists: "Playlists",
    rfid: "RFID",
    energy: "Akku & PiSugar",
    settings: "Einstellungen",
  };
  const viewDescriptions = {
    music: "Die gemeinsame Musikliste aus lokalen Titeln und Spotify-Beispielen.",
    spotify: "Spotify ist hier als Quelle gekennzeichnet. Eine Kontoverbindung gibt es in dieser Vorschau nicht.",
    playlists: "Deine Playlists erscheinen hier später aus der Phoniebox-Verwaltung.",
    rfid: "RFID-Zuordnungen werden in dieser Vorschau nicht mit Karten oder Geräten verändert.",
    settings: "Einstellungen bleiben Beispieldaten; diese Vorschau ändert keine Gerätekonfiguration.",
  };
  const viewIcons = { music: "♫", spotify: "●", playlists: "▤", rfid: "▧", settings: "⚙" };
  const body = document.body;
  const sidebar = document.querySelector("#sidebar");
  const menuToggle = document.querySelector(".menu-toggle");
  const scrim = document.querySelector(".sidebar-scrim");
  const search = document.querySelector("#music-search");
  const albumGrid = document.querySelector("#album-grid");
  const recentList = document.querySelector("#recent-list");
  const emptyState = document.querySelector("#empty-state");
  const energyPanel = document.querySelector("#energy-panel");
  const placeholder = document.querySelector("#placeholder-panel");
  const batteryStatus = document.querySelector("#battery-status");
  const queueButton = document.querySelector(".queue-button");
  const queuePanel = document.querySelector("#queue-panel");
  let currentTrack = 0;
  let playing = true;

  function setMenu(open) {
    const wasOpen = body.classList.contains("menu-open");
    body.classList.toggle("menu-open", open);
    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.setAttribute("aria-label", open ? "Menü schließen" : "Menü öffnen");
    if (open) {
      const active = sidebar.querySelector('.nav-item[aria-current="page"]');
      active?.focus();
    } else if (wasOpen) {
      menuToggle.focus();
    }
  }

  function setView(view) {
    const label = viewLabels[view] || viewLabels.start;
    document.querySelectorAll(".nav-item[data-view]").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    document.querySelector("#breadcrumb-current").textContent = label;
    const isEnergy = view === "energy";
    const isPlaceholder = ["rfid", "settings"].includes(view);
    energyPanel.hidden = !isEnergy;
    placeholder.hidden = !isPlaceholder;
    document.querySelectorAll(".hero, .music-section").forEach((section) => {
      section.hidden = isEnergy || isPlaceholder;
    });
    if (isPlaceholder) {
      document.querySelector("#placeholder-title").textContent = label;
      document.querySelector("#placeholder-description").textContent = viewDescriptions[view];
      document.querySelector("#placeholder-icon").textContent = viewIcons[view];
    }
    closeQueue();
    setMenu(false);
    if (window.matchMedia("(max-width: 700px)").matches) window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function filterMusic() {
    const term = search.value.trim().toLocaleLowerCase("de");
    let visibleAlbums = 0;
    document.querySelectorAll(".album-card").forEach((card) => {
      const match = !term || card.dataset.search.includes(term);
      card.hidden = !match;
      if (match) visibleAlbums += 1;
    });
    document.querySelectorAll(".recent-item").forEach((item) => {
      item.hidden = Boolean(term) && !item.dataset.search.includes(term);
    });
    emptyState.hidden = visibleAlbums !== 0;
    albumGrid.hidden = visibleAlbums === 0;
    recentList.closest(".music-section").hidden = visibleAlbums === 0 || !term;
  }

  function paintTrack(track) {
    document.querySelector("#player-title").textContent = track.title;
    const artist = document.querySelector("#player-artist");
    artist.replaceChildren(document.createTextNode(`${track.artist} · `));
    const source = document.createElement("span");
    source.className = "source-text";
    source.textContent = track.source;
    artist.append(source);
    const cover = document.querySelector("#player-cover");
    cover.className = `player-cover ${track.cover}`;
    const artDetail = document.createElement("span");
    artDetail.className = track.cover === "cover-sun" ? "sun-disc" : track.cover === "cover-wave" ? "wave-sun" : track.cover === "cover-comet" ? "comet-star" : "cover-word";
    if (track.cover === "cover-comet") artDetail.textContent = "✦";
    cover.replaceChildren(artDetail);
  }

  function selectTrack(track) {
    const index = uniqueTracks.findIndex((item) => item.title === track.title && item.artist === track.artist);
    if (index >= 0) currentTrack = index;
    paintTrack(track);
    setPlaying(true);
  }

  function setPlaying(nextPlaying) {
    playing = nextPlaying;
    const button = document.querySelector(".play-toggle");
    button.setAttribute("aria-pressed", String(playing));
    button.setAttribute("aria-label", playing ? "Vorschau pausieren" : "Vorschau fortsetzen");
    button.querySelector("span").textContent = playing ? "Ⅱ" : "▶";
    document.querySelector("#playback-state").textContent = playing ? "Vorschau läuft" : "Vorschau pausiert";
  }

  function moveTrack(direction) {
    currentTrack = (currentTrack + direction + uniqueTracks.length) % uniqueTracks.length;
    paintTrack(uniqueTracks[currentTrack]);
    setPlaying(true);
  }

  function closeQueue() {
    queuePanel.hidden = true;
    queueButton.setAttribute("aria-expanded", "false");
  }

  function setBatteryMode(mode) {
    const enabled = mode !== "off";
    const known = mode === "active";
    batteryStatus.hidden = !enabled;
    if (known) {
      document.querySelector("#battery-label").textContent = "PiSugar · 82 %";
      document.querySelector("#energy-state-title").textContent = "Akku verbunden";
      document.querySelector("#energy-state-description").textContent = "Der Akkustand ist als Beispieldatum verfügbar.";
      document.querySelector("#energy-reading").hidden = false;
      document.querySelector("#battery-fill").style.height = "72%";
      document.querySelector(".battery-pill").setAttribute("aria-label", "PiSugar-Akku: 82 Prozent, Energieansicht öffnen");
    } else if (mode === "unreachable") {
      document.querySelector("#battery-label").textContent = "PiSugar · unbekannt";
      document.querySelector("#energy-state-title").textContent = "Akku nicht erreichbar";
      document.querySelector("#energy-state-description").textContent = "Der aktuelle Akkustand ist nicht verfügbar.";
      document.querySelector("#energy-reading").hidden = true;
      document.querySelector("#battery-fill").style.height = "0%";
      document.querySelector(".battery-pill").setAttribute("aria-label", "PiSugar-Akku unbekannt, Energieansicht öffnen");
    } else {
      document.querySelector("#energy-state-title").textContent = "PiSugar deaktiviert";
      document.querySelector("#energy-state-description").textContent = "Für dieses Gerät ist kein PiSugar-Status aktiv.";
      document.querySelector("#energy-reading").hidden = true;
      document.querySelector("#battery-fill").style.height = "0%";
    }
  }

  document.addEventListener("click", (event) => {
    const viewButton = event.target.closest("[data-view]");
    if (viewButton) {
      setView(viewButton.dataset.view);
      return;
    }
    const trackButton = event.target.closest("[data-track]");
    if (trackButton) {
      selectTrack({ title: trackButton.dataset.track, artist: trackButton.dataset.artist, source: trackButton.dataset.source, cover: trackButton.dataset.cover });
      return;
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "play-mix") {
      currentTrack = 0;
      paintTrack(uniqueTracks[currentTrack]);
      setPlaying(true);
    } else if (action === "toggle-play") {
      setPlaying(!playing);
    } else if (action === "previous") {
      moveTrack(-1);
    } else if (action === "next") {
      moveTrack(1);
    }
  });

  menuToggle.addEventListener("click", () => setMenu(true));
  scrim.addEventListener("click", () => setMenu(false));
  search.addEventListener("input", filterMusic);
  document.querySelector("#reset-search").addEventListener("click", () => {
    search.value = "";
    filterMusic();
    search.focus();
  });
  document.querySelector("#volume").addEventListener("input", (event) => {
    document.querySelector("#volume-value").textContent = event.target.value;
  });
  document.querySelector(".player-like").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const liked = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(liked));
    button.setAttribute("aria-label", liked ? "Titel nicht mehr merken" : "Titel merken");
    button.textContent = liked ? "♥" : "♡";
  });
  queueButton.addEventListener("click", () => {
    const open = queueButton.getAttribute("aria-expanded") !== "true";
    queueButton.setAttribute("aria-expanded", String(open));
    queuePanel.hidden = !open;
  });
  document.querySelectorAll('input[name="battery-mode"]').forEach((input) => {
    input.addEventListener("change", (event) => setBatteryMode(event.target.value));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (body.classList.contains("menu-open")) setMenu(false);
      closeQueue();
    }
    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      search.focus();
    }
  });

  paintTrack(uniqueTracks[0]);
  setBatteryMode("active");
})();
