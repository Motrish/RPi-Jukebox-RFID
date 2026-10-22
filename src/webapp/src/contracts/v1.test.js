/** @jest-environment node */

import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import {
  ContractValidationError,
  validateCommand,
  validateCommandResult,
  validateError,
  validateIdentifier,
  validateMediaRef,
  validatePlaylistEntry,
  validatePlaylistSnapshot,
  validateQueueEntry,
  validateQueueSnapshot,
} from './v1';

const REPOSITORY_ROOT = path.resolve(__dirname, '../../../../');
const FIXTURE_PATH = path.join(REPOSITORY_ROOT, 'test/contracts/fixtures/v1.json');
const FIXTURES = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));
const VALIDATORS = {
  validate_command: validateCommand,
  validate_command_result: validateCommandResult,
  validate_error: validateError,
  validate_identifier: validateIdentifier,
  validate_media_ref: validateMediaRef,
  validate_playlist_entry: validatePlaylistEntry,
  validate_playlist_snapshot: validatePlaylistSnapshot,
  validate_queue_entry: validateQueueEntry,
  validate_queue_snapshot: validateQueueSnapshot,
};

// Fixed bridge source: input values arrive only through JSON on stdin. Validator
// selection is restricted to this static map; no payload becomes code.
const PYTHON_BRIDGE = [
  'import json, sys',
  'from jukebox.contracts.v1 import (',
  '    ContractValidationError, validate_command, validate_command_result,',
  '    validate_error, validate_identifier, validate_media_ref,',
  '    validate_playlist_entry, validate_playlist_snapshot,',
  '    validate_queue_entry, validate_queue_snapshot,',
  ')',
  'validators = {',
  '    "validate_command": validate_command,',
  '    "validate_command_result": validate_command_result,',
  '    "validate_error": validate_error,',
  '    "validate_identifier": validate_identifier,',
  '    "validate_media_ref": validate_media_ref,',
  '    "validate_playlist_entry": validate_playlist_entry,',
  '    "validate_playlist_snapshot": validate_playlist_snapshot,',
  '    "validate_queue_entry": validate_queue_entry,',
  '    "validate_queue_snapshot": validate_queue_snapshot,',
  '}',
  'request = json.load(sys.stdin)',
  'results = []',
  'for case in request["cases"]:',
  '    value = json.loads(case["serialized"])',
  '    if "rawJson" in case:',
  '        target = value',
  '        for part in case["path"][:-1]:',
  '            target = target[part]',
  '        target[case["path"][-1]] = json.loads(case["rawJson"])',
  '    try:',
  '        result = validators[case["validator"]](value)',
  '    except ContractValidationError as error:',
  '        results.append({"ok": False, "error": error.error})',
  '    else:',
  '        results.append({"ok": True, "value": result})',
  'print(json.dumps(results, ensure_ascii=False, separators=(",", ":")))',
].join('\n');

const clone = (value) => JSON.parse(JSON.stringify(value));

function pythonValidate(cases) {
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const output = execFileSync(python, ['-c', PYTHON_BRIDGE], {
    cwd: REPOSITORY_ROOT,
    env: {
      ...process.env,
      PYTHONPATH: path.join(REPOSITORY_ROOT, 'src/jukebox'),
    },
    input: JSON.stringify({ cases }),
    encoding: 'utf8',
    timeout: 30000,
    maxBuffer: 32 * 1024 * 1024,
  });
  return JSON.parse(output);
}

function attempt(validator, input) {
  try {
    return { ok: true, value: VALIDATORS[validator](input) };
  } catch (error) {
    if (!(error instanceof ContractValidationError)) {
      throw error;
    }
    return { ok: false, error: error.error };
  }
}

