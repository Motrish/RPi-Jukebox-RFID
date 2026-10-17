import React, { useEffect, useRef, useState } from 'react';

import { fetchLibraryPage } from './libraryClient';

const TIMEOUT_MS = 10000;
const UNSAFE_CODE_CHARACTER = /[^A-Za-z0-9_-]/;
const EMPTY_PAGE = { items: [], nextCursor: null };

const ERROR_MESSAGES = {
  INVALID_CREDENTIAL: 'Der Zugangscode muss aus 43 URL-sicheren Zeichen bestehen.',
  INVALID_CURSOR: 'Die angeforderte Seite ist ungültig. Bitte aktualisieren.',
  INVALID_RESPONSE: 'Die Bibliotheksantwort konnte nicht gelesen werden.',
  SERVICE_UNAVAILABLE: 'Die Bibliothek ist vorübergehend nicht erreichbar. Bitte erneut versuchen.',
  NETWORK_ERROR: 'Die Bibliothek ist nicht erreichbar. Bitte Verbindung prüfen und erneut versuchen.',
  REQUEST_FAILED: 'Die Bibliothek konnte nicht geladen werden. Bitte erneut versuchen.',
};

function fixedError(error) {
  if (error?.code === 'UNAUTHORIZED') {
    return 'Der Zugangscode ist abgelaufen. Bitte erneut freigeben.';
  }
  return ERROR_MESSAGES[error?.code] || 'Die Bibliothek konnte nicht geladen werden. Bitte erneut versuchen.';
}

function Availability({ value }) {
  const labels = {
    AVAILABLE: 'Vorhanden',
    MISSING: 'Fehlt',
    UNKNOWN: 'Unbekannt',
  };
  return (
    <span className={`library-availability library-availability-${value.toLowerCase()}`}>
      <span className="library-availability-dot" aria-hidden="true" />
      {labels[value]}
    </span>
  );
}

