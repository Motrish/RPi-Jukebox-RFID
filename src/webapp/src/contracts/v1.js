const MAX_INTEGER = Number.MAX_SAFE_INTEGER;
const MAX_ENTRIES = 10000;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;
const SPOTIFY_TRACK_PATTERN = /^spotify:track:[A-Za-z0-9]{22}$/;
const PYTHON_WHITESPACE = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u;

const COMMAND_FIELDS = new Map([
  ['PLAYLIST_CREATE', ['name', 'items']],
  ['PLAYLIST_RENAME', ['playlistId', 'expectedRevision', 'name']],
  ['PLAYLIST_APPEND', ['playlistId', 'expectedRevision', 'items']],
  ['PLAYLIST_REMOVE', ['playlistId', 'expectedRevision', 'entryId']],
  ['PLAYLIST_MOVE', ['playlistId', 'expectedRevision', 'entryId', 'toPosition']],
  ['PLAYLIST_DELETE', ['playlistId', 'expectedRevision']],
  ['QUEUE_CREATE', ['items']],
  ['QUEUE_LOAD_PLAYLIST', ['queueId', 'expectedQueueRevision', 'playlistId', 'expectedPlaylistRevision']],
  ['QUEUE_APPEND', ['queueId', 'expectedRevision', 'items']],
  ['QUEUE_REMOVE', ['queueId', 'expectedRevision', 'entryId']],
  ['QUEUE_MOVE', ['queueId', 'expectedRevision', 'entryId', 'toPosition']],
  ['QUEUE_SET_MODES', ['queueId', 'expectedRevision', 'repeatMode', 'shuffleMode']],
  ['QUEUE_SET_CURRENT', ['queueId', 'expectedRevision', 'entryId']],
  ['QUEUE_SAVE_NEW_PLAYLIST', ['queueId', 'expectedQueueRevision', 'name']],
  ['QUEUE_SAVE_PLAYLIST', ['queueId', 'expectedQueueRevision', 'playlistId', 'expectedPlaylistRevision']],
]);

const RESULT_KIND = new Map([
  ['PLAYLIST_CREATE', 'playlist'], ['PLAYLIST_RENAME', 'playlist'],
  ['PLAYLIST_APPEND', 'playlist'], ['PLAYLIST_REMOVE', 'playlist'],
  ['PLAYLIST_MOVE', 'playlist'], ['QUEUE_SAVE_NEW_PLAYLIST', 'playlist'],
  ['QUEUE_SAVE_PLAYLIST', 'playlist'], ['QUEUE_CREATE', 'queue'],
  ['QUEUE_LOAD_PLAYLIST', 'queue'], ['QUEUE_APPEND', 'queue'],
  ['QUEUE_REMOVE', 'queue'], ['QUEUE_MOVE', 'queue'],
  ['QUEUE_SET_MODES', 'queue'], ['QUEUE_SET_CURRENT', 'queue'],
]);

const ERROR_DETAILS = new Map([
  ['VALIDATION_ERROR', ['field', 'reason']],
  ['UNSUPPORTED_VERSION', ['supportedVersions']],
  ['NOT_FOUND', ['objectType', 'objectId']],
  ['COMMAND_NOT_FOUND', ['commandId']],
  ['REVISION_CONFLICT', ['conflicts']],
  ['COMMAND_ID_REUSED', ['commandId']],
  ['POSITION_OUT_OF_RANGE', ['entryId', 'minimum', 'maximum']],
  ['LIMIT_EXCEEDED', ['field', 'limit']],
  ['ACTIVE_ENTRY_REQUIRES_CONTROLLER', ['queueId', 'currentEntryId']],
  ['REVISION_EXHAUSTED', ['objectType', 'objectId']],
  ['STORE_BUSY', ['operation']],
  ['STORE_UNAVAILABLE', ['operation']],
  ['INTERNAL_ERROR', ['diagnosticId']],
]);

const RETRYABLE_ERRORS = new Set(['STORE_BUSY', 'STORE_UNAVAILABLE']);

export class ContractValidationError extends Error {
  constructor(field, reason, code = 'VALIDATION_ERROR', details) {
    super(`${code}: ${field} (${reason})`);
    this.name = 'ContractValidationError';
    this.code = code;
    this.field = field;
    this.reason = reason;
    this.error = {
      code,
      message: 'The supplied contract value is invalid.',
      retryable: false,
      operation: 'CONTRACT_VALIDATION',
      details: details || (code === 'UNSUPPORTED_VERSION'
        ? { supportedVersions: [1] }
        : { field, reason }),
    };
  }
}

