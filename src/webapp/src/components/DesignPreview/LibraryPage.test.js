import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import LibraryPage from './LibraryPage';
import { fetchLibraryPage } from './libraryClient';

const realFetchLibraryPage = jest.requireActual('./libraryClient').fetchLibraryPage;

jest.mock('./libraryClient', () => ({ fetchLibraryPage: jest.fn() }));

const CODE = 'a'.repeat(43);
const item = (libraryId, displayName, availability = 'AVAILABLE') => ({
  libraryId, displayName, availability,
});
const page = (items, nextCursor = null) => ({ items, nextCursor });
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

jest.setTimeout(10000);

beforeEach(() => {
  fetchLibraryPage.mockReset();
});

function openLibrary() {
  render(<LibraryPage />);
  expect(fetchLibraryPage).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
  fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
}

test('does not request before code submission and renders duplicate titles by opaque ID', async () => {
  fetchLibraryPage.mockResolvedValue(page([
    item('lib_first', 'Gleicher Titel.mp3'),
    item('lib_second', 'Gleicher Titel.mp3', 'UNKNOWN'),
    item('lib_third', '<img src=x onerror=alert(1)>', 'MISSING'),
  ]));
  openLibrary();

  expect(await screen.findByText('lib_first')).toBeInTheDocument();
  expect(screen.getByText('lib_second')).toBeInTheDocument();
  expect(screen.getByText('Vorhanden')).toBeInTheDocument();
  expect(screen.getByText('Unbekannt')).toBeInTheDocument();
  expect(screen.getByText('Fehlt')).toBeInTheDocument();
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  expect(document.querySelector('img')).toBeNull();
  expect(fetchLibraryPage).toHaveBeenCalledWith(CODE, undefined, expect.any(AbortSignal));
});

test('shows an honest empty state and pages without a total count', async () => {
  fetchLibraryPage.mockResolvedValueOnce(page([], null)).mockResolvedValueOnce(page([
    item('lib_1', 'Titel.mp3'),
  ], 'lib_1')).mockResolvedValueOnce(page([item('lib_2', 'Weiter.mp3')]));
  openLibrary();
  expect(await screen.findByText(/keine titel/i)).toBeInTheDocument();
  expect(screen.getByText(/seite 1/i)).toBeInTheDocument();
  expect(screen.queryByText(/von \d+/i)).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /aktualisieren/i }));
  expect(await screen.findByText('Titel.mp3')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /weiter/i }));
  expect(await screen.findByText('Weiter.mp3')).toBeInTheDocument();
  expect(fetchLibraryPage.mock.calls[2][1]).toBe('lib_1');
  fireEvent.click(screen.getByRole('button', { name: /zurück/i }));
  await waitFor(() => expect(fetchLibraryPage.mock.calls[3][1]).toBeUndefined());
});

test('401 clears the code and catalog and returns to the code form', async () => {
  fetchLibraryPage.mockResolvedValueOnce(page([item('lib_1', 'Privater Titel.mp3')]));
  openLibrary();
  expect(await screen.findByText('Privater Titel.mp3')).toBeInTheDocument();
  fetchLibraryPage.mockRejectedValueOnce(Object.assign(new Error('unsafe raw response'), { code: 'UNAUTHORIZED' }));
  fireEvent.click(screen.getByRole('button', { name: /aktualisieren/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/zugangscode.*abgelaufen|erneut/i);
  expect(screen.queryByText('Privater Titel.mp3')).not.toBeInTheDocument();
  expect(screen.getByLabelText(/zugangscode/i)).toHaveValue('');
  expect(screen.queryByText('unsafe raw response')).not.toBeInTheDocument();
});

test('forgetting access removes the code and current catalog', async () => {
  fetchLibraryPage.mockResolvedValue(page([item('lib_1', 'Vertraulicher Titel.mp3')]));
  openLibrary();
  expect(await screen.findByText('Vertraulicher Titel.mp3')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /zugang vergessen/i }));
  expect(screen.queryByText('Vertraulicher Titel.mp3')).not.toBeInTheDocument();
  expect(screen.getByLabelText(/zugangscode/i)).toHaveValue('');
});

