import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  HashRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useLocation,
} from 'react-router-dom';

import {
  DEMO_BATTERY_PERCENT,
  filterTracks,
  getRelativeTrack,
  getTrack,
  getUpcomingTracks,
  INITIAL_TRACK_ID,
  RECENT_TRACK_IDS,
} from './previewModel';
import './styles.css';

const ROUTES = [
  { path: '/start', label: 'Start', icon: '⌂' },
  { path: '/music', label: 'Musik', icon: '♫' },
  { path: '/spotify', label: 'Spotify', icon: '●', spotify: true },
  { path: '/playlists', label: 'Playlists', icon: '▤' },
  { path: '/rfid', label: 'RFID', icon: '▧' },
  { path: '/energy', label: 'Akku & PiSugar', icon: '◒' },
  { path: '/settings', label: 'Einstellungen', icon: '⚙' },
];

function SourceBadge({ source }) {
  const className = source === 'Spotify' ? 'source-tag source-spotify' : 'source-tag source-local';
  return <span className={className}>{source}</span>;
}

function CoverArt({ track, compact = false }) {
  return (
    <span className={`cover-art ${track.cover}${compact ? ' cover-compact' : ''}`} aria-hidden="true">
      {track.cover === 'cover-sun' && <><span className="sun-disc" /><span className="cover-land" /></>}
      {track.cover === 'cover-wave' && <><span className="wave-sun" /><span className="wave-line wave-a" /><span className="wave-line wave-b" /></>}
      {track.cover === 'cover-comet' && <><span className="comet-orbit" /><span className="comet-star">✦</span></>}
      {track.cover === 'cover-park' && <><span className="park-sun" /><span className="park-hill hill-back" /><span className="park-hill hill-front" /></>}
      {track.cover === 'cover-dance' && <><span className="dance-shape shape-one" /><span className="dance-shape shape-two" /><span className="dance-shape shape-three" /></>}
      {track.cover === 'cover-cloud' && <><span className="cloud-shape cloud-a" /><span className="cloud-shape cloud-b" /></>}
      {!compact && <span className="cover-word">{track.title.toLocaleUpperCase('de')}</span>}
    </span>
  );
}

function TrackCard({ track, onSelect }) {
  return (
    <button className="album-card" type="button" onClick={() => onSelect(track)}>
      <CoverArt track={track} />
      <span className="album-title">{track.title}</span>
      <span className="album-subtitle">{track.artist} <SourceBadge source={track.source} /></span>
    </button>
  );
}

function TrackGrid({ tracks, onSelect, query, onReset }) {
  if (tracks.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-icon" aria-hidden="true">⌕</span>
        <h3>Nichts gefunden</h3>
        <p>Zu dieser Suche gibt es in den Beispieldaten keine Titel.</p>
        <button className="button-secondary" type="button" onClick={onReset}>Suche zurücksetzen</button>
      </div>
    );
  }
  return (
    <div className="album-grid" aria-live="polite" data-search={query ? 'filtered' : 'all'}>
      {tracks.map((track) => <TrackCard key={track.id} track={track} onSelect={onSelect} />)}
    </div>
  );
}

function SectionHeading({ eyebrow, title, titleId, action, onAction }) {
  return (
    <div className="section-heading">
      <div><p className="eyebrow section-eyebrow">{eyebrow}</p><h2 id={titleId}>{title}</h2></div>
      {action && <button className="text-button" type="button" onClick={onAction}>{action} <span aria-hidden="true">→</span></button>}
    </div>
  );
}

function Hero({ onPlay }) {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <p className="eyebrow">DEIN MIX AUS ALLEN WELTEN</p>
        <p className="hero-overline">Lieblingsmix</p>
        <h1 id="hero-title">Abend<br className="hero-break" /> für alle</h1>
        <p className="hero-description">Vertraute Lieblingslieder für Küche, Kinderzimmer und lange Abende.</p>
        <div className="hero-meta"><span>18 Titel</span><span className="meta-divider" aria-hidden="true" /><span>Eigene Musik &amp; Spotify</span></div>
        <button className="hero-play" type="button" onClick={onPlay}><span aria-hidden="true">▶</span> Mix starten</button>
      </div>
      <div className="hero-art" aria-hidden="true">
        <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
        <div className="hero-record"><div className="record-groove" /><div className="record-label">PB<span>♫</span></div></div>
        <div className="hero-spark spark-one">✳</div><div className="hero-spark spark-two">✦</div>
      </div>
    </section>
  );
}

