# U03a2 – echte Bibliothek in der Reactoberfläche

Basis: future3/modern-ui 769a46a31a1fbc423fae4bdda1f78beda6b02ec5, Treee852667f70781399948ce3fbc76a8f8b7fa8af33. Autor ausschließlich Luna, Root/Sol ausschließlich Koordination, Prosa, Review und mechanische Publikation. Kein Astra. Isolierter Teilstage G:/Entwicklung/phoniebox-staging/u03-library-ui; kein lokaler Vollcheckout verfügbar. Root führt die einzige operative Liste tasks/todo.md weiter, statt eine zweite SDD-Liste anzulegen. Vorhandene Nutzerfreigabe zur Entwicklung und nächste-Schritte-Auftrag decken diesen beschriebenen Slice und spätere Integration im bestehenden Featurebranch ab.

## Ergebnis und Gestaltung

Neue Route #/design-preview/library und Menüpunkt Bibliothek im Musikbereich der vorhandenen dunklen Shell. Bestehende sieben Vorschauseiten und ihre Browserabnahme erhalten. Musik bleibt die bisherige Beispielsammlung, der neue Menüpunkt ist der echte Katalog. Im neuen Bereich sagt das bestehende Vorschauhinweisband ausdrücklich, dass Player und Gerätestatus Vorschau sind; Dateien stammen aus dem Katalog. Kein neuer Vollbildentwurf, keine andere Farbwelt, kein wirkender Playbutton/Resolver/Upload/Scanner. Bestehende globale Beispielsuchbox auf der echten Bibliotheksroute ausblenden; keine vorgetäuschte Serversuche. Mobile Menüführung und Tastatur bleiben nutzbar.

Bibliotheksseite mit einer h1, kurzem Zugangscodeformular, echtem Lade-/Leer-/Fehlerzustand, bis20 Einträgen pro Seite und Vor/Zurück; Seitenzahl ohne erfundene Gesamttitelzahl. Titel als Text, vollständige opaque libraryId zur Unterscheidung gleicher Namen, textuelle Verfügbarkeit Vorhanden/Fehlt/Unbekannt neben Farbe/Icon. Lange Namen/IDs umbrechen. Kein dangerouslySetInnerHTML. Bei leerem Katalog hilfreicher Hinweis, keine Fakeeinträge. Aktualisieren beginnt wieder auf der ersten Seite. Freigabe vergessen leert Code und alle Katalogdaten und bringt das Formular zurück; nach401 dasselbe mit fester verständlicher Meldung. Route verlassen/unmount leert den zugangshaltenden Componentzustand und bricht Requests ab.

## Datenfluss und Grenzen

Ein kleiner Client holt ausschließlich relative GET /api/library/media?limit=20 mit optional einem bereits validierten A02cursor. Authorization Bearer, credentials omit, cache no-store, redirect error und AbortSignal. Code exakt43 ASCII-URLsafezeichen, nie URL/Cookie/Storage/Konsolen-/Fehlertext. Passwortfeld mit Label, keine Secretanzeige. Vor Öffnen keine APIanfrage. Keine Polling-/automatische Retryschleife, keine Legacycontexts oder WebSockets. Browser hält maximal aktuelle Seite plus Cursorhistorie, keine Sammlungscachekopie.

Geschlossene Liste/Zeilen/Cursorformen wie U03a1 prüfen und feste sichere UIfehler für401,503/Netz, falsches JSON/Schema anzeigen; keine Rawantwort oder exception.message übernehmen. Doppelte/unsichere IDs und widersprüchliche Cursor sind Fehler. UNKNOWN als gültiger Status erhalten. Ein ausstehender Abruf kann nach neuem Code, Vergessen, Seitenwechsel, Unmount oder späterem Request keine Daten wieder einsetzen. AbortController plus Generation oder gleichwertig. Endlicher Browserrequesttimeout10s und dessen Cleanup; kein behaupteter Abbruch des Backenddateisystems. Statusmeldungen per role status/alert, sinnvolle Fokusführung, native Buttons/Formsubmit.