function compareWithPython(cases) {
  const originalPythonCases = cases.map((item) => ({
    validator: item.validator,
    serialized: JSON.stringify(item.input),
  }));
  const originalPythonResults = pythonValidate(originalPythonCases);
  const javascriptResults = cases.map((item) => attempt(item.validator, item.input));
  cases.forEach((item, index) => {
    expect(JSON.stringify(item.input)).toBe(originalPythonCases[index].serialized);
  });
  const canonicalCases = [];

  cases.forEach((item, index) => {
    const javascript = javascriptResults[index];
    const python = originalPythonResults[index];
    if (item.expectedError) {
      expect(javascript.ok).toBe(false);
      expect(javascript.error.code).toBe(item.expectedError);
    } else {
      expect(javascript.ok).toBe(true);
      expect(python.ok).toBe(true);
    }
    expect(javascript.ok).toBe(python.ok);
    if (javascript.ok) {
      expect(JSON.parse(JSON.stringify(javascript.value))).toEqual(python.value);
      canonicalCases.push({
        validator: item.validator,
        serialized: JSON.stringify(javascript.value),
        expectedValue: javascript.value,
      });
    } else {
      expect(javascript.error).toEqual(python.error);
    }
  });

  const canonicalResults = pythonValidate(canonicalCases);
  expect(canonicalResults).toHaveLength(canonicalCases.length);
  canonicalResults.forEach((result, index) => {
    expect(result.ok).toBe(true);
    expect(result.value).toEqual(canonicalCases[index].expectedValue);
  });
}

function command(action, fields) {
  return {
    contractVersion: 1,
    commandId: `cmd_synthetic_${action.toLowerCase()}`,
    action,
    ...fields,
  };
}

function validCommands() {
  const items = [
    { mediaRef: FIXTURES.valid_media_refs[0], title: 'Local story' },
    { mediaRef: FIXTURES.valid_media_refs[1], title: 'Spotify track' },
  ];
  return [
    command('PLAYLIST_CREATE', { name: 'Mix', items }),
    command('PLAYLIST_RENAME', { playlistId: 'pl_1', expectedRevision: 0, name: 'Mix' }),
    command('PLAYLIST_APPEND', { playlistId: 'pl_1', expectedRevision: 0, items }),
    command('PLAYLIST_REMOVE', { playlistId: 'pl_1', expectedRevision: 0, entryId: 'pe_1' }),
    command('PLAYLIST_MOVE', { playlistId: 'pl_1', expectedRevision: 0, entryId: 'pe_1', toPosition: 0 }),
    command('PLAYLIST_DELETE', { playlistId: 'pl_1', expectedRevision: 0 }),
    command('QUEUE_CREATE', { items }),
    command('QUEUE_LOAD_PLAYLIST', {
      queueId: 'q_1', expectedQueueRevision: 0, playlistId: 'pl_1', expectedPlaylistRevision: 0,
    }),
    command('QUEUE_APPEND', { queueId: 'q_1', expectedRevision: 0, items }),
    command('QUEUE_REMOVE', { queueId: 'q_1', expectedRevision: 0, entryId: 'qe_1' }),
    command('QUEUE_MOVE', { queueId: 'q_1', expectedRevision: 0, entryId: 'qe_1', toPosition: 0 }),
    command('QUEUE_SET_MODES', { queueId: 'q_1', expectedRevision: 0, repeatMode: 'ALL', shuffleMode: 'ON' }),
    command('QUEUE_SET_CURRENT', { queueId: 'q_1', expectedRevision: 0, entryId: null }),
    command('QUEUE_SAVE_NEW_PLAYLIST', { queueId: 'q_1', expectedQueueRevision: 0, name: 'Saved' }),
    command('QUEUE_SAVE_PLAYLIST', {
      queueId: 'q_1', expectedQueueRevision: 0, playlistId: 'pl_1', expectedPlaylistRevision: 0,
    }),
  ];
}

function validErrors() {
  const definitions = [
    ['VALIDATION_ERROR', false, { field: 'name', reason: 'invalid_name' }],
    ['UNSUPPORTED_VERSION', false, { supportedVersions: [1] }],
    ['NOT_FOUND', false, { objectType: 'playlist', objectId: 'pl_missing' }],
    ['COMMAND_NOT_FOUND', false, { commandId: 'cmd_missing' }],
    ['REVISION_CONFLICT', false, { conflicts: [
      { objectType: 'playlist', objectId: 'pl_1', expectedRevision: 1, actualRevision: 2 },
    ] }],
    ['COMMAND_ID_REUSED', false, { commandId: 'cmd_1' }],
    ['POSITION_OUT_OF_RANGE', false, { entryId: 'pe_1', minimum: 0, maximum: 2 }],
    ['LIMIT_EXCEEDED', false, { field: 'command.items', limit: 10000 }],
    ['ACTIVE_ENTRY_REQUIRES_CONTROLLER', false, { queueId: 'q_1', currentEntryId: 'qe_1' }],
    ['REVISION_EXHAUSTED', false, { objectType: 'playlist', objectId: 'pl_1' }],
    ['STORE_BUSY', true, { operation: 'PLAYLIST_GET' }],
    ['STORE_UNAVAILABLE', true, { operation: 'PLAYLIST_GET' }],
    ['INTERNAL_ERROR', false, { diagnosticId: 'diag_1' }],
  ];
  return definitions.map(([code, retryable, details]) => ({
    code,
    message: 'A safe synthetic diagnostic.',
    retryable,
    operation: 'SYNTHETIC_TEST',
    details,
  }));
}