function fail(field, reason, code = 'VALIDATION_ERROR', details) {
  throw new ContractValidationError(field, reason, code, details);
}

function object(value, field) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
      || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)) {
    fail(field, 'invalid_type');
  }
  if (Object.keys(value).some((key) => typeof key !== 'string')) {
    fail(field, 'invalid_field_name');
  }
  return value;
}

function fields(value, expected, field) {
  const actual = Object.keys(value);
  if (actual.some((key) => !expected.includes(key))) {
    fail(field, 'unknown_field');
  }
  const missing = expected.filter((key) => !Object.prototype.hasOwnProperty.call(value, key)).sort();
  if (missing.length) {
    fail(`${field}.${missing[0]}`, 'missing_field');
  }
}

function required(value, key, field) {
  if (!Object.prototype.hasOwnProperty.call(value, key)) {
    fail(`${field}.${key}`, 'missing_field');
  }
  return value[key];
}

function fullMatch(pattern, value) {
  const match = pattern.exec(value);
  return match !== null && match[0] === value;
}

function token(value, field) {
  if (typeof value !== 'string' || !fullMatch(TOKEN_PATTERN, value)) {
    fail(field, 'invalid_identifier');
  }
  return value;
}

function integer(value, field) {
  if (!Number.isSafeInteger(value) || value < 0 || value > MAX_INTEGER) {
    fail(field, 'invalid_integer');
  }
  return value === 0 ? 0 : value;
}

function version(value) {
  if (!Number.isInteger(value)) {
    fail('document.contractVersion', 'invalid_version_type');
  }
  if (!Number.isSafeInteger(value)) {
    fail('document.contractVersion', 'invalid_version_type');
  }
  if (value !== 1) {
    fail('document.contractVersion', 'unsupported_version', 'UNSUPPORTED_VERSION');
  }
  return value;
}

function pythonWhitespaceOnly(value) {
  return value.length > 0 && !Array.from(value).some((character) => !PYTHON_WHITESPACE.test(character));
}

function text(value, field, maximum, reason) {
  if (typeof value !== 'string' || Array.from(value).length < 1
      || Array.from(value).length > maximum || pythonWhitespaceOnly(value)) {
    fail(field, reason);
  }
  return value;
}

function name(value, field) {
  return text(value, field, 256, 'invalid_name');
}

function title(value, field) {
  return text(value, field, 1024, 'invalid_title');
}

function message(value, field) {
  return text(value, field, 1024, 'invalid_message');
}

function safeText(value, field) {
  return text(value, field, 256, 'invalid_text');
}

function enumValue(value, field, allowed) {
  if (typeof value !== 'string' || !allowed.has(value)) {
    fail(field, 'invalid_enum');
  }
  return value;
}

function denseArray(value, field) {
  if (!Array.isArray(value)) {
    fail(field, 'invalid_type');
  }
  for (let index = 0; index < value.length; index += 1) {
    if (!Object.prototype.hasOwnProperty.call(value, index)) {
      fail(`${field}[${index}]`, 'missing_item');
    }
  }
  return value;
}

function validateMediaRef(value, field = 'mediaRef') {
  const input = object(value, field);
  const kind = required(input, 'kind', field);
  if (typeof kind !== 'string') {
    fail(`${field}.kind`, 'invalid_type');
  }
  if (kind === 'LOCAL') {
    fields(input, ['kind', 'libraryId'], field);
    return { kind: 'LOCAL', libraryId: token(required(input, 'libraryId', field), `${field}.libraryId`) };
  }
  if (kind === 'SPOTIFY') {
    fields(input, ['kind', 'uri'], field);
    const uri = required(input, 'uri', field);
    if (typeof uri !== 'string' || !fullMatch(SPOTIFY_TRACK_PATTERN, uri)) {
      fail(`${field}.uri`, 'invalid_spotify_track_uri');
    }
    return { kind: 'SPOTIFY', uri };
  }
  fail(`${field}.kind`, 'unknown_source_kind');
}

function validateIdentifier(value, field = 'identifier') {
  return token(value, field);
}

function validatePlaylistEntry(value, expectedPosition = null, field = 'entry') {
  const input = object(value, field);
  fields(input, ['entryId', 'mediaRef', 'title', 'position'], field);
  const entryId = token(required(input, 'entryId', field), `${field}.entryId`);
  const mediaRef = validateMediaRef(required(input, 'mediaRef', field), `${field}.mediaRef`);
  const entryTitle = title(required(input, 'title', field), `${field}.title`);
  const position = integer(required(input, 'position', field), `${field}.position`);
  if (expectedPosition !== null && position !== expectedPosition) {
    fail(`${field}.position`, 'position_mismatch');
  }
  return { entryId, mediaRef, title: entryTitle, position };
}

