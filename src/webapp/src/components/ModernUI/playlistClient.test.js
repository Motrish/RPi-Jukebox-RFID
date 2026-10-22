import {
  getPlaylist, getQueue, listPlaylists, sendPlaylistCommand,
} from './playlistClient';

const readToken = 'a'.repeat(43);
const writeToken = 'b'.repeat(43);
const playlist = { contractVersion: 1, playlistId: 'pl_1', name: 'Mix', revision: 2, entries: [] };
const queue = {
  contractVersion: 1, queueId: 'q_1', revision: 2, sourcePlaylistId: null,
  sourcePlaylistRevision: null, entries: [], currentEntryId: null,
  repeatMode: 'OFF', shuffleMode: 'OFF',
};
const command = { contractVersion: 1, commandId: 'cmd_1', action: 'PLAYLIST_CREATE', name: 'Mix', items: [] };
const result = {
  contractVersion: 1, commandId: 'cmd_1', action: 'PLAYLIST_CREATE', status: 'APPLIED', result: { playlist },
};

function reply(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeEach(() => { global.fetch = jest.fn(); });
afterEach(() => { delete global.fetch; });

it('lists with bounded cursor and read capability in a header only', async () => {
  global.fetch.mockResolvedValue(reply({
    contractVersion: 1, playlists: [{ playlistId: 'pl_1', name: 'Mix', revision: 2 }], nextCursor: null,
  }));
  await expect(listPlaylists(readToken, { cursor: 'opaque' })).resolves.toMatchObject({ playlists: [{ playlistId: 'pl_1' }] });
  expect(global.fetch).toHaveBeenCalledWith('/api/playlists?limit=50&cursor=opaque', expect.objectContaining({
    method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error',
    headers: { Authorization: `Bearer ${readToken}` },
  }));
});

it('rejects playlist lists that are not in strictly ascending id order', async () => {
  global.fetch.mockResolvedValueOnce(reply({
    contractVersion: 1,
    playlists: [
      { playlistId: 'pl_2', name: 'Second', revision: 1 },
      { playlistId: 'pl_1', name: 'First', revision: 1 },
    ],
    nextCursor: null,
  }));
  await expect(listPlaylists(readToken)).rejects.toMatchObject({ code: 'invalid_response' });
});

it('uses V1 whitespace rules for playlist names and keeps summary bounds strict', async () => {
  global.fetch.mockResolvedValueOnce(reply({
    contractVersion: 1, playlists: [{ playlistId: 'pl_1', name: '\u001c', revision: 2 }], nextCursor: null,
  }));
  await expect(listPlaylists(readToken)).rejects.toMatchObject({ code: 'invalid_response' });

  global.fetch.mockResolvedValueOnce(reply({
    contractVersion: 1, playlists: [{ playlistId: 'pl_1', name: '\ufeff', revision: 2 }], nextCursor: null,
  }));
  await expect(listPlaylists(readToken)).resolves.toMatchObject({ playlists: [{ name: '\ufeff' }] });

  global.fetch.mockResolvedValueOnce(reply({
    contractVersion: 1,
    playlists: [{ playlistId: 'bad id', name: 'a'.repeat(257), revision: 2 }], nextCursor: null,
  }));
  await expect(listPlaylists(readToken)).rejects.toMatchObject({ code: 'invalid_response' });
});

it('validates playlist and queue snapshots and encodes opaque ids', async () => {
  global.fetch.mockResolvedValueOnce(reply(playlist));
  await expect(getPlaylist(readToken, 'pl_1')).resolves.toEqual(playlist);
  expect(global.fetch.mock.calls[0][0]).toBe('/api/playlists/pl_1');
  global.fetch.mockResolvedValueOnce(reply(queue));
  await expect(getQueue(readToken, 'q_1')).resolves.toEqual(queue);
});

it('rejects snapshots whose validated identity differs from the requested id', async () => {
  global.fetch.mockResolvedValueOnce(reply({ ...playlist, playlistId: 'pl_2' }));
  await expect(getPlaylist(readToken, 'pl_1')).rejects.toMatchObject({
    code: 'invalid_response', message: 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.',
  });

  global.fetch.mockResolvedValueOnce(reply({ ...queue, queueId: 'q_2' }));
  await expect(getQueue(readToken, 'q_1')).rejects.toMatchObject({
    code: 'invalid_response', message: 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.',
  });
});

it('does not fetch for malformed capabilities, ids, cursors, or forbidden commands', async () => {
  await expect(listPlaylists('short')).rejects.toMatchObject({ code: 'invalid_input' });
  await expect(getPlaylist(readToken, 'bad id')).rejects.toMatchObject({ code: 'invalid_input' });
  await expect(listPlaylists(readToken, { cursor: 'bad cursor' })).rejects.toMatchObject({ code: 'invalid_input' });
  await expect(sendPlaylistCommand(writeToken, { ...command, action: 'QUEUE_SET_CURRENT' })).rejects.toMatchObject({ code: 'invalid_input' });
  expect(global.fetch).not.toHaveBeenCalled();
});

it('sends mutations only with the write capability and never retries', async () => {
  global.fetch.mockResolvedValueOnce(reply(result));
  await expect(sendPlaylistCommand(writeToken, command)).resolves.toEqual(result);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledWith('/api/playlist-commands', expect.objectContaining({
    method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${writeToken}` },
    body: JSON.stringify(command),
  }));
});

it('rejects malformed list/result response and mismatched command identity', async () => {
  global.fetch.mockResolvedValueOnce(reply({ contractVersion: 1, playlists: [], nextCursor: [] }));
  await expect(listPlaylists(readToken)).rejects.toMatchObject({ code: 'invalid_response' });
  global.fetch.mockResolvedValueOnce(reply({ ...result, commandId: 'other' }));
  await expect(sendPlaylistCommand(writeToken, command)).rejects.toMatchObject({ code: 'invalid_response' });
});

it.each([[401, 'unauthorized'], [403, 'forbidden'], [409, 'conflict'], [503, 'unavailable']])(
  'maps HTTP %i to a safe error', async (status, code) => {
    global.fetch.mockResolvedValue(reply({ secret: readToken }, status));
    await expect(getQueue(readToken, 'q_1')).rejects.toMatchObject({ code });
  },
);