function appliedResult(writeCommand) {
  const { action, commandId } = writeCommand;
  let result;
  if (action === 'PLAYLIST_DELETE') {
    result = { deletedPlaylistId: 'pl_1', deletedRevision: 2 };
  } else if (action.startsWith('PLAYLIST') || action.startsWith('QUEUE_SAVE')) {
    result = { playlist: FIXTURES.valid_playlist };
  } else {
    result = { queue: FIXTURES.valid_queue };
  }
  return { contractVersion: 1, commandId, action, status: 'APPLIED', result };
}

function errorFor(code) {
  return validErrors().find((error) => error.code === code);
}

function rejectedResult(writeCommand) {
  return {
    contractVersion: 1,
    commandId: writeCommand.commandId,
    action: writeCommand.action,
    status: 'REJECTED',
    error: errorFor('VALIDATION_ERROR'),
  };
}

function entries(count, queue = false) {
  return Array.from({ length: count }, (_, index) => ({
    entryId: `entry_${index}`,
    ...(queue ? { sourceEntryId: null } : {}),
    mediaRef: { kind: 'LOCAL', libraryId: 'lib_synthetic_001' },
    title: 'Synthetic',
    position: index,
  }));
}

function queueSnapshotWithEntries(count) {
  return {
    ...clone(FIXTURES.valid_empty_queue),
    entries: entries(count, true),
  };
}

function playlistSnapshotWithEntries(count) {
  return {
    ...clone(FIXTURES.valid_playlist),
    entries: entries(count),
  };
}

function setPath(value, parts, replacement) {
  let target = value;
  parts.slice(0, -1).forEach((part) => { target = target[part]; });
  target[parts[parts.length - 1]] = replacement;
}

