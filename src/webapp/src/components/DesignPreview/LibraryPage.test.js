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