## Genau sieben ausführbare Pfade

1. src/webapp/src/components/DesignPreview/index.js – minimale Navigation/Route/Hinweisband/Suchboxintegration.
2. src/webapp/src/components/DesignPreview/styles.css – ausschließlich scoped Bibliotheksstyles mit bestehenden Tokens/Abständen.
3. src/webapp/src/components/DesignPreview/LibraryPage.js – neue echte Bibliotheksansicht, kleine lokale Darstellungskomponenten bei Bedarf.
4. src/webapp/src/components/DesignPreview/libraryClient.js – enger relativer GETclient und sichere Antwortvalidierung.
5. src/webapp/src/components/DesignPreview/LibraryPage.test.js – Client-/Componentverhalten mit vorhandener ReactTestingLibrary/Jest.
6. tests/design-preview/library_smoke.py – gerätefreier Linux-Browserharness mit echtem Katalog und API.
7. .github/workflows/test_build_webapp_v3.yml – vorhandenen Webworkflow um gezielte Jest- und begrenzte Bibliotheksbrowserabnahme erweitern; alle bestehenden Prüfungen erhalten.

Keine anderen Projektdateien, Dependencies/Lockfiles, API-/Katalog-/Contractquellen, Geräteservices oder nginxkonfiguration ändern. Keine neuen Frameworks. Quellen für diesen Slice begrenzen: vorhandene App/Previewindex/Styles, Webworkflow, alter Reactharness, package.json sowie API-/Katalog-/Identifiergrenze. Umfangserweiterung erst Root mit konkretem Befund vorlegen, nicht still Dateien hinzufügen.

## Beweise vor Integration

Phase1 nur LibraryPage.test.js, library_smoke.py und Workflow erstellen/ändern, beide neuen Produktmodule bleiben abwesend und Index/Styles unverändert. Tests reale Verhaltensgrenzen: kein Abruf vor Code, relative sichere GETs/geschlossene Projektion/Fehler, gültige Daten/Leer, gleiche Titel mit unterschiedlichen IDs, Vor/Zurück/Aktualisieren,401 löscht Berechtigung+Daten, Vergessen/Unmount/neuester Request gewinnt, Timeout-/Abortcleanup. Ein Test darf nicht bloß Helperimplementierung spiegeln. Erst Freeze, Review und tatsächlicher CI-RED am fehlenden Modul vor Phase2. Build muss vor diesem RED laufen; bestehende Vertragsprüfungen bleiben erhalten. Root publiziert die exakten sieben Whitelistpfade, keine Cache-/Seeddateien.

Browserharness nur für Tests: 127.0.0.1, ephemere Ports, vertrauenswürdiger fester CRA-Buildroot mit beim Start aus Builddateien erstellter Assetallowlist, kein allgemeiner vom HTTPpfad gesteuerter Directorywalker. Eigener fester Loopback-Proxy zu genau der injizierten APIadresse. Eingehende Hostauthority und Origin fehlen/entsprechen exakt der äußeren Testorigin; fremde/mehrfache Werte vor Weiterleitung ablehnen. Erst danach Host und gegebenenfalls Origin auf die feste Backendauthority umschreiben; kein Forwardedvertrauen/CORS/Querytoken. Nur die feste GET-APIroute und feste Assetliste; keine HTTP-Testkontroll-, Import- oder Adminroute. Kein Proxyziel aus einem Request. Zugriff auf Serverfixtures ausschließlich über den Pythonharness. Alle Listener/Threads/Browser/Tempdaten finally schließen; Standardtesttimeout und CIstepdeadline3min.

