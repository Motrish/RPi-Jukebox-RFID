import {
  ContractValidationError,
  validateError,
  validateIdentifier,
  validateQueueEntry,
} from './v1';

const MAX_INTEGER = Number.MAX_SAFE_INTEGER;
const ACTIONS = new Set(['PLAYBACK_START', 'PLAYBACK_STOP']);
const OLD_ERRORS = new Set([
  'VALIDATION_ERROR', 'UNSUPPORTED_VERSION', 'NOT_FOUND', 'REVISION_CONFLICT',
  'COMMAND_ID_REUSED', 'LIMIT_EXCEEDED', 'REVISION_EXHAUSTED', 'STORE_BUSY',
  'STORE_UNAVAILABLE', 'INTERNAL_ERROR',
]);
const STAMP = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\.([0-9]{3})Z$/;
const PYTHON_WHITESPACE = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/u;

function fail(field, reason, code = 'VALIDATION_ERROR') {
  throw new ContractValidationError(field, reason, code);
}

function object(value, field) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
      || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)) {
    fail(field, 'invalid_type');
  }
  return value;
}

function fields(value, expected, field) {
  const allowed = new Set(expected);
  if (Object.keys(value).some((key) => !allowed.has(key))) fail(field, 'unknown_field');
  const missing = expected.filter((key) => !Object.prototype.hasOwnProperty.call(value, key)).sort();
  if (missing.length) fail(`${field}.${missing[0]}`, 'missing_field');
}

function required(value, key, field) {
  if (!Object.prototype.hasOwnProperty.call(value, key)) fail(`${field}.${key}`, 'missing_field');
  return value[key];
}

function version(value) {
  if (!Number.isInteger(value)) fail('document.contractVersion', 'invalid_version_type');
  if (value !== 1) fail('document.contractVersion', 'unsupported_version', 'UNSUPPORTED_VERSION');
  return value;
}

function integer(value, field) {
  if (!Number.isSafeInteger(value) || value < 0 || value > MAX_INTEGER) fail(field, 'invalid_integer');
  return value === 0 ? 0 : value;
}

function text(value, field) {
  if (typeof value !== 'string' || Array.from(value).length < 1 || Array.from(value).length > 1024
      || PYTHON_WHITESPACE.test(value)) fail(field, 'invalid_message');
  return value;
}

function timestamp(value) {
  if (typeof value !== 'string') fail('result.acceptedAt', 'invalid_timestamp');
  const match = STAMP.exec(value);
  if (!match || match[0] !== value) fail('result.acceptedAt', 'invalid_timestamp');
  const [, y, m, d, h, min, s] = match;
  const year = Number(y), month = Number(m), day = Number(d);
  const hour = Number(h), minute = Number(min), second = Number(s);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > monthDays[month - 1]
      || hour > 23 || minute > 59 || second > 59) fail('result.acceptedAt', 'invalid_timestamp');
  return value;
}

export function validatePlaybackCommand(value) {
  const input = object(value, 'command');
  const action = required(input, 'action', 'command');
  if (typeof action !== 'string' || !ACTIONS.has(action)) fail('command.action', 'unknown_action');
  const names = ['contractVersion', 'commandId', 'action'];
  if (action === 'PLAYBACK_START') names.push('queueId', 'expectedQueueRevision', 'entryId');
  fields(input, names, 'command');
  const result = {
    contractVersion: version(required(input, 'contractVersion', 'document')),
    commandId: validateIdentifier(required(input, 'commandId', 'command'), 'command.commandId'),
    action,
  };
  if (action === 'PLAYBACK_START') {
    result.queueId = validateIdentifier(input.queueId, 'command.queueId');
    result.expectedQueueRevision = integer(input.expectedQueueRevision, 'command.expectedQueueRevision');
    result.entryId = validateIdentifier(input.entryId, 'command.entryId');
  }
  return result;
}

export function validatePlaybackAdmissionError(value) {
  const input = object(value, 'error');
  const code = required(input, 'code', 'error');
  if (typeof code !== 'string') fail('error.code', 'unknown_error_code');
  if (OLD_ERRORS.has(code)) return validateError(input);
  if (code !== 'CAPABILITY_UNAVAILABLE') fail('error.code', 'unknown_error_code');
  fields(input, ['code', 'message', 'retryable', 'operation', 'details'], 'error');
  const message = text(required(input, 'message', 'error'), 'error.message');
  if (required(input, 'retryable', 'error') !== false) fail('error.retryable', 'retryability_mismatch');
  const operation = validateIdentifier(required(input, 'operation', 'error'), 'error.operation');
  const details = object(required(input, 'details', 'error'), 'error.details');
  fields(details, ['capability'], 'error.details');
  const capability = required(details, 'capability', 'error.details');
  if (capability !== 'SPOTIFY_PLAYBACK') fail('error.details.capability', 'invalid_capability');
  return { code, message, retryable: false, operation, details: { capability } };
}

export function validatePlaybackCommandResult(value) {
  const input = object(value, 'commandResult');
  const action = required(input, 'action', 'commandResult');
  if (typeof action !== 'string' || !ACTIONS.has(action)) fail('commandResult.action', 'unknown_action');
  const status = required(input, 'status', 'commandResult');
  if (typeof status !== 'string' || !['ACCEPTED', 'REJECTED'].includes(status)) {
    fail('commandResult.status', 'invalid_status');
  }
  const arm = status === 'ACCEPTED' ? 'result' : 'error';
  fields(input, ['contractVersion', 'commandId', 'action', 'status', arm], 'commandResult');
  const contractVersion = version(required(input, 'contractVersion', 'document'));
  const commandId = validateIdentifier(required(input, 'commandId', 'commandResult'), 'commandResult.commandId');
  if (status === 'REJECTED') {
    const error = validatePlaybackAdmissionError(required(input, 'error', 'commandResult'));
    if (!['PLAYBACK_ADMIT', 'CONTRACT_VALIDATION'].includes(error.operation)) {
      fail('commandResult.error.operation', 'invalid_operation');
    }
    return { contractVersion, commandId, action, status, error };
  }
  const result = object(required(input, 'result', 'commandResult'), 'commandResult.result');
  fields(result, ['intentId', 'intentSequence', 'acceptedAt', 'selection'], 'commandResult.result');
  const intentId = validateIdentifier(result.intentId, 'result.intentId');
  const intentSequence = integer(result.intentSequence, 'result.intentSequence');
  if (intentSequence === 0) fail('result.intentSequence', 'invalid_integer');
  const acceptedAt = timestamp(result.acceptedAt);
  let selection;
  if (action === 'PLAYBACK_STOP') {
    if (result.selection !== null) fail('result.selection', 'must_be_null');
    selection = null;
  } else {
    const rawSelection = object(result.selection, 'result.selection');
    fields(rawSelection, ['queueId', 'queueRevision', 'entry'], 'result.selection');
    const queueId = validateIdentifier(rawSelection.queueId, 'selection.queueId');
    const queueRevision = integer(rawSelection.queueRevision, 'selection.queueRevision');
    const entry = validateQueueEntry(rawSelection.entry, null, 'selection.entry');
    if (entry.mediaRef.kind !== 'LOCAL') fail('selection.entry.mediaRef.kind', 'local_media_required');
    selection = { queueId, queueRevision, entry };
  }
  return {
    contractVersion, commandId, action, status,
    result: { intentId, intentSequence, acceptedAt, selection },
  };
}