export default function LibraryPage() {
  const [code, setCode] = useState('');
  const [authorizedCode, setAuthorizedCode] = useState('');
  const [page, setPage] = useState(EMPTY_PAGE);
  const [cursorHistory, setCursorHistory] = useState([undefined]);
  const [pageIndex, setPageIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const generation = useRef(0);
  const activeRequest = useRef(null);
  const mounted = useRef(false);
  const headingRef = useRef(null);
  const codeInputRef = useRef(null);
  const focusCodeInput = useRef(false);

  useEffect(() => {
    if (!authorizedCode && focusCodeInput.current && codeInputRef.current) {
      codeInputRef.current.focus();
      focusCodeInput.current = false;
    }
  }, [authorizedCode]);

  function abortActiveRequest() {
    const request = activeRequest.current;
    if (!request) return;
    window.clearTimeout(request.timer);
    request.controller.abort();
    activeRequest.current = null;
  }

  function forgetAccess(message = '') {
    generation.current += 1;
    abortActiveRequest();
    setCode('');
    setAuthorizedCode('');
    setPage(EMPTY_PAGE);
    setCursorHistory([undefined]);
    setPageIndex(0);
    setLoading(false);
    setErrorMessage(message);
    focusCodeInput.current = true;
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
      const request = activeRequest.current;
      if (request) {
        window.clearTimeout(request.timer);
        request.controller.abort();
        activeRequest.current = null;
      }
    };
  }, []);

  async function requestPage(requestCode, cursor, requestedPageIndex, requestedHistory) {
    abortActiveRequest();
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    const controller = new AbortController();
    const request = { controller, timer: null };
    request.timer = window.setTimeout(() => {
      if (generation.current !== requestGeneration) return;
      generation.current += 1;
      activeRequest.current = null;
      controller.abort();
      setLoading(false);
      setErrorMessage('Die Anfrage dauerte zu lange. Bitte erneut versuchen.');
    }, TIMEOUT_MS);
    controller.signal.addEventListener('abort', () => window.clearTimeout(request.timer), { once: true });
    activeRequest.current = request;
    setLoading(true);
    setErrorMessage('');

    try {
      const result = await fetchLibraryPage(requestCode, cursor, controller.signal);
      if (!mounted.current || generation.current !== requestGeneration) return;
      setPage(result);
      setPageIndex(requestedPageIndex);
      setCursorHistory(requestedHistory);
      setLoading(false);
    } catch (failure) {
      if (!mounted.current || generation.current !== requestGeneration) return;
      if (failure?.code === 'UNAUTHORIZED') {
        forgetAccess(fixedError(failure));
        return;
      }
      setErrorMessage(fixedError(failure));
      setLoading(false);
    } finally {
      window.clearTimeout(request.timer);
      if (activeRequest.current === request) activeRequest.current = null;
    }
  }

  function submitCode(event) {
    event.preventDefault();
    if (code.length !== 43 || UNSAFE_CODE_CHARACTER.test(code)) {
      setErrorMessage(ERROR_MESSAGES.INVALID_CREDENTIAL);
      return;
    }
    setAuthorizedCode(code);
    setCode('');
    requestPage(code, undefined, 0, [undefined]);
    headingRef.current?.focus();
  }

  function refresh() {
    if (!authorizedCode) return;
    requestPage(authorizedCode, undefined, 0, [undefined]);
  }

  function goToPage(nextIndex, nextCursor, history) {
    if (loading || !authorizedCode) return;
    requestPage(authorizedCode, nextCursor, nextIndex, history);
  }

  const hasPrevious = pageIndex > 0;
  const hasNext = page.nextCursor !== null && page.items.length > 0;

  return (
    <section className="library-page" aria-labelledby="library-title" aria-busy={loading}>
      <div className="library-heading">
        <div>
          <p className="eyebrow section-eyebrow">EURE DATEIEN</p>
          <h1 id="library-title" ref={headingRef} tabIndex={-1}>Bibliothek</h1>
        </div>
        {authorizedCode && <div className="library-heading-actions">
          <button className="text-button library-refresh" type="button" onClick={refresh}>Aktualisieren</button>
          <button className="button-secondary library-forget" type="button" onClick={() => forgetAccess()}>
            Zugang vergessen
          </button>
        </div>}
      </div>
      <p className="library-intro">Durchsuche den vorhandenen Musikkatalog. Es werden keine Dateien verändert.</p>

      {!authorizedCode && (
        <form className="library-access" onSubmit={submitCode}>
          <label htmlFor="library-access-code">Zugangscode</label>
          <p id="library-access-help">Gib den bereitgestellten Zugangscode ein, um den Katalog zu öffnen.</p>
          <div className="library-access-row">
            <input
              id="library-access-code"
              ref={codeInputRef}
              aria-describedby="library-access-help"
              type="password"
              autoComplete="off"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
            <button className="library-primary-button" type="submit">Bibliothek öffnen</button>
          </div>
        </form>
      )}

      {loading && <p className="library-status" role="status">Bibliothek wird geladen …</p>}
      {errorMessage && <p className="library-error" role="alert">{errorMessage}</p>}

      {authorizedCode && !loading && !errorMessage && page.items.length === 0 && (
        <div className="empty-state library-empty">
          <span className="empty-icon" aria-hidden="true">♫</span>
          <h2>Keine Titel im Katalog</h2>
          <p>Im vorhandenen Musikkatalog sind derzeit keine Titel eingetragen.</p>
        </div>
      )}

      {authorizedCode && page.items.length > 0 && (
        <>
          <div className="library-list-heading">
            <p>Einträge aus dem Musikkatalog</p>
          </div>
          <ul className="library-list" aria-label="Titel im Musikkatalog">
            {page.items.map((item) => (
              <li className="library-row" key={item.libraryId}>
                <span className="library-row-icon" aria-hidden="true">♫</span>
                <span className="library-row-copy">
                  <span className="library-title-text">{item.displayName}</span>
                  <span className="library-id">{item.libraryId}</span>
                </span>
                <Availability value={item.availability} />
              </li>
            ))}
          </ul>
        </>
      )}
      {authorizedCode && (
        <nav className="library-pagination" aria-label="Katalogseiten">
          <button className="button-secondary" type="button" disabled={!hasPrevious || loading}
            onClick={() => goToPage(pageIndex - 1, cursorHistory[pageIndex - 1], cursorHistory.slice(0, pageIndex))}>Zurück</button>
          <span>Seite {pageIndex + 1}</span>
          <button className="button-secondary" type="button" disabled={!hasNext || loading}
            onClick={() => goToPage(pageIndex + 1, page.nextCursor, [...cursorHistory.slice(0, pageIndex + 1), page.nextCursor])}>Weiter</button>
        </nav>
      )}
      {!authorizedCode && errorMessage && (
        <div className="library-error-actions">
          <button className="button-secondary" type="button" onClick={() => setErrorMessage('')}>Schließen</button>
        </div>
      )}
      {authorizedCode && page.items.length === 0 && !loading && errorMessage && (
        <div className="library-error-actions">
          <button className="button-secondary" type="button" onClick={refresh}>Erneut versuchen</button>
        </div>
      )}
    </section>
  );
}