Echte Linux-Temporärdateien (mindestens21, einschließlich gleicher Basenamen in zwei Unterordnern, Unicode/lange Namen; eine nach Register entfernte Datei), echter LibraryCatalog und echtes make_server/make_read_authorizer mit festem synthetischem Testcode. Keine echten Credentials in Toolausgaben. Erfolgs-/Pagingpfad muss echte Browserrequests über dieselbe Origin bis zum echten Katalog nachweisen. Zusätzliche kontrollierte Leer-/401-/503-/Malformed-/Verzögerungsfälle dürfen Fixture-/Fetchkontrolle nutzen und sind als solche auszuweisen. Keine Erfolgsabnahme ausschließlich mit page.route oder Fakekatalog. Keine Registry-/Geräte-/Systemänderung und kein Audio-/ARMv6-Nachweis aus diesen Dateien.

Chromium prüft Katalogabruf, gleiche Titel per ID, Paging, MISSING,404-/401-/503-/Leer-/Loadingverhalten soweit jeweilige UIroute vorhanden, Codeverlust nachReload/Routewechsel/Vergessen, verspäteten alten Request und keinerlei Wiederauftauchen nach Verlust. Browsernetz erlaubt ausschließlich lokale Buildassets und GET /api/library/media; unerwartete Origins/API-/Legacy-/Socketaufrufe scheitern. Keine Secrets in Reports/Screenshots/URLs; Testcode nur Passwortfeld/synthetische Header. Zustand mit geöffnetem Codeformular kann ohne eingegebenen Wert fotografiert werden. Screenshots Desktop1440 und Mobil390, Überlauf zusätzlich320/768/1024 prüfen; Tastaturformular und mobiles Menü. Fehlertests dürfen erwartete HTTPfehlermeldungen nicht mit unerwarteten JSfehlern verwechseln. PNG für Root-Sichtprüfung als begrenzter markierter Base64log oder abrufbares Artefakt, kein reines Dateipfadscreenshotversprechen.

Final: unveränderte bisherigen Web-/Jest-/Chromiumprüfungen plus neue echte Bibliotheksabnahme, volle Python3.9–3.13/Lint bei geändertem Pythonharness, serielles unabhängiges Source-/Gesamtänderungsreview, genaue SHAs und Remote-Readback. Nur danach Integration in future3/modern-ui. Kein LAN-/nginx-/HTTPS-/Produktauth- oder Gerätepass: Testproxy belegt Same-origin-Browserlogik, der vorhandene nginxanschluss folgt separat.

## Root-Abgleich und Rulings

| Producer/Consumer | Abgleich |
| --- | --- |
| U03a1 API / Client | Feldform, limit20, A02cursor,43Zeichen-Bearer und401 stimmen; keine Detail-/Resolveverwendung nötig. |
| Shell / LibraryPage | Neue Route statt Ersatz bestehender Demomusik vermeidet Regressionen; Hinweisband begrenzt Simulationsaussage auf Player/Gerät. |
| Client / Race-Tests | Abbruch und Generationsschutz müssen alte Antworten und Zeitablauf abfangen, nicht nur neue Fetchaufrufe zählen. |
| Proxy / API Host-Origin | Äußere Origin prüfen, dann feste Backendwerte; einfacher ungeprüfter Originrewrite wäre falsch. |
| Harness / CI | Echte Linuxdateien+Katalog statt Windowsfiktion; bestehender Browserharness bleibt unverändert. |

Ruling: Der neue Menüpunkt ergänzt den vorhandenen freigegebenen Entwurf, statt einen zweiten entwurfsfremden Vollbildclient zu erzeugen. Risiko bei falscher Auswahl: reversibler späterer Shellumbau, kein Gerätedatenverlust. Bestehende Nutzerfreigabe zur Softwareentwicklung gilt; keine erneute Bestätigung für routinemäßige Interfaceentscheidungen. Isolierter APIbasierter Stage ersetzt bis zum zulässigen Vollcheckout die nicht ausführbare lokale Worktree-/SDD-Shellautomation; Status ausschließlich im vorhandenen todo.md. Root genehmigt Phase1 in dieser Grenze.