test('a late earlier response cannot replace the latest page', async () => {
  const first = deferred();
  const second = deferred();
  fetchLibraryPage.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  render(<LibraryPage />);
  fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
  fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
  fireEvent.click(screen.getByRole('button', { name: /aktualisieren/i }));
  await act(async () => second.resolve(page([item('lib_new', 'Neuer Stand.mp3')])));
  expect(await screen.findByText('Neuer Stand.mp3')).toBeInTheDocument();
  await act(async () => first.resolve(page([item('lib_old', 'Alter Stand.mp3')])));
  expect(screen.queryByText('Alter Stand.mp3')).not.toBeInTheDocument();
  expect(screen.getByText('Neuer Stand.mp3')).toBeInTheDocument();
});

test('an old request cannot restore data after forgetting and opening a new code', async () => {
  const oldRequest = deferred();
  const newRequest = deferred();
  fetchLibraryPage.mockResolvedValueOnce(page([item('lib_first', 'Vorher geladen.mp3')]))
    .mockReturnValueOnce(oldRequest.promise)
    .mockReturnValueOnce(newRequest.promise);
  render(<LibraryPage />);
  fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
  fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
  expect(await screen.findByText('Vorher geladen.mp3')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /aktualisieren/i }));
  fireEvent.click(screen.getByRole('button', { name: /zugang vergessen/i }));
  expect(screen.getByLabelText(/zugangscode/i)).toHaveValue('');
  fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
  fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
  await act(async () => newRequest.resolve(page([item('lib_new', 'Neu freigegeben.mp3')])));
  expect(await screen.findByText('Neu freigegeben.mp3')).toBeInTheDocument();
  await act(async () => oldRequest.resolve(page([item('lib_old', 'Alte Freigabe.mp3')])));
  expect(screen.queryByText('Alte Freigabe.mp3')).not.toBeInTheDocument();
  expect(screen.getByText('Neu freigegeben.mp3')).toBeInTheDocument();
});

test('unmount aborts the pending request and removes the secret-bearing view', async () => {
  let receivedSignal;
  fetchLibraryPage.mockImplementation((_code, _cursor, signal) => {
    receivedSignal = signal;
    return new Promise(() => {});
  });
  const view = render(<LibraryPage />);
  fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
  fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
  expect(receivedSignal).toBeInstanceOf(AbortSignal);
  view.unmount();
  expect(receivedSignal.aborted).toBe(true);
});

test('network and service failures use fixed safe messages', async () => {
  fetchLibraryPage.mockRejectedValue(new Error('secret echoed by server'));
  openLibrary();
  expect(await screen.findByRole('alert')).toHaveTextContent(/nicht erreichbar|erneut versuchen/i);
  expect(screen.queryByText(/secret echoed/i)).not.toBeInTheDocument();
});

test('the real client sends one relative, non-persistent, abortable GET', async () => {
  const signal = new AbortController().signal;
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => page([item('lib_safe', 'Titel.mp3')], 'lib_safe'),
  });
  try {
    await expect(realFetchLibraryPage(CODE, 'lib_cursor', signal)).resolves.toEqual(
      page([item('lib_safe', 'Titel.mp3')], 'lib_safe'),
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/library/media?limit=20&cursor=lib_cursor');
    expect(options).toMatchObject({
      method: 'GET',
      headers: { Authorization: `Bearer ${CODE}` },
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      signal,
    });
    expect(url).not.toContain(CODE);
  } finally {
    global.fetch = originalFetch;
  }
});

test('the real client rejects bad local input and closed-schema violations safely', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn();
  try {
    await expect(realFetchLibraryPage(`${CODE}!`, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'INVALID_CREDENTIAL' });
    expect(global.fetch).not.toHaveBeenCalled();
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [item('lib_unsafe', 'Titel.mp3'), item('lib_unsafe', 'Duplikat.mp3')],
        nextCursor: 'lib_unsafe',
        privateDebug: 'must not leak',
      }),
    });
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(global.fetch.mock.calls[0][0]).toBe('/api/library/media?limit=20');
  } finally {
    global.fetch = originalFetch;
  }
});