function validateQueueEntry(value, expectedPosition = null, field = 'entry') {
  const input = object(value, field);
  fields(input, ['entryId', 'sourceEntryId', 'mediaRef', 'title', 'position'], field);
  const entryId = token(required(input, 'entryId', field), `${field}.entryId`);
  let sourceEntryId = required(input, 'sourceEntryId', field);
  if (sourceEntryId !== null) {
    sourceEntryId = token(sourceEntryId, `${field}.sourceEntryId`);
  }
  const mediaRef = validateMediaRef(required(input, 'mediaRef', field), `${field}.mediaRef`);
  const entryTitle = title(required(input, 'title', field), `${field}.title`);
  const position = integer(required(input, 'position', field), `${field}.position`);
  if (expectedPosition !== null && position !== expectedPosition) {
    fail(`${field}.position`, 'position_mismatch');
  }
  return { entryId, sourceEntryId, mediaRef, title: entryTitle, position };
}

function entryList(value, isQueue, field) {
  denseArray(value, field);
  if (value.length > MAX_ENTRIES) {
    fail(field, 'limit_exceeded', 'LIMIT_EXCEEDED', { field, limit: MAX_ENTRIES });
  }
  const result = [];
  const seen = new Set();
  value.forEach((raw, index) => {
    const itemField = `${field}[${index}]`;
    const parsed = isQueue
      ? validateQueueEntry(raw, index, itemField)
      : validatePlaylistEntry(raw, index, itemField);
    if (seen.has(parsed.entryId)) {
      fail(`${itemField}.entryId`, 'duplicate_entry_id');
    }
    seen.add(parsed.entryId);
    result.push(parsed);
  });
  return result;
}

function validatePlaylistSnapshot(value) {
  const input = object(value, 'playlist');
  fields(input, ['contractVersion', 'playlistId', 'name', 'revision', 'entries'], 'playlist');
  const contractVersion = version(required(input, 'contractVersion', 'document'));
  const playlistId = token(required(input, 'playlistId', 'playlist'), 'playlist.playlistId');
  const playlistName = name(required(input, 'name', 'playlist'), 'playlist.name');
  const revision = integer(required(input, 'revision', 'playlist'), 'playlist.revision');
  const entries = entryList(required(input, 'entries', 'playlist'), false, 'playlist.entries');
  return { contractVersion, playlistId, name: playlistName, revision, entries };
}

function validateQueueSnapshot(value) {
  const input = object(value, 'queue');
  fields(input, [
    'contractVersion', 'queueId', 'revision', 'sourcePlaylistId', 'sourcePlaylistRevision',
    'entries', 'currentEntryId', 'repeatMode', 'shuffleMode',
  ], 'queue');
  const contractVersion = version(required(input, 'contractVersion', 'document'));
  const queueId = token(required(input, 'queueId', 'queue'), 'queue.queueId');
  const revision = integer(required(input, 'revision', 'queue'), 'queue.revision');
  let sourcePlaylistId = required(input, 'sourcePlaylistId', 'queue');
  let sourcePlaylistRevision = required(input, 'sourcePlaylistRevision', 'queue');
  if (sourcePlaylistId === null && sourcePlaylistRevision === null) {
    // This queue has no playlist attribution.
  } else if (sourcePlaylistId === null || sourcePlaylistRevision === null) {
    fail('queue.sourcePlaylistId', 'source_fields_must_be_paired');
  } else {
    sourcePlaylistId = token(sourcePlaylistId, 'queue.sourcePlaylistId');
    sourcePlaylistRevision = integer(sourcePlaylistRevision, 'queue.sourcePlaylistRevision');
  }
  const entries = entryList(required(input, 'entries', 'queue'), true, 'queue.entries');
  let currentEntryId = required(input, 'currentEntryId', 'queue');
  if (currentEntryId !== null) {
    currentEntryId = token(currentEntryId, 'queue.currentEntryId');
    if (!entries.some((entry) => entry.entryId === currentEntryId)) {
      fail('queue.currentEntryId', 'selection_not_found');
    }
  }
  const repeatMode = enumValue(required(input, 'repeatMode', 'queue'), 'queue.repeatMode', new Set(['OFF', 'ALL', 'ONE']));
  const shuffleMode = enumValue(required(input, 'shuffleMode', 'queue'), 'queue.shuffleMode', new Set(['OFF', 'ON']));
  return {
    contractVersion, queueId, revision, sourcePlaylistId, sourcePlaylistRevision,
    entries, currentEntryId, repeatMode, shuffleMode,
  };
}

