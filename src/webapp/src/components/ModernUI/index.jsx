import React from 'react';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { getPlaylist, getQueue, listPlaylists, sendPlaylistCommand } from './playlistClient';
import LibraryBrowser from './LibraryBrowser';
import SettingsPage from './SettingsPage';

function Snapshot({ title, snapshot }) {
  if (!snapshot) return null;
  return <Paper component="section" sx={{ p: 2, mt: 2 }}>
    <Typography variant="h6">{title}: {snapshot.name || snapshot.queueId} · Revision {snapshot.revision}</Typography>
  </Paper>;
}

export default function ModernUI() {
  const [readToken, setReadToken] = React.useState('');
  const [writeToken, setWriteToken] = React.useState('');
  const [playlists, setPlaylists] = React.useState(null);
  const [playlist, setPlaylist] = React.useState(null);
  const [queueId, setQueueId] = React.useState('');
  const [queue, setQueue] = React.useState(null);
  const [commandText, setCommandText] = React.useState('');
  const [commandResult, setCommandResult] = React.useState(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [selectedEntryId, setSelectedEntryId] = React.useState(null);
  const [settingsDraft, setSettingsDraft] = React.useState({ local_playback: { http: { enabled: false, bearer_token_path: '', port: 8090 } } });
  const controllers = React.useRef(new Set());
  const busyRef = React.useRef(false);
  const credentialRef = React.useRef({ readToken, writeToken });
  const generationRef = React.useRef(0);
  const mountedRef = React.useRef(true);

  React.useEffect(() => {
    if (credentialRef.current.readToken !== readToken || credentialRef.current.writeToken !== writeToken) {
      credentialRef.current = { readToken, writeToken };
      generationRef.current += 1;
      controllers.current.forEach((controller) => controller.abort());
      controllers.current.clear();
      busyRef.current = false; setBusy(false);
      setPlaylists(null); setPlaylist(null); setQueue(null); setCommandResult(null); setSelectedEntryId(null); setError('');
    }
  }, [readToken, writeToken]);
  React.useEffect(() => {
    const activeControllers = controllers.current;
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      activeControllers.forEach((controller) => controller.abort());
    };
  }, []);

  const run = async (operation, commit) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    const controller = new AbortController(); controllers.current.add(controller);
    const credentials = credentialRef.current;
    const generation = generationRef.current;
    const isCurrent = () => mountedRef.current && generation === generationRef.current && !controller.signal.aborted && credentials === credentialRef.current;
    try {
      const value = await operation(controller.signal, credentials);
      if (isCurrent()) commit(value);
    } catch (_) {
      if (isCurrent()) setError(_.message === 'invalid command JSON' ? 'Das Kommando muss gültiges JSON sein.' : 'Die Anfrage ist fehlgeschlagen. Prüfe Zugangscode und Eingaben.');
    } finally {
      controllers.current.delete(controller);
      if (isCurrent()) { busyRef.current = false; setBusy(false); }
    }
    return undefined;
  };

  const loadPlaylists = () => run((signal, credentials) => listPlaylists(credentials.readToken, { signal }), (result) => setPlaylists(result.playlists));
  const selectPlaylist = (id) => run((signal, credentials) => getPlaylist(credentials.readToken, id, { signal }), setPlaylist);
  const loadQueue = () => run((signal, credentials) => getQueue(credentials.readToken, queueId.trim(), { signal }), setQueue);
  const submitCommand = () => run(async (signal, credentials) => {
    let command;
    try { command = JSON.parse(commandText); } catch (_) { throw new Error('invalid command JSON'); }
    return sendPlaylistCommand(credentials.writeToken, command, { signal });
  }, (result) => {
    setCommandResult(result);
    if (result.status === 'REJECTED') setError('Kommando abgelehnt: Die gewünschte Änderung wurde nicht ausgeführt.');
    else {
      const snapshot = result.result?.playlist || result.result?.queue;
      if (snapshot) { if ('playlistId' in snapshot) setPlaylist(snapshot); else setQueue(snapshot); }
    }
  });
  const libraryItems = [...(playlist?.entries || []), ...(queue?.entries || [])].map((entry) => ({ id: entry.entryId, title: entry.title, artist: '' }));

  return <Box sx={{ maxWidth: 900, mx: 'auto', p: 3 }}>
    <Typography variant="h4" gutterBottom>Phoniebox – Playlist-Pilot</Typography>
    <Typography paragraph>Lokale V1-Verwaltung. Zugangscodes bleiben nur in diesem Ansichtszustand.</Typography>
    <TextField label="Lese-Zugangscode" type="password" value={readToken} onChange={(event) => setReadToken(event.target.value)} fullWidth margin="normal" autoComplete="off" />
    <TextField label="Schreib-Zugangscode (optional, getrennt)" type="password" value={writeToken} onChange={(event) => setWriteToken(event.target.value)} fullWidth margin="normal" autoComplete="off" />
    <Button disabled={busy || !readToken} onClick={loadPlaylists} variant="contained">Playlists laden</Button>
    {playlists && <Box component="section" sx={{ mt: 2 }}><Typography variant="h6">Playlists</Typography>
      {playlists.map((item) => <Button key={item.playlistId} disabled={busy} onClick={() => selectPlaylist(item.playlistId)} sx={{ mr: 1 }}>{item.name} · Revision {item.revision}</Button>)}
    </Box>}
    <Snapshot title="Playlist" snapshot={playlist} />
    {playlist && <LibraryBrowser items={libraryItems} onSelect={(entry) => setSelectedEntryId(entry.id)} />}
    {selectedEntryId && <Typography role="status">Ausgewählt: {libraryItems.find((entry) => entry.id === selectedEntryId)?.title}</Typography>}
    <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
      <TextField label="Queue-ID" value={queueId} onChange={(event) => setQueueId(event.target.value)} />
      <Button disabled={busy || !readToken || !queueId.trim()} onClick={loadQueue}>Queue laden</Button>
    </Box>
    <Snapshot title="Queue" snapshot={queue} />
    {queue && !playlist && <LibraryBrowser items={libraryItems} onSelect={(entry) => setSelectedEntryId(entry.id)} />}
    <details style={{ marginTop: 24 }}>
      <summary>Lokaler Konfigurationsentwurf</summary>
      <Typography role="note">Nur in dieser Ansicht, nicht im Daemon gespeichert.</Typography>
      <SettingsPage initialValues={settingsDraft} onSave={setSettingsDraft} />
    </details>
    <TextField label="Erweitertes V1-Kommando (JSON)" value={commandText} onChange={(event) => setCommandText(event.target.value)} fullWidth multiline minRows={5} margin="normal" />
    <Button disabled={busy || !writeToken || !commandText.trim()} onClick={submitCommand} variant="contained">Kommando senden</Button>
    {error && <Alert role="alert" severity="error" sx={{ mt: 2 }}>{error}</Alert>}
    {commandResult && <Alert severity={commandResult.status === 'REJECTED' ? 'error' : 'success'} sx={{ mt: 2 }}>
      {commandResult.status === 'REJECTED' ? 'Kommando abgelehnt.' : 'Kommando angewendet.'} ID: {commandResult.commandId}
    </Alert>}
    <Typography variant="caption" display="block" sx={{ mt: 2 }}>Wiedergabesteuerung und Daemon-Konfiguration sind hier nicht verfügbar.</Typography>
  </Box>;
}