test('the real client accepts UNKNOWN availability as a valid row', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => page([item('lib_unknown', 'Noch nicht geprüft.mp3', 'UNKNOWN')]),
  });
  try {
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .resolves.toEqual(page([item('lib_unknown', 'Noch nicht geprüft.mp3', 'UNKNOWN')]));
  } finally {
    global.fetch = originalFetch;
  }
});

test.each([
  ['a duplicate identifier', page([item('lib_same', 'Eins.mp3'), item('lib_same', 'Zwei.mp3')])],
  ['an unsafe identifier', page([item('lib/unsafe', 'Titel.mp3')])],
  ['a cursor that disagrees with the last row', page([item('lib_one', 'Titel.mp3')], 'lib_other')],
  ['an invalid row shape', { items: [{ libraryId: 'lib_one', displayName: 'Titel.mp3' }], nextCursor: null }],
  ['an unrecognized list field', { ...page([item('lib_one', 'Titel.mp3')]), privateDebug: 'hidden' }],
])('the real client rejects %s independently', async (_label, body) => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body });
  try {
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  } finally {
    global.fetch = originalFetch;
  }
});

test('the real client rejects an unparsable response body without exposing it', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => { throw new Error('raw secret payload'); },
  });
  try {
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  } finally {
    global.fetch = originalFetch;
  }
});

test('the real client hides fetch rejection details', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn().mockRejectedValue(new TypeError('secret network detail'));
  try {
    const error = await realFetchLibraryPage(CODE, undefined, new AbortController().signal)
      .catch((failure) => failure);
    expect(error).toBeInstanceOf(Error);
    expect(error.message).not.toContain('secret network detail');
  } finally {
    global.fetch = originalFetch;
  }
});

test('the real client turns unauthorized and service responses into fixed errors', async () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ secret: 'do not show' }) })
    .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ secret: 'do not show' }) });
  try {
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'UNAUTHORIZED' });
    await expect(realFetchLibraryPage(CODE, undefined, new AbortController().signal))
      .rejects.toMatchObject({ code: 'SERVICE_UNAVAILABLE' });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  } finally {
    global.fetch = originalFetch;
  }
});

test('the component aborts at the ten second deadline and leaves a safe error', async () => {
  jest.useFakeTimers();
  let signal;
  fetchLibraryPage.mockImplementation((_code, _cursor, requestSignal) => {
    signal = requestSignal;
    return new Promise((_resolve, reject) => {
      requestSignal.addEventListener('abort', () => {
        reject(Object.assign(new Error('aborted request'), { name: 'AbortError' }));
      }, { once: true });
    });
  });
  try {
    render(<LibraryPage />);
    fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
    fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
    expect(screen.getByRole('status')).toBeInTheDocument();
    await act(async () => { jest.advanceTimersByTime(10000); });
    expect(screen.getByRole('alert').textContent.trim().length).toBeGreaterThan(0);
    expect(screen.queryByText('aborted request')).not.toBeInTheDocument();
    expect(signal.aborted).toBe(true);
    expect(jest.getTimerCount()).toBe(0);
  } finally {
    jest.clearAllTimers();
    jest.useRealTimers();
  }
});

test('a completed component request clears its deadline timer', async () => {
  jest.useFakeTimers();
  fetchLibraryPage.mockResolvedValue(page([item('lib_done', 'Erledigt.mp3')]));
  try {
    render(<LibraryPage />);
    fireEvent.change(screen.getByLabelText(/zugangscode/i), { target: { value: CODE } });
    fireEvent.click(screen.getByRole('button', { name: /bibliothek öffnen/i }));
    await act(async () => {});
    expect(screen.getByText('Erledigt.mp3')).toBeInTheDocument();
    expect(jest.getTimerCount()).toBe(0);
  } finally {
    jest.clearAllTimers();
    jest.useRealTimers();
  }
});