function commandItems(value, field) {
  denseArray(value, field);
  if (value.length > MAX_ENTRIES) {
    fail(field, 'limit_exceeded', 'LIMIT_EXCEEDED', { field, limit: MAX_ENTRIES });
  }
  return value.map((raw, index) => {
    const itemField = `${field}[${index}]`;
    const input = object(raw, itemField);
    fields(input, ['mediaRef', 'title'], itemField);
    return {
      mediaRef: validateMediaRef(required(input, 'mediaRef', itemField), `${itemField}.mediaRef`),
      title: title(required(input, 'title', itemField), `${itemField}.title`),
    };
  });
}

function validateCommand(value) {
  const input = object(value, 'command');
  const action = required(input, 'action', 'command');
  if (typeof action !== 'string' || !COMMAND_FIELDS.has(action)) {
    fail('command.action', 'unknown_action');
  }
  const commandFields = COMMAND_FIELDS.get(action);
  fields(input, ['contractVersion', 'commandId', 'action', ...commandFields], 'command');
  const result = {
    contractVersion: version(required(input, 'contractVersion', 'document')),
    commandId: token(required(input, 'commandId', 'command'), 'command.commandId'),
    action,
  };
  commandFields.forEach((fieldName) => {
    const raw = required(input, fieldName, 'command');
    const field = `command.${fieldName}`;
    if (['playlistId', 'queueId', 'entryId'].includes(fieldName)) {
      result[fieldName] = fieldName === 'entryId' && action === 'QUEUE_SET_CURRENT' && raw === null
        ? null
        : token(raw, field);
    } else if (['expectedRevision', 'expectedQueueRevision', 'expectedPlaylistRevision'].includes(fieldName)) {
      result[fieldName] = integer(raw, field);
    } else if (fieldName === 'toPosition') {
      result[fieldName] = integer(raw, field);
    } else if (fieldName === 'name') {
      result[fieldName] = name(raw, field);
    } else if (fieldName === 'items') {
      result[fieldName] = commandItems(raw, field);
    } else if (fieldName === 'repeatMode') {
      result[fieldName] = enumValue(raw, field, new Set(['OFF', 'ALL', 'ONE']));
    } else if (fieldName === 'shuffleMode') {
      result[fieldName] = enumValue(raw, field, new Set(['OFF', 'ON']));
    }
  });
  return result;
}

function validateErrorDetails(code, value) {
  const input = object(value, 'error.details');
  fields(input, ERROR_DETAILS.get(code), 'error.details');
  if (code === 'VALIDATION_ERROR') {
    return {
      field: safeText(required(input, 'field', 'details'), 'details.field'),
      reason: token(required(input, 'reason', 'details'), 'details.reason'),
    };
  }
  if (code === 'UNSUPPORTED_VERSION') {
    const versions = denseArray(required(input, 'supportedVersions', 'details'), 'details.supportedVersions');
    if (versions.length === 0
        || versions.some((item) => !Number.isSafeInteger(item) || item < 1)) {
      fail('details.supportedVersions', 'invalid_versions');
    }
    return { supportedVersions: [...versions] };
  }
  if (code === 'NOT_FOUND' || code === 'REVISION_EXHAUSTED') {
    return {
      objectType: token(required(input, 'objectType', 'details'), 'details.objectType'),
      objectId: token(required(input, 'objectId', 'details'), 'details.objectId'),
    };
  }
  if (code === 'COMMAND_NOT_FOUND' || code === 'COMMAND_ID_REUSED') {
    return { commandId: token(required(input, 'commandId', 'details'), 'details.commandId') };
  }
  if (code === 'REVISION_CONFLICT') {
    const conflicts = denseArray(required(input, 'conflicts', 'details'), 'details.conflicts');
    if (conflicts.length === 0) {
      fail('details.conflicts', 'invalid_conflicts');
    }
    return {
      conflicts: conflicts.map((raw, index) => {
        const field = `details.conflicts[${index}]`;
        const conflict = object(raw, field);
        fields(conflict, ['objectType', 'objectId', 'expectedRevision', 'actualRevision'], field);
        return {
          objectType: token(required(conflict, 'objectType', field), `${field}.objectType`),
          objectId: token(required(conflict, 'objectId', field), `${field}.objectId`),
          expectedRevision: integer(required(conflict, 'expectedRevision', field), `${field}.expectedRevision`),
          actualRevision: integer(required(conflict, 'actualRevision', field), `${field}.actualRevision`),
        };
      }),
    };
  }
  if (code === 'POSITION_OUT_OF_RANGE') {
    const minimum = integer(required(input, 'minimum', 'details'), 'details.minimum');
    const maximum = integer(required(input, 'maximum', 'details'), 'details.maximum');
    if (minimum > maximum) {
      fail('details.minimum', 'invalid_range');
    }
    return {
      entryId: token(required(input, 'entryId', 'details'), 'details.entryId'), minimum, maximum,
    };
  }
  if (code === 'LIMIT_EXCEEDED') {
    return {
      field: safeText(required(input, 'field', 'details'), 'details.field'),
      limit: integer(required(input, 'limit', 'details'), 'details.limit'),
    };
  }
  if (code === 'ACTIVE_ENTRY_REQUIRES_CONTROLLER') {
    return {
      queueId: token(required(input, 'queueId', 'details'), 'details.queueId'),
      currentEntryId: token(required(input, 'currentEntryId', 'details'), 'details.currentEntryId'),
    };
  }
  if (code === 'STORE_BUSY' || code === 'STORE_UNAVAILABLE') {
    return { operation: token(required(input, 'operation', 'details'), 'details.operation') };
  }
  return { diagnosticId: token(required(input, 'diagnosticId', 'details'), 'details.diagnosticId') };
}

