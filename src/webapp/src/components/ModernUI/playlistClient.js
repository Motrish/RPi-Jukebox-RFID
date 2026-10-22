import {
  validateCommand, validateCommandResult, validateIdentifier,
  validatePlaylistSnapshot, validateQueueSnapshot,
} from '../../contracts/v1';

const CAPABILITY = /^[A-Za-z0-9_-]{43}$/;
const CURSOR = /^[A-Za-z0-9_-]{1,128}$/;
const ALLOWED_COMMANDS = new Set([
  'PLAYLIST_CREATE', 'PLAYLIST_RENAME', 'PLAYLIST_APPEND', 'PLAYLIST_REMOVE',
  'PLAYLIST_MOVE', 'PLAYLIST_DELETE', 'QUEUE_CREATE', 'QUEUE_LOAD_PLAYLIST',
  'QUEUE_APPEND', 'QUEUE_REMOVE', 'QUEUE_MOVE', 'QUEUE_SET_MODES',
  'QUEUE_SAVE_NEW_PLAYLIST', 'QUEUE_SAVE_PLAYLIST',
]);

function clientError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function input(condition) {
  if (!condition) throw clientError('invalid_input', 'Ungültige Playlist-Anfrage.');
}

function capability(value) {
  input(typeof value === 'string' && CAPABILITY.test(value));
}

function identifier(value, field) {
  try {
    return validateIdentifier(value, field);
  } catch (_) {
    throw clientError('invalid_input', 'Ungültige Playlist-Anfrage.');
  }
}

function validateList(value) {
  input(value && typeof value === 'object' && !Array.isArray(value)
    && value.contractVersion === 1 && Array.isArray(value.playlists)
    && value.playlists.length <= 50
    && (value.nextCursor === null || (typeof value.nextCursor === 'string' && CURSOR.test(value.nextCursor))));
  const keys = Object.keys(value).sort();
  input(keys.length === 3 && keys.join(',') === 'contractVersion,nextCursor,playlists');
  let previousId;
  const playlists = value.playlists.map((item) => {
    input(item && typeof item === 'object' && !Array.isArray(item)
      && Object.keys(item).sort().join(',') === 'name,playlistId,revision'
      && Number.isSafeInteger(item.revision) && item.revision >= 0);
    let summary;
    try {
      summary = validatePlaylistSnapshot({
        contractVersion: 1, playlistId: item.playlistId, name: item.name,
        revision: item.revision, entries: [],
      });
    } catch (_) {
      throw clientError('invalid_response', 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.');
    }
    const playlistId = summary.playlistId;
    if (previousId !== undefined && playlistId <= previousId) {
      throw clientError('invalid_response', 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.');
    }
    previousId = playlistId;
    return { playlistId, name: summary.name, revision: summary.revision };
  });
  if (value.nextCursor !== null) {
    identifier(value.nextCursor, 'nextCursor');
    input(playlists.length > 0 && value.nextCursor === playlists[playlists.length - 1].playlistId);
  }
  return { contractVersion: 1, playlists, nextCursor: value.nextCursor };
}

async function request(path, token, options, parse) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: 'omit', cache: 'no-store', redirect: 'error',
      headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
    });
  } catch (_) {
    throw clientError('network_error', 'Die Playlist-Anfrage ist fehlgeschlagen.');
  }
  if (!response.ok) {
    const errors = {
      401: ['unauthorized', 'Zugriff abgelaufen. Bitte erneut anmelden.'],
      403: ['forbidden', 'Keine Berechtigung für diese Playlist-Aktion.'],
      409: ['conflict', 'Die Playlist wurde zwischenzeitlich geändert.'],
      503: ['unavailable', 'Der Playlist-Dienst ist vorübergehend nicht verfügbar.'],
    };
    const [code, message] = errors[response.status] || ['http_error', 'Die Playlist-Anfrage ist fehlgeschlagen.'];
    throw clientError(code, message);
  }
  try {
    return parse(await response.json());
  } catch (_) {
    throw clientError('invalid_response', 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.');
  }
}

export async function listPlaylists(readToken, { cursor, signal } = {}) {
  capability(readToken);
  input(cursor === undefined || (typeof cursor === 'string' && CURSOR.test(cursor)));
  const query = cursor === undefined ? 'limit=50' : `limit=50&cursor=${encodeURIComponent(cursor)}`;
  return request(`/api/playlists?${query}`, readToken, { method: 'GET', signal }, validateList);
}

export async function getPlaylist(readToken, id, { signal } = {}) {
  capability(readToken);
  const requestedId = identifier(id, 'playlistId');
  return request(`/api/playlists/${encodeURIComponent(requestedId)}`, readToken, { signal }, (body) => {
    const snapshot = validatePlaylistSnapshot(body);
    if (snapshot.playlistId !== requestedId) throw clientError('invalid_response', 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.');
    return snapshot;
  });
}

export async function getQueue(readToken, id, { signal } = {}) {
  capability(readToken);
  const requestedId = identifier(id, 'queueId');
  return request(`/api/queues/${encodeURIComponent(requestedId)}`, readToken, { signal }, (body) => {
    const snapshot = validateQueueSnapshot(body);
    if (snapshot.queueId !== requestedId) throw clientError('invalid_response', 'Der Playlist-Dienst hat eine ungültige Antwort geliefert.');
    return snapshot;
  });
}

export async function sendPlaylistCommand(writeToken, command, { signal } = {}) {
  capability(writeToken);
  let validated;
  try {
    validated = validateCommand(command);
  } catch (_) {
    throw clientError('invalid_input', 'Ungültiger Playlist-Befehl.');
  }
  input(ALLOWED_COMMANDS.has(validated.action));
  return request('/api/playlist-commands', writeToken, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(validated),
  }, (body) => {
    const validatedResult = validateCommandResult(body);
    input(validatedResult.commandId === validated.commandId && validatedResult.action === validated.action);
    return validatedResult;
  });
}