function RecentList({ tracks, onSelect }) {
  return (
    <div className="recent-list">
      {tracks.map((track) => (
        <button className="recent-item" key={track.id} type="button" onClick={() => onSelect(track)}>
          <span className="mini-cover"><CoverArt track={track} compact /></span>
          <span className="recent-copy"><strong>{track.title}</strong><span>{track.artist}</span></span>
          <SourceBadge source={track.source} /><span className="recent-arrow" aria-hidden="true">↗</span>
        </button>
      ))}
    </div>
  );
}

function PlaceholderPage({ title, description, icon }) {
  return (
    <section className="placeholder-panel" aria-live="polite">
      <div className="placeholder-icon" aria-hidden="true">{icon}</div>
      <p className="eyebrow">PHONIEBOX</p>
      <h1>{title}</h1>
      <p>{description}</p>
      <span className="demo-only">Ansicht in der Designvorschau</span>
    </section>
  );
}

function EnergyPage({ batteryMode, setBatteryMode }) {
  const active = batteryMode === 'active';
  const unreachable = batteryMode === 'unreachable';
  return (
    <section className="device-panel" aria-labelledby="energy-title">
      <div className="section-heading">
        <div><p className="eyebrow section-eyebrow">GERÄTESTATUS</p><h1 id="energy-title">Akku &amp; PiSugar</h1></div>
        <span className="demo-only">Nur Vorschau</span>
      </div>
      <div className="energy-card">
        <div className="energy-illustration" aria-hidden="true">
          <span className="battery-large"><span style={{ transform: `scaleY(${active ? DEMO_BATTERY_PERCENT / 100 : 0})` }} /></span>
          <span className="energy-spark">✦</span>
        </div>
        <div className="energy-copy">
          <p className="eyebrow">PISUGAR 2 · 2 LED</p>
          <h2>{active ? 'Akku verbunden' : unreachable ? 'Akku nicht erreichbar' : 'PiSugar deaktiviert'}</h2>
          <p>{active ? 'Der Akkustand ist als Beispieldatum verfügbar.' : unreachable ? 'Der aktuelle Akkustand ist nicht verfügbar.' : 'Für dieses Gerät ist kein PiSugar-Status aktiv.'}</p>
          {active && <div className="energy-reading"><strong>{DEMO_BATTERY_PERCENT}%</strong><span>Akku</span></div>}
        </div>
      </div>
      <fieldset className="preview-controls">
        <legend>Vorschauzustand simulieren</legend>
        <label><input type="radio" name="battery-mode" value="active" checked={active} onChange={() => setBatteryMode('active')} /> Aktiv · Prozent bekannt</label>
        <label><input type="radio" name="battery-mode" value="unreachable" checked={unreachable} onChange={() => setBatteryMode('unreachable')} /> Aktiv · nicht erreichbar</label>
        <label><input type="radio" name="battery-mode" value="off" checked={batteryMode === 'off'} onChange={() => setBatteryMode('off')} /> PiSugar deaktiviert</label>
      </fieldset>
      <p className="honest-note">Diese Auswahl ändert nur die Anzeige. Es werden keine Energieaktionen am Gerät ausgeführt.</p>
    </section>
  );
}

