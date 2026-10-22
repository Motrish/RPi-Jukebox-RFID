import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../../App';
import * as client from './playlistClient';

jest.mock('./playlistClient', () => ({
  listPlaylists: jest.fn(), getPlaylist: jest.fn(), getQueue: jest.fn(), sendPlaylistCommand: jest.fn(),
}));

const token = 'a'.repeat(43);

beforeEach(() => {
  window.location.hash = '#/modern-ui';
  client.listPlaylists.mockReset();
  client.getPlaylist.mockReset();
  client.getQueue.mockReset();
  client.sendPlaylistCommand.mockReset();
});

test('boots the isolated pilot without fetching until explicitly requested', async () => {
  render(<App />);
  expect(await screen.findByText('Phoniebox – Playlist-Pilot')).toBeInTheDocument();
  expect(client.listPlaylists).not.toHaveBeenCalled();
  expect(client.getPlaylist).not.toHaveBeenCalled();
  expect(client.getQueue).not.toHaveBeenCalled();
  expect(client.sendPlaylistCommand).not.toHaveBeenCalled();
});

test('searches loaded snapshot entries and selecting one does not start playback', async () => {
  client.listPlaylists.mockResolvedValue({ playlists: [{ playlistId: 'p1', name: 'Mix', revision: 7 }] });
  client.getPlaylist.mockResolvedValue({ playlistId: 'p1', name: 'Mix', revision: 7, entries: [{ entryId: 'e1', title: 'Moonlight' }, { entryId: 'e2', title: 'Sunrise', url: 'https://invalid.example' }] });
  render(<App />);
  fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  fireEvent.click(await screen.findByText('Mix · Revision 7'));
  expect(await screen.findByText('Playlist: Mix · Revision 7')).toBeInTheDocument();
  const search = screen.getByLabelText('Search library');
  fireEvent.change(search, { target: { value: 'moon' } });
  expect(screen.getByText('Moonlight')).toBeInTheDocument();
  expect(screen.queryByText('Sunrise')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Moonlight'));
  expect(screen.getByText('Ausgewählt: Moonlight')).toBeInTheDocument();
  expect(client.sendPlaylistCommand).not.toHaveBeenCalled();
});

test('exposes local settings as an explicitly view-only draft', async () => {
  render(<App />);
  fireEvent.click(screen.getByText('Lokaler Konfigurationsentwurf'));
  expect(screen.getByText('Nur in dieser Ansicht, nicht im Daemon gespeichert.')).toBeInTheDocument();
  const enabled = screen.getByLabelText('Enable Local Playback HTTP');
  fireEvent.click(enabled);
  const path = screen.getByLabelText('Bearer Token Path');
  expect(path).toBeEnabled();
  fireEvent.click(screen.getByText('Save Settings'));
  expect(await screen.findByText('Bearer token path is required when HTTP is enabled')).toBeInTheDocument();
  fireEvent.change(path, { target: { value: '/run/local-token' } });
  fireEvent.change(screen.getByLabelText('Port'), { target: { value: '65536' } });
  fireEvent.click(screen.getByText('Save Settings'));
  expect(await screen.findByText('Port must be an integer from 1 to 65535')).toBeInTheDocument();
});

test('uses the read token for reads and the separate write token for commands', async () => {
  client.listPlaylists.mockResolvedValue({ playlists: [] });
  client.sendPlaylistCommand.mockResolvedValue({ commandId: 'cmd_1', action: 'QUEUE_CREATE', status: 'REJECTED' });
  render(<App />);
  fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
  fireEvent.change(screen.getByLabelText('Schreib-Zugangscode (optional, getrennt)'), { target: { value: `${token}b` } });
  fireEvent.click(screen.getByText('Playlists laden'));
  await waitFor(() => expect(client.listPlaylists).toHaveBeenCalledWith(token, expect.any(Object)));
  fireEvent.change(screen.getByLabelText('Erweitertes V1-Kommando (JSON)'), {
    target: { value: '{"contractVersion":1,"commandId":"cmd_1","action":"QUEUE_CREATE","items":[]}' },
  });
  fireEvent.click(screen.getByText('Kommando senden'));
  await waitFor(() => expect(client.sendPlaylistCommand).toHaveBeenCalledWith(`${token}b`, expect.objectContaining({ commandId: 'cmd_1' }), expect.any(Object)));
  expect(await screen.findByText('Kommando abgelehnt: Die gewünschte Änderung wurde nicht ausgeführt.')).toBeInTheDocument();
});

test('starts playlist pagination with an undefined cursor', async () => {
  client.listPlaylists.mockImplementation((_token, { cursor }) => {
    if (cursor !== undefined && typeof cursor !== 'string') throw new TypeError('cursor must be a string or undefined');
    return Promise.resolve({ playlists: [], nextCursor: null });
  });
  render(<App />);
  fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  await waitFor(() => expect(client.listPlaylists).toHaveBeenCalledWith(token, expect.objectContaining({ cursor: undefined })));
  expect(await screen.findByText('Playlists')).toBeInTheDocument();
});

test('requests the first playlist page through the real client without a cursor', async () => {
  const realClient = jest.requireActual('./playlistClient');
  const originalFetch = global.fetch;
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ contractVersion: 1, playlists: [], nextCursor: null }),
  });
  global.fetch = fetchMock;
  client.listPlaylists.mockImplementation(realClient.listPlaylists);

  try {
    render(<App />);
    fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
    fireEvent.click(screen.getByText('Playlists laden'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith('/api/playlists?limit=50', expect.objectContaining({
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      headers: { Authorization: `Bearer ${token}` },
    }));
    expect(await screen.findByText('Playlists')).toBeInTheDocument();
  } finally {
    global.fetch = originalFetch;
  }
});

