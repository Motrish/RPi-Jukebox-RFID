const UNSAFE_TOKEN_CHARACTER = /[^A-Za-z0-9_-]/;
const PAGE_SIZE = 20;

export const defaultLibraryPage = Object.freeze({ items: [], nextCursor: null });

function libraryError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function hasOnlyKeys(value, keys) {
  return value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function isToken(value) {
  return typeof value === 'string'
    && value.length >= 1
    && value.length <= 128
    && !UNSAFE_TOKEN_CHARACTER.test(value);
}

function isCode(value) {
  return typeof value === 'string'
    && value.length === 43
    && !UNSAFE_TOKEN_CHARACTER.test(value);
}

function validatePage(value) {
  if (!hasOnlyKeys(value, ['items', 'nextCursor'])
    || !Array.isArray(value.items)
    || value.items.length > PAGE_SIZE
    || !(value.nextCursor === null || isToken(value.nextCursor))) {
    throw libraryError('INVALID_RESPONSE', 'Die Bibliotheksantwort ist ungültig.');
  }

  const seen = new Set();
  value.items.forEach((item) => {
    if (!hasOnlyKeys(item, ['libraryId', 'displayName', 'availability'])
      || !isToken(item.libraryId)
      || typeof item.displayName !== 'string'
      || item.displayName.trim().length === 0
      || !['AVAILABLE', 'MISSING', 'UNKNOWN'].includes(item.availability)
      || seen.has(item.libraryId)) {
      throw libraryError('INVALID_RESPONSE', 'Die Bibliotheksantwort ist ungültig.');
    }
    seen.add(item.libraryId);
  });

  const last = value.items[value.items.length - 1];
  if (value.nextCursor !== null && (!last || value.nextCursor !== last.libraryId)) {
    throw libraryError('INVALID_RESPONSE', 'Die Bibliotheksantwort ist ungültig.');
  }

  return {
    items: value.items.map(({ libraryId, displayName, availability }) => ({
      libraryId,
      displayName,
      availability,
    })),
    nextCursor: value.nextCursor,
  };
}

export async function fetchLibraryPage(code, cursor, signal) {
  if (!isCode(code)) {
    throw libraryError('INVALID_CREDENTIAL', 'Der Zugangscode ist ungültig.');
  }
  if (cursor !== undefined && cursor !== null && !isToken(cursor)) {
    throw libraryError('INVALID_CURSOR', 'Die angeforderte Seite ist ungültig.');
  }

  const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (cursor !== undefined && cursor !== null) query.set('cursor', cursor);

  let response;
  try {
    response = await fetch(`/api/library/media?${query.toString()}`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${code}` },
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      signal,
    });
  } catch (_error) {
    throw libraryError('NETWORK_ERROR', 'Die Bibliothek ist nicht erreichbar.');
  }

  if (response.status === 401) {
    throw libraryError('UNAUTHORIZED', 'Der Zugangscode ist abgelaufen. Bitte erneut freigeben.');
  }
  if (response.status === 503) {
    throw libraryError('SERVICE_UNAVAILABLE', 'Die Bibliothek ist vorübergehend nicht erreichbar.');
  }
  if (!response.ok) {
    throw libraryError('REQUEST_FAILED', 'Die Bibliothek konnte nicht geladen werden.');
  }

  let body;
  try {
    body = await response.json();
  } catch (_error) {
    throw libraryError('INVALID_RESPONSE', 'Die Bibliotheksantwort ist ungültig.');
  }
  return validatePage(body);
}

export default defaultLibraryPage;