function PreviewShell() {
  const [currentTrackId, setCurrentTrackId] = useState(INITIAL_TRACK_ID);
  const [playing, setPlaying] = useState(true);
  const [liked, setLiked] = useState(false);
  const [volume, setVolume] = useState(64);
  const [queueOpen, setQueueOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [batteryMode, setBatteryMode] = useState('active');
  const [query, setQuery] = useState('');
  const searchRef = useRef(null);
  const menuToggleRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const currentTrack = getTrack(currentTrackId);
  const upcomingTracks = useMemo(() => getUpcomingTracks(currentTrackId), [currentTrackId]);
  const visibleTracks = useMemo(() => filterTracks(query), [query]);
  const recentTracks = useMemo(
    () => RECENT_TRACK_IDS.map(getTrack).filter((track) => !query.trim() || track.search.includes(query.trim().toLocaleLowerCase('de'))),
    [query],
  );
  const currentView = location.pathname.split('/').filter(Boolean).pop() || 'start';
  const batteryAvailable = batteryMode !== 'off';

  useEffect(() => {
    setMenuOpen(false);
    setQueueOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        if (menuOpen) {
          setMenuOpen(false);
          menuToggleRef.current?.focus();
        }
        setQueueOpen(false);
      }
      if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey
        && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [menuOpen]);

  function selectTrack(track) {
    setCurrentTrackId(track.id);
    setPlaying(true);
  }

  function moveTrack(offset) {
    setCurrentTrackId(getRelativeTrack(currentTrackId, offset).id);
    setPlaying(true);
  }

  function startMix() {
    setCurrentTrackId(INITIAL_TRACK_ID);
    setPlaying(true);
  }

  function resetSearch() {
    setQuery('');
    searchRef.current?.focus();
  }

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <div className="design-preview">
        <aside className={`sidebar${menuOpen ? ' sidebar-open' : ''}`} id="preview-sidebar" aria-label="Hauptnavigation">
          <Link className="brand" to="/start" aria-label="Phoniebox Start" onClick={closeMenu}>
            <span className="brand-mark" aria-hidden="true">♫</span><span>phoniebox</span>
          </Link>
          <p className="nav-label">Bibliothek</p>
          <nav className="primary-nav" aria-label="Bereiche">
            {ROUTES.slice(0, 5).map((route) => <NavigationLink key={route.path} route={route} onNavigate={closeMenu} />)}
          </nav>
          <p className="nav-label nav-label-spaced">Gerät</p>
          <nav className="primary-nav" aria-label="Gerät">
            {ROUTES.slice(5).map((route) => <NavigationLink key={route.path} route={route} onNavigate={closeMenu} />)}
          </nav>
          <div className="sidebar-note"><span className="status-dot" aria-hidden="true" /><span>Lokale Vorschau</span></div>
        </aside>
        <button className="sidebar-scrim" type="button" aria-label="Menü schließen" tabIndex={-1} onClick={closeMenu} />

        <main className="main-content">
          <header className="topbar">
            <button
              className="menu-toggle icon-button"
              type="button"
              ref={menuToggleRef}
              aria-label={menuOpen ? 'Menü schließen' : 'Menü öffnen'}
              aria-expanded={menuOpen}
              aria-controls="preview-sidebar"
              onClick={() => setMenuOpen(true)}
            >☰</button>
            <div className="breadcrumbs"><span className="breadcrumb-kicker">DEINE MUSIK</span><span className="breadcrumb-current">{ROUTES.find((route) => route.path === `/${currentView}`)?.label || 'Start'}</span></div>
            <label className="search-box" htmlFor="preview-search">
              <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="6.4" /><path d="m16 16 4.1 4.1" /></svg>
              <input id="preview-search" ref={searchRef} type="search" aria-label="Titel, Album oder Quelle suchen" placeholder="Titel, Album oder Quelle suchen" value={query} onChange={(event) => setQuery(event.target.value)} />
              <kbd>/</kbd>
            </label>
            {batteryAvailable && (
              <Link className="battery-pill" to="/energy" aria-label={batteryMode === 'active' ? `PiSugar-Akku: ${DEMO_BATTERY_PERCENT} Prozent` : 'PiSugar-Akku unbekannt'}>
                <span className="battery-glyph" aria-hidden="true"><span /></span>
                <span>{batteryMode === 'active' ? `PiSugar · ${DEMO_BATTERY_PERCENT} %` : 'PiSugar · unbekannt'}</span>
              </Link>
            )}
            <div className="profile-avatar" aria-label="Profil: Zuhause">Z<span className="avatar-presence" aria-hidden="true" /></div>
          </header>

          <div className="preview-ribbon" role="note"><span className="ribbon-dot" aria-hidden="true" />Designvorschau · Beispieldaten</div>

          <Routes>
            <Route path="/" element={<Navigate to="/start" replace />} />
            <Route path="/start" element={(
              <>
                <Hero onPlay={startMix} />
                <section className="music-section" aria-labelledby="favorites-title">
                  <SectionHeading eyebrow="FÜR JEDEN MOMENT" title="Lieblingsmusik" titleId="favorites-title" action="Alle Titel" onAction={() => navigate('/music')} />
                  <TrackGrid tracks={visibleTracks.slice(0, 6)} onSelect={selectTrack} query={query} onReset={resetSearch} />
                </section>
                {(!query || recentTracks.length > 0) && <section className="music-section recent-section" aria-labelledby="recent-title">
                  <SectionHeading eyebrow="ZULETZT BEI EUCH" title="Kürzlich verwendet" titleId="recent-title" />
                  <RecentList tracks={recentTracks} onSelect={selectTrack} />
                </section>}
              </>
            )} />
            <Route path="/music" element={(
              <MusicPage title="Musik" eyebrow="EURE SAMMLUNG" tracks={visibleTracks} query={query} onSelect={selectTrack} onReset={resetSearch} />
            )} />
            <Route path="/spotify" element={(
              <MusicPage title="Spotify" eyebrow="VERBUNDENE QUELLE · BEISPIELDATEN" tracks={filterTracks(query, 'Spotify')} query={query} onSelect={selectTrack} onReset={resetSearch} description="Spotify-Titel sind hier Beispieldaten. Eine Kontoverbindung wird nicht hergestellt." />
            )} />
            <Route path="/playlists" element={(
              <MusicPage title="Playlists" eyebrow="EURE MISCHUNGEN" tracks={visibleTracks} query={query} onSelect={selectTrack} onReset={resetSearch} description="Die gemeinsame Musikvorschau zeigt, wie Titel aus beiden Quellen zusammenfinden." />
            )} />
            <Route path="/rfid" element={<PlaceholderPage title="RFID" icon="▧" description="RFID-Zuordnungen werden in dieser Vorschau nicht mit Karten oder Geräten verändert." />} />
            <Route path="/energy" element={<EnergyPage batteryMode={batteryMode} setBatteryMode={setBatteryMode} />} />
            <Route path="/settings" element={<PlaceholderPage title="Einstellungen" icon="⚙" description="Einstellungen bleiben Beispieldaten; diese Vorschau ändert keine Gerätekonfiguration." />} />
            <Route path="*" element={<Navigate to="/start" replace />} />
          </Routes>
          <footer className="page-footer">Phoniebox · Lokale Musik, die sich nach Zuhause anfühlt <span>U02b · Designvorschau</span></footer>
        </main>

        <footer className="player" aria-label="Vorschauplayer">
          <div className="player-track">
            <CoverArt track={currentTrack} compact />
            <div className="player-copy"><strong>{currentTrack.title}</strong><span>{currentTrack.artist} · <span className="source-text">{currentTrack.source}</span></span></div>
            <button className="player-like icon-button" type="button" aria-label={liked ? 'Titel nicht mehr merken' : 'Titel merken'} aria-pressed={liked} onClick={() => setLiked((value) => !value)}>{liked ? '♥' : '♡'}</button>
          </div>
          <div className="player-controls">
            <button className="icon-button" type="button" aria-label="Vorheriger Titel" onClick={() => moveTrack(-1)}>⏮</button>
            <button className="play-toggle" type="button" aria-label={playing ? 'Vorschau pausieren' : 'Vorschau fortsetzen'} aria-pressed={playing} onClick={() => setPlaying((value) => !value)}><span aria-hidden="true">{playing ? 'Ⅱ' : '▶'}</span></button>
            <button className="icon-button" type="button" aria-label="Nächster Titel" onClick={() => moveTrack(1)}>⏭</button>
          </div>
          <div className="player-progress"><div className="progress-label"><span>{playing ? 'Vorschau läuft' : 'Vorschau pausiert'}</span><span>Beispiel · ohne Audio</span></div><div className="progress-track" aria-hidden="true"><span /></div></div>
          <div className="player-volume"><span aria-hidden="true">◖</span><label className="visually-hidden" htmlFor="preview-volume">Vorschau-Lautstärke</label><input id="preview-volume" type="range" min="0" max="100" value={volume} onChange={(event) => setVolume(Number(event.target.value))} /><span className="volume-value">{volume}</span></div>
          <button className="queue-button icon-button" type="button" aria-expanded={queueOpen} aria-controls="preview-queue" aria-label="Warteschlange anzeigen" onClick={() => setQueueOpen((value) => !value)}>☷</button>
          {queueOpen && <div className="queue-panel" id="preview-queue" role="region" aria-label="Warteschlange">
            <strong>Als Nächstes</strong>
            <ol>{upcomingTracks.map((track) => <li key={track.id}>{track.title} · {track.source}</li>)}</ol>
          </div>}
        </footer>
    </div>
  );
}

function NavigationLink({ route, onNavigate }) {
  return (
    <NavLink
      className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`}
      to={route.path}
      end
      onClick={onNavigate}
    >
      <span className={`nav-icon${route.spotify ? ' spotify-icon' : ''}`} aria-hidden="true">{route.icon}</span>{route.label}
    </NavLink>
  );
}

function MusicPage({ title, eyebrow, tracks, query, onSelect, onReset, description }) {
  return (
    <section className="music-page">
      <div className="section-heading page-heading"><div><p className="eyebrow section-eyebrow">{eyebrow}</p><h1>{title}</h1></div></div>
      {description && <p className="page-description">{description}</p>}
      <TrackGrid tracks={tracks} onSelect={onSelect} query={query} onReset={onReset} />
    </section>
  );
}

export default function DesignPreview() {
  return (
    <HashRouter basename="/design-preview">
      <PreviewShell />
    </HashRouter>
  );
}