function validateError(value) {
  const input = object(value, 'error');
  const code = required(input, 'code', 'error');
  if (typeof code !== 'string' || !ERROR_DETAILS.has(code)) {
    fail('error.code', 'unknown_error_code');
  }
  fields(input, ['code', 'message', 'retryable', 'operation', 'details'], 'error');
  const errorMessage = message(required(input, 'message', 'error'), 'error.message');
  const retryable = required(input, 'retryable', 'error');
  if (typeof retryable !== 'boolean' || retryable !== RETRYABLE_ERRORS.has(code)) {
    fail('error.retryable', 'retryability_mismatch');
  }
  const operation = token(required(input, 'operation', 'error'), 'error.operation');
  const details = validateErrorDetails(code, required(input, 'details', 'error'));
  return { code, message: errorMessage, retryable, operation, details };
}

function commandResultBody(action, value) {
  const input = object(value, 'commandResult.result');
  if (action === 'PLAYLIST_DELETE') {
    fields(input, ['deletedPlaylistId', 'deletedRevision'], 'commandResult.result');
    return {
      deletedPlaylistId: token(required(input, 'deletedPlaylistId', 'result'), 'result.deletedPlaylistId'),
      deletedRevision: integer(required(input, 'deletedRevision', 'result'), 'result.deletedRevision'),
    };
  }
  const kind = RESULT_KIND.get(action);
  fields(input, [kind], 'commandResult.result');
  const snapshot = required(input, kind, 'commandResult.result');
  return { [kind]: kind === 'playlist' ? validatePlaylistSnapshot(snapshot) : validateQueueSnapshot(snapshot) };
}

function validateCommandResult(value) {
  const input = object(value, 'commandResult');
  const action = required(input, 'action', 'commandResult');
  if (typeof action !== 'string' || !COMMAND_FIELDS.has(action)) {
    fail('commandResult.action', 'unknown_action');
  }
  const status = required(input, 'status', 'commandResult');
  if (typeof status !== 'string' || !['APPLIED', 'REJECTED'].includes(status)) {
    fail('commandResult.status', 'invalid_status');
  }
  const arm = status === 'APPLIED' ? 'result' : 'error';
  fields(input, ['contractVersion', 'commandId', 'action', 'status', arm], 'commandResult');
  const contractVersion = version(required(input, 'contractVersion', 'document'));
  const commandId = token(required(input, 'commandId', 'commandResult'), 'commandResult.commandId');
  const body = arm === 'error'
    ? validateError(required(input, 'error', 'commandResult'))
    : commandResultBody(action, required(input, 'result', 'commandResult'));
  return { contractVersion, commandId, action, status, [arm]: body };
}

export {
  validateCommand,
  validateCommandResult,
  validateError,
  validateIdentifier,
  validateMediaRef,
  validatePlaylistEntry,
  validatePlaylistSnapshot,
  validateQueueEntry,
  validateQueueSnapshot,
};
