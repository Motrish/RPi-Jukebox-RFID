/** @jest-environment node */

import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { ContractValidationError } from './v1';
import {
  validatePlaybackAdmissionError,
  validatePlaybackCommand,
  validatePlaybackCommandResult,
} from './playback-v1';

const ROOT = path.resolve(__dirname, '../../../../');
const FIXTURE = JSON.parse(fs.readFileSync(
  path.join(ROOT, 'test/contracts/fixtures/playback_v1.json'), 'utf8',
));
const VALIDATORS = {
  validate_playback_command: validatePlaybackCommand,
  validate_playback_command_result: validatePlaybackCommandResult,
  validate_playback_admission_error: validatePlaybackAdmissionError,
};
const PYTHON_BRIDGE = [
  'import json, sys',
  'from jukebox.contracts.playback_v1 import (',
  '    ContractValidationError, validate_playback_command,',
  '    validate_playback_command_result, validate_playback_admission_error,',
  ')',
  'validators = {',
  '    "validate_playback_command": validate_playback_command,',
  '    "validate_playback_command_result": validate_playback_command_result,',
  '    "validate_playback_admission_error": validate_playback_admission_error,',
  '}',
  'request = json.load(sys.stdin)',
  'results = []',
  'for case in request["cases"]:',
  '    try:',
  '        value = validators[case["validator"]](case["input"])',
  '    except ContractValidationError as error:',
  '        results.append({"error": error.error})',
  '    else:',
  '        results.append({"expected": value})',
  'print(json.dumps(results, ensure_ascii=False, separators=(",", ":")))',
].join('\n');

function pythonResults(cases = FIXTURE.cases) {
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const output = execFileSync(python, ['-c', PYTHON_BRIDGE], {
    cwd: ROOT,
    env: { ...process.env, PYTHONPATH: path.join(ROOT, 'src/jukebox') },
    input: JSON.stringify({ cases }),
    encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024,
  });
  return JSON.parse(output);
}

function jsResults(cases = FIXTURE.cases) {
  return cases.map((testCase) => {
    try {
      return { expected: VALIDATORS[testCase.validator](testCase.input) };
    } catch (error) {
      if (!(error instanceof ContractValidationError)) throw error;
      return { error: error.error };
    }
  });
}

describe('playback admission contract parity', () => {
  test('matches all frozen Python fixture outcomes and diagnostics', () => {
    expect(FIXTURE.fixtureVersion).toBe(1);
    expect(FIXTURE.cases).toHaveLength(54);
    const js = jsResults();
    const python = pythonResults();
    FIXTURE.cases.forEach((testCase, index) => {
      expect(js[index]).toEqual(python[index]);
      expect({ expected: js[index].expected, error: js[index].error }).toEqual({
        expected: testCase.expected,
        error: testCase.error,
      });
    });
  });

  test('reports unsafe integer versions as unsupported in both peers', () => {
    const command = { contractVersion: 1, commandId: 'c', action: 'PLAYBACK_STOP' };
    const acceptedStop = JSON.parse(JSON.stringify(
      FIXTURE.cases.find((item) => item.name === 'accepted stop').input,
    ));
    const cases = [-9007199254740992, 9007199254740992].flatMap((contractVersion) => [
      {
        validator: 'validate_playback_command',
        input: { ...command, contractVersion },
      },
      {
        validator: 'validate_playback_command_result',
        input: { ...acceptedStop, contractVersion },
      },
    ]);
    const expected = {
      code: 'UNSUPPORTED_VERSION',
      message: 'The supplied contract value is invalid.',
      retryable: false,
      operation: 'CONTRACT_VALIDATION',
      details: { supportedVersions: [1] },
    };
    const js = jsResults(cases);
    const python = pythonResults(cases);
    cases.forEach((testCase, index) => {
      expect(js[index]).toEqual({ error: expected });
      expect(js[index]).toEqual(python[index]);
    });
  });

  test('handles native JavaScript closure, types, timestamps, copies, and prototypes', () => {
    const command = { contractVersion: 1, commandId: 'cmd1', action: 'PLAYBACK_START',
      queueId: 'q1', expectedQueueRevision: 0, entryId: 'e1' };
    expect(() => validatePlaybackCommand({ ...command, extra: true })).toThrow(ContractValidationError);
    expect(() => validatePlaybackCommand(Object.assign(Object.create({ inherited: true }), command)))
      .toThrow(ContractValidationError);
    expect(() => validatePlaybackCommand({ ...command, expectedQueueRevision: true }))
      .toThrow(ContractValidationError);

    const localResult = JSON.parse(JSON.stringify(FIXTURE.cases.find((item) => item.name === 'accepted start').input));
    const parsed = validatePlaybackCommandResult(localResult);
    expect(parsed.result.selection.entry).not.toBe(localResult.result.selection.entry);
    expect(parsed.result.selection.entry.mediaRef).not.toBe(localResult.result.selection.entry.mediaRef);
    parsed.result.selection.entry.mediaRef.libraryId = 'changed';
    expect(localResult.result.selection.entry.mediaRef.libraryId).toBe('lib1');

    const astralError = {
      code: 'CAPABILITY_UNAVAILABLE', message: '😀'.repeat(1024), retryable: false,
      operation: 'PLAYBACK_ADMIT', details: { capability: 'SPOTIFY_PLAYBACK' },
    };
    expect(validatePlaybackAdmissionError(astralError).message).toHaveLength(2048);
    expect(() => validatePlaybackAdmissionError({ ...astralError, message: '😀'.repeat(1025) }))
      .toThrow(ContractValidationError);
    const base = FIXTURE.cases.find((item) => item.name === 'accepted stop').input;
    for (const invalid of ['0000-01-01T00:00:00.000Z', '1900-02-29T00:00:00.000Z',
      '2024-02-30T00:00:00.000Z', '2024-01-01T24:00:00.000Z']) {
      const candidate = JSON.parse(JSON.stringify(base));
      candidate.result.acceptedAt = invalid;
      expect(() => validatePlaybackCommandResult(candidate)).toThrow(ContractValidationError);
    }
  });
});