describe('transport-free V1 JavaScript contract writer', () => {
  test('keeps all legacy fixture examples and the shared corpus classifications', () => {
    expect(FIXTURES.valid_media_refs).toHaveLength(2);
    expect(FIXTURES.valid_playlist.entries).toHaveLength(3);
    expect(FIXTURES.valid_queue.entries).toHaveLength(3);
    expect(FIXTURES.valid_empty_queue.entries).toEqual([]);
    expect(FIXTURES.js_conformance.domain.integerMaximum).toBe(Number.MAX_SAFE_INTEGER);
    expect(FIXTURES.js_conformance.domain.rawNumberCases.map((item) => item.classification)).toEqual([
      'RAW_FLOAT_LEXEME_LOST_AFTER_JSON_PARSE',
      'RAW_FLOAT_LEXEME_LOST_AFTER_JSON_PARSE',
      'RAW_FLOAT_LEXEME_LOST_AFTER_JSON_PARSE',
      'RAW_FLOAT_LEXEME_LOST_AFTER_JSON_PARSE',
      'OUTSIDE_SAFE_INTEGER_DOMAIN',
      'OUTSIDE_SAFE_INTEGER_DOMAIN',
    ]);
  });

  test('accepts and Python-revalidates the mixed source, entry, and snapshot fixtures', () => {
    const playlistEntry = FIXTURES.valid_playlist.entries[0];
    const queueEntry = FIXTURES.valid_queue.entries[0];
    const checks = [
      ...FIXTURES.valid_media_refs.map((input) => ({ validator: 'validate_media_ref', input })),
      { validator: 'validate_identifier', input: 'A_b-9' },
      { validator: 'validate_identifier', input: 'x'.repeat(128) },
      { validator: 'validate_playlist_entry', input: playlistEntry },
      { validator: 'validate_queue_entry', input: queueEntry },
      { validator: 'validate_playlist_snapshot', input: FIXTURES.valid_playlist },
      { validator: 'validate_queue_snapshot', input: FIXTURES.valid_queue },
      { validator: 'validate_queue_snapshot', input: FIXTURES.valid_empty_queue },
    ];
    compareWithPython(checks);
  });

  test('validates every write command, both result arms, and every error-details family', () => {
    const writes = validCommands();
    expect(writes).toHaveLength(15);
    const checks = writes.map((input) => ({ validator: 'validate_command', input }));
    const results = writes.flatMap((writeCommand) => [
      { validator: 'validate_command_result', input: appliedResult(writeCommand) },
      { validator: 'validate_command_result', input: rejectedResult(writeCommand) },
    ]);
    const errors = validErrors().map((input) => ({ validator: 'validate_error', input }));
    compareWithPython([...checks, ...results, ...errors]);
  });

  test('matches closed-shape, version, result-arm, selection, and prototype rejections', () => {
    const missingMediaField = { kind: 'LOCAL' };
    const extraMediaField = { ...FIXTURES.valid_media_refs[0], unexpected: true };
    const missingQueueSource = clone(FIXTURES.valid_queue.entries[0]);
    delete missingQueueSource.sourceEntryId;
    const duplicatePlaylistEntry = clone(FIXTURES.valid_playlist);
    duplicatePlaylistEntry.entries[1].entryId = duplicatePlaylistEntry.entries[0].entryId;
    const gappedPositions = clone(FIXTURES.valid_playlist);
    gappedPositions.entries[1].position = 5;
    const unpairedSource = { ...clone(FIXTURES.valid_queue), sourcePlaylistId: null };
    const wrongSelection = { ...clone(FIXTURES.valid_queue), currentEntryId: 'qe_missing' };
    const unsupportedVersion = { ...clone(FIXTURES.valid_playlist), contractVersion: 2 };
    const appliedNullResult = { ...appliedResult(validCommands()[0]), result: null };
    const rejectedNullError = { ...rejectedResult(validCommands()[0]), error: null };
    const appliedNullError = { ...appliedResult(validCommands()[0]), error: null };
    const rejectedNullResult = { ...rejectedResult(validCommands()[0]), result: null };
    const resultWithBothArms = {
      ...appliedResult(validCommands()[0]),
      error: errorFor('VALIDATION_ERROR'),
    };
    const unknownAction = command('__proto__', {});
    const inheritedMedia = Object.create({ kind: 'LOCAL', libraryId: 'lib_synthetic_001' });
    const parsedPrototypeKey = JSON.parse('{"kind":"LOCAL","libraryId":"lib_synthetic_001","__proto__":{"polluted":true}}');
    const prototypeError = { ...errorFor('VALIDATION_ERROR'), code: 'toString' };
    const invalidStatuses = [[], {}];
    const wrongRetryability = { ...errorFor('STORE_BUSY'), retryable: false };
    const wrongLimitDetails = {
      ...errorFor('LIMIT_EXCEEDED'),
      details: { field: 'command.items', reason: 'limit_exceeded' },
    };
    const prototypeCases = FIXTURES.js_conformance.prototypePropertyNames.flatMap((name) => [
      { validator: 'validate_media_ref', input: { ...FIXTURES.valid_media_refs[0], [name]: true }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command', input: command(name, {}), expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: { ...errorFor('VALIDATION_ERROR'), code: name }, expectedError: 'VALIDATION_ERROR' },
    ]);
    const checks = [
      { validator: 'validate_media_ref', input: missingMediaField, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_media_ref', input: extraMediaField, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_media_ref', input: inheritedMedia, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_media_ref', input: parsedPrototypeKey, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_queue_entry', input: missingQueueSource, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: duplicatePlaylistEntry, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: gappedPositions, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_queue_snapshot', input: unpairedSource, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_queue_snapshot', input: wrongSelection, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: unsupportedVersion, expectedError: 'UNSUPPORTED_VERSION' },
      ...[0, -1].map((contractVersion) => ({
        validator: 'validate_playlist_snapshot',
        input: { ...clone(FIXTURES.valid_playlist), contractVersion },
        expectedError: 'UNSUPPORTED_VERSION',
      })),
      { validator: 'validate_command', input: unknownAction, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: prototypeError, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: wrongRetryability, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: wrongLimitDetails, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command_result', input: resultWithBothArms, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command_result', input: appliedNullResult, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command_result', input: rejectedNullError, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command_result', input: appliedNullError, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command_result', input: rejectedNullResult, expectedError: 'VALIDATION_ERROR' },
      ...invalidStatuses.map((status) => ({
        validator: 'validate_command_result',
        input: { ...appliedResult(validCommands()[0]), status },
        expectedError: 'VALIDATION_ERROR',
      })),
      ...prototypeCases,
    ];
    compareWithPython(checks.filter((item) => item.input !== inheritedMedia));
    checks.filter((item) => item.input === inheritedMedia).forEach((item) => {
      expect(() => VALIDATORS[item.validator](item.input)).toThrow(ContractValidationError);
    });
  });

  test('uses only finite safe integer values for versions, revisions, and positions', () => {
    const invalidNumbers = [true, null, -1, 1.5, '1', Number.NaN, Infinity, -Infinity,
      Number.MAX_SAFE_INTEGER + 1];
    const checks = invalidNumbers.slice(0, 5).flatMap((value) => [
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), revision: value }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_command', input: command('PLAYLIST_MOVE', {
        playlistId: 'pl_1', expectedRevision: 0, entryId: 'pe_1', toPosition: value,
      }), expectedError: 'VALIDATION_ERROR' },
    ]);
    checks.push(
      ...FIXTURES.js_conformance.domain.sharedSafeIntegers.map((revision) => ({
        validator: 'validate_playlist_snapshot',
        input: { ...clone(FIXTURES.valid_playlist), revision },
      })),
      { validator: 'validate_queue_snapshot', input: { ...clone(FIXTURES.valid_empty_queue), sourcePlaylistRevision: Number.MAX_SAFE_INTEGER, sourcePlaylistId: 'pl_1' } },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), revision: Number.MAX_SAFE_INTEGER + 1 }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), contractVersion: true }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), contractVersion: null }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), contractVersion: '1' }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), contractVersion: 1.5 }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_snapshot', input: { ...clone(FIXTURES.valid_playlist), contractVersion: 2 }, expectedError: 'UNSUPPORTED_VERSION' },
    );
    compareWithPython(checks);

    for (const value of invalidNumbers.slice(5)) {
      const input = { ...clone(FIXTURES.valid_playlist), revision: value };
      expect(() => validatePlaylistSnapshot(input)).toThrow(ContractValidationError);
    }
    const missingValue = { ...clone(FIXTURES.valid_playlist), revision: undefined };
    expect(() => validatePlaylistSnapshot(missingValue)).toThrow(ContractValidationError);
  });

  test('normalizes accepted negative zero to canonical positive zero', () => {
    const input = { ...clone(FIXTURES.valid_playlist), revision: -0 };
    const output = validatePlaylistSnapshot(input);

    expect(Object.is(input.revision, -0)).toBe(true);
    expect(Object.is(output.revision, -0)).toBe(false);
    expect(output.revision).toBe(0);
  });

  test('documents raw number lexeme loss and keeps out-of-domain versions explicit', () => {
    const rawCases = FIXTURES.js_conformance.domain.rawNumberCases;
    const pythonCases = rawCases.map((item) => {
      const input = item.validator === 'validate_error'
        ? errorFor('UNSUPPORTED_VERSION')
        : clone(FIXTURES.valid_playlist);
      return {
        validator: item.validator,
        serialized: JSON.stringify(input),
        rawJson: item.rawJson,
        path: item.path,
      };
    });
    const pythonResults = pythonValidate(pythonCases);
    const canonicalCases = [];
    const outcomeChecks = [];
    const expectedOutcomeChecks = [];

    rawCases.forEach((item, index) => {
      const parsedNumber = JSON.parse(item.rawJson);
      expect(parsedNumber).toBe(item.jsParsedNumber);
      const input = item.validator === 'validate_error'
        ? errorFor('UNSUPPORTED_VERSION')
        : clone(FIXTURES.valid_playlist);
      setPath(input, item.path, parsedNumber);
      const javascript = attempt(item.validator, input);
      const python = pythonResults[index];
      if (item.jsOutcome === 'ACCEPT_CANONICAL_SAFE_INTEGER') {
        const canonical = JSON.stringify(javascript.value);
        outcomeChecks.push({
          javascriptAccepted: javascript.ok,
          pythonAccepted: python.ok,
          pythonError: python.error && python.error.code,
          canonicalRoundTrip: JSON.parse(canonical),
          javascriptValue: javascript.value,
        });
        expectedOutcomeChecks.push({
          javascriptAccepted: true,
          pythonAccepted: false,
          pythonError: item.pythonOutcome,
          canonicalRoundTrip: javascript.value,
          javascriptValue: javascript.value,
        });
        canonicalCases.push({
          validator: item.validator,
          serialized: canonical,
          expectedValue: javascript.value,
        });
      } else {
        outcomeChecks.push({
          javascriptAccepted: javascript.ok,
          pythonOutcome: python.ok ? 'ACCEPT' : python.error.code,
          javascriptOutcome: item.jsOutcome,
        });
        expectedOutcomeChecks.push({
          javascriptAccepted: false,
          pythonOutcome: item.pythonOutcome,
          javascriptOutcome: 'EXPLICIT_REJECTION_NO_ERROR_PARITY_CLAIM',
        });
      }
    });

    expect(outcomeChecks).toEqual(expectedOutcomeChecks);

    const canonicalResults = pythonValidate(canonicalCases);
    expect(canonicalResults).toHaveLength(canonicalCases.length);
    canonicalResults.forEach((result, index) => {
      expect(result.ok).toBe(true);
      expect(result.value).toEqual(canonicalCases[index].expectedValue);
    });
  });

  test('rejects sparse arrays at every contract list boundary', () => {
    const sparse = () => Array(1);
    const unsupportedVersion = {
      ...errorFor('UNSUPPORTED_VERSION'),
      details: { supportedVersions: sparse() },
    };
    const revisionConflict = {
      ...errorFor('REVISION_CONFLICT'),
      details: { conflicts: sparse() },
    };
    const sparseCases = [
      { validator: validatePlaylistSnapshot, input: { ...clone(FIXTURES.valid_playlist), entries: sparse() } },
      { validator: validateQueueSnapshot, input: { ...clone(FIXTURES.valid_empty_queue), entries: sparse() } },
      { validator: validateCommand, input: command('PLAYLIST_CREATE', { name: 'Sparse', items: sparse() }) },
      { validator: validateError, input: unsupportedVersion },
      { validator: validateError, input: revisionConflict },
    ];

    sparseCases.forEach(({ validator, input }) => {
      expect(() => validator(input)).toThrow(ContractValidationError);
    });
  });

  test('matches Python code-point lengths and whitespace semantics without normalizing text', () => {
    const astral = FIXTURES.js_conformance.unicode.astralCharacter;
    const whitespace = FIXTURES.js_conformance.unicode.pythonWhitespaceCases;
    const checks = [
      { validator: 'validate_command', input: command('PLAYLIST_CREATE', { name: astral.repeat(256), items: [] }) },
      { validator: 'validate_command', input: command('PLAYLIST_CREATE', { name: astral.repeat(257), items: [] }), expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_playlist_entry', input: { ...FIXTURES.valid_playlist.entries[0], title: astral.repeat(1024) } },
      { validator: 'validate_playlist_entry', input: { ...FIXTURES.valid_playlist.entries[0], title: astral.repeat(1025) }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: { ...errorFor('VALIDATION_ERROR'), message: astral.repeat(1024) } },
      { validator: 'validate_error', input: { ...errorFor('VALIDATION_ERROR'), message: astral.repeat(1025) }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_error', input: { ...errorFor('VALIDATION_ERROR'), details: { field: astral.repeat(256), reason: 'invalid_name' } } },
      { validator: 'validate_error', input: { ...errorFor('VALIDATION_ERROR'), details: { field: astral.repeat(257), reason: 'invalid_name' } }, expectedError: 'VALIDATION_ERROR' },
    ];
    whitespace.forEach((sample) => {
      expect(['PYTHON_WHITESPACE', 'PYTHON_NON_WHITESPACE']).toContain(sample.jsClassification);
      expect(sample.pythonStripIsEmpty).toBe(sample.jsClassification === 'PYTHON_WHITESPACE');
      const name = command('PLAYLIST_CREATE', { name: sample.value, items: [] });
      checks.push({
        validator: 'validate_command',
        input: name,
        expectedError: sample.pythonStripIsEmpty ? 'VALIDATION_ERROR' : undefined,
      });
      const title = { ...FIXTURES.valid_playlist.entries[0], title: sample.value };
      checks.push({
        validator: 'validate_playlist_entry',
        input: title,
        expectedError: sample.pythonStripIsEmpty ? 'VALIDATION_ERROR' : undefined,
      });
    });
    compareWithPython(checks);
    expect(validatePlaylistEntry({
      ...FIXTURES.valid_playlist.entries[0], title: '  keep surrounding space  ',
    }).title).toBe('  keep surrounding space  ');
  });

  test('requires full ASCII token and Spotify matches, including terminal-newline rejection', () => {
    const validToken = 'a'.repeat(128);
    const invalidIds = ['', 'a/b', 'ümlaut', 'x'.repeat(129), 'token\n'];
    const checks = [
      { validator: 'validate_identifier', input: validToken },
      ...invalidIds.map((input) => ({ validator: 'validate_identifier', input, expectedError: 'VALIDATION_ERROR' })),
      { validator: 'validate_media_ref', input: { kind: 'SPOTIFY', uri: 'spotify:track:0123456789ABCDEFGHIJKL' } },
      { validator: 'validate_media_ref', input: { kind: 'SPOTIFY', uri: 'spotify:track:0123456789ABCDEFGHIJKL\n' }, expectedError: 'VALIDATION_ERROR' },
      { validator: 'validate_media_ref', input: { kind: 'M3U', uri: 'https://example.invalid/list.m3u' }, expectedError: 'VALIDATION_ERROR' },
    ];
    compareWithPython(checks);
  });

  test('accepts exactly the 10000 item limit and rejects 10001 for every list family', () => {
    const limit = FIXTURES.js_conformance.domain.maxEntries;
    const commandItems = Array.from({ length: limit }, () => ({
      mediaRef: { kind: 'LOCAL', libraryId: 'lib_synthetic_001' },
      title: 'Synthetic',
    }));
    const checks = [
      { validator: 'validate_playlist_snapshot', input: playlistSnapshotWithEntries(limit) },
      { validator: 'validate_queue_snapshot', input: queueSnapshotWithEntries(limit) },
      { validator: 'validate_command', input: command('PLAYLIST_CREATE', { name: 'Boundary', items: commandItems }) },
      { validator: 'validate_playlist_snapshot', input: playlistSnapshotWithEntries(limit + 1), expectedError: 'LIMIT_EXCEEDED' },
      { validator: 'validate_queue_snapshot', input: queueSnapshotWithEntries(limit + 1), expectedError: 'LIMIT_EXCEEDED' },
      { validator: 'validate_command', input: command('PLAYLIST_CREATE', { name: 'Overflow', items: [...commandItems, commandItems[0]] }), expectedError: 'LIMIT_EXCEEDED' },
    ];
    compareWithPython(checks);
  });

  test('returns detached JSON copies for nested snapshots, commands, and results', () => {
    const input = clone(FIXTURES.valid_playlist);
    const parsed = validatePlaylistSnapshot(input);
    expect(parsed).not.toBe(input);
    expect(parsed.entries).not.toBe(input.entries);
    expect(parsed.entries[0]).not.toBe(input.entries[0]);
    expect(parsed.entries[0].mediaRef).not.toBe(input.entries[0].mediaRef);
    parsed.entries[0].mediaRef.libraryId = 'changed_output';
    expect(input.entries[0].mediaRef.libraryId).toBe('lib_synthetic_001');

    const write = validCommands()[0];
    const parsedCommand = validateCommand(write);
    expect(parsedCommand).not.toBe(write);
    expect(parsedCommand.items).not.toBe(write.items);
    expect(parsedCommand.items[0].mediaRef).not.toBe(write.items[0].mediaRef);

    const queue = clone(FIXTURES.valid_queue);
    const parsedQueue = validateQueueSnapshot(queue);
    expect(parsedQueue.entries).not.toBe(queue.entries);
    expect(parsedQueue.entries[0].mediaRef).not.toBe(queue.entries[0].mediaRef);

    const error = errorFor('REVISION_CONFLICT');
    const parsedError = validateError(error);
    expect(parsedError.details.conflicts).not.toBe(error.details.conflicts);
    expect(parsedError.details.conflicts[0]).not.toBe(error.details.conflicts[0]);

    const result = appliedResult(write);
    const parsedResult = validateCommandResult(result);
    expect(parsedResult).not.toBe(result);
    expect(parsedResult.result.playlist).not.toBe(result.result.playlist);
    expect(parsedResult.result.playlist.entries[0]).not.toBe(result.result.playlist.entries[0]);
  });
});