test('loads playlist pages once and hides the action when there is no next cursor', async () => {
  client.listPlaylists.mockResolvedValueOnce({
    playlists: [{ playlistId: 'p1', name: 'Erste Seite', revision: 1 }], nextCursor: 'p1',
  });
  let resolveNextPage;
  client.listPlaylists.mockReturnValueOnce(new Promise((resolve) => { resolveNextPage = resolve; }));
  render(<App />);
  fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  expect(await screen.findByText('Erste Seite · Revision 1')).toBeInTheDocument();

  const more = screen.getByRole('button', { name: 'Mehr laden' });
  fireEvent.click(more);
  fireEvent.click(more);
  await waitFor(() => expect(client.listPlaylists).toHaveBeenCalledTimes(2));
  expect(client.listPlaylists).toHaveBeenLastCalledWith(token, expect.objectContaining({ cursor: 'p1' }));
  expect(more).toBeDisabled();
  await act(async () => resolveNextPage({
    playlists: [{ playlistId: 'p2', name: 'Zweite Seite', revision: 2 }], nextCursor: null,
  }));
  expect(await screen.findByText('Zweite Seite · Revision 2')).toBeInTheDocument();
  expect(screen.getByText('Erste Seite · Revision 1')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Mehr laden' })).not.toBeInTheDocument();
  expect(client.listPlaylists).toHaveBeenCalledTimes(2);
});

test('guards a pending command against double submit', async () => {
  let resolveCommand;
  client.sendPlaylistCommand.mockReturnValue(new Promise((resolve) => { resolveCommand = resolve; }));
  render(<App />);
  fireEvent.change(screen.getByLabelText('Schreib-Zugangscode (optional, getrennt)'), { target: { value: token } });
  fireEvent.change(screen.getByLabelText('Erweitertes V1-Kommando (JSON)'), {
    target: { value: '{"contractVersion":1,"commandId":"cmd_2","action":"QUEUE_CREATE","items":[]}' },
  });
  const button = screen.getByText('Kommando senden');
  fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(client.sendPlaylistCommand).toHaveBeenCalledTimes(1));
  await act(async () => {
    resolveCommand({ commandId: 'cmd_2', action: 'QUEUE_CREATE', status: 'APPLIED', result: { queue: { queueId: 'q', revision: 0, entries: [] } } });
  });
  expect(await screen.findByText('Kommando angewendet. ID: cmd_2')).toBeInTheDocument();
});

test('does not commit a delayed read after the read token changes', async () => {
  let resolveRead;
  client.listPlaylists.mockReturnValue(new Promise((resolve) => { resolveRead = resolve; }));
  render(<App />);
  const field = screen.getByLabelText('Lese-Zugangscode');
  fireEvent.change(field, { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  await waitFor(() => expect(client.listPlaylists).toHaveBeenCalledTimes(1));
  fireEvent.change(field, { target: { value: `${token}b` } });
  await act(async () => resolveRead({ playlists: [{ playlistId: 'old', name: 'alte Playlist', revision: 1 }] }));
  expect(screen.queryByText('alte Playlist · Revision 1')).not.toBeInTheDocument();
});

test('does not commit a delayed command after the write token changes', async () => {
  let resolveCommand;
  client.sendPlaylistCommand.mockReturnValue(new Promise((resolve) => { resolveCommand = resolve; }));
  render(<App />);
  const field = screen.getByLabelText('Schreib-Zugangscode (optional, getrennt)');
  fireEvent.change(field, { target: { value: token } });
  fireEvent.change(screen.getByLabelText('Erweitertes V1-Kommando (JSON)'), {
    target: { value: '{"contractVersion":1,"commandId":"stale","action":"QUEUE_CREATE","items":[]}' },
  });
  fireEvent.click(screen.getByText('Kommando senden'));
  await waitFor(() => expect(client.sendPlaylistCommand).toHaveBeenCalledTimes(1));
  fireEvent.change(field, { target: { value: `${token}b` } });
  await act(async () => resolveCommand({ commandId: 'stale', status: 'APPLIED' }));
  expect(screen.queryByText('Kommando angewendet. ID: stale')).not.toBeInTheDocument();
});

test('clears the selected library entry when credentials change', async () => {
  client.listPlaylists.mockResolvedValue({ playlists: [{ playlistId: 'p1', name: 'Mix', revision: 7 }] });
  client.getPlaylist.mockResolvedValue({ playlistId: 'p1', name: 'Mix', revision: 7, entries: [{ entryId: 'e1', title: 'Moonlight' }] });
  render(<App />);
  const readToken = screen.getByLabelText('Lese-Zugangscode');
  fireEvent.change(readToken, { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  fireEvent.click(await screen.findByText('Mix · Revision 7'));
  fireEvent.click(await screen.findByText('Moonlight'));
  expect(screen.getByText('Ausgewählt: Moonlight')).toBeInTheDocument();

  fireEvent.change(readToken, { target: { value: '' } });
  expect(screen.queryByText('Ausgewählt: Moonlight')).not.toBeInTheDocument();
});

test('does not update state when a request resolves after unmount', async () => {
  let resolveRead;
  client.listPlaylists.mockReturnValue(new Promise((resolve) => { resolveRead = resolve; }));
  const view = render(<App />);
  fireEvent.change(screen.getByLabelText('Lese-Zugangscode'), { target: { value: token } });
  fireEvent.click(screen.getByText('Playlists laden'));
  await waitFor(() => expect(client.listPlaylists).toHaveBeenCalledTimes(1));
  view.unmount();
  await act(async () => resolveRead({ playlists: [] }));
});
