# P01a – vorgeschlagene transportfreie LOCAL-Providergrenze

Stand: 16.10.2026. Konzeptauftrag, **keine Coderfreigabe**. Neue Bezeichner und Modulpfade in diesem Dokument sind Vorschläge; es werden keine vorhandenen Klassen oder fertigen Resolver behauptet. Kein Code, Schema, Test oder Runtimeanschluss durch Sol.

## Gegenstand und gepinnter Bestand

Quellbasis: V3.6.0 `4fa84fd50750fd4b52984d51aa7c95466cf5b241`, insbesondere `src/jukebox/components/playermpd/__init__.py` (Blob `86dbc60ab1412c4957857416fe2ff9115d2b7185`), `components/player/__init__.py` und `resources/default-settings/mpd.default.conf`. Dateien wurden am Commit gelesen. Aktuelle Store-/Contractarbeit ersetzt diese Bestandsschnittstellen nicht.

| Bestehender Einstieg | Tatsächliches Verhalten | Konsequenz für die Grenze |
| --- | --- | --- |
| `PlayerMPD.__init__`, connect | Erzeugt MPDClient, verbindet mit Host/6600, setzt timeout und idletimeout auf None und startet 250-ms-Poller. Initialisierung kann eine vorhandene Queue löschen. | Keine zweite PlayerMPD-Instanz zur Adaptererzeugung. Ein Import-/Fakekonstruktor darf keinen Client, Timer oder Dienst starten. |
| MpdLock | Reentrant-Lock um denselben Client; Eintritt versucht connect, ConnectionError wird abgefangen. | Bestehende Sperre teilen. Verbindungswechsel muss künftig sichtbar sein; stilles Reconnect ist kein Ausführungsnachweis. |
| play_single | Unter Sperre clear, addid, play; Rückgabe von addid wird verworfen. | Für eine korrelierte Ausführung braucht die interne Bindung die tatsächliche MPD-ID und bewusst gesetzte Optionen. Name play_single allein garantiert keinen abgesicherten Einzeltrackmodus. |
| play_folder / play_album | Befüllt mehrere MPD-Einträge und startet die MPD-Queue. | Nicht als Providerstart einer zentralen Einzelausführung verwenden. |
| play / pause / toggle | play startet die ausgewählte MPD-Queue; pause kann explizit 1/0 erhalten; toggle lässt MPD umschalten. | Provider nutzt explizite Zielzustände statt Toggle und unterscheidet Wiederaufnahme von neuem Start. |
| resume | Liest CURRENTSONGPOS/ELAPSED aus Ordnerstatus, führt seek und play aus. | Das ist kein positionsbewahrendes Resume derselben Providerexecution. Nicht ungeprüft delegieren. |
| stop | Führt MPD-stop unter Sperre aus, liefert keine anschließende Zustandsprüfung. | Erfolgreicher Methodenaufruf allein ist kein bestätigter Anbieterstop. |
| seek | Delegiert auf seekcur; Einheit im Wrapper nicht typisiert. | Providergrenze nimmt absolute Millisekunden und bindet die Aktion an die aktuelle executionId. |
| shuffle / _repeatmode | Setzt MPD-random. Repeatmodus setzt repeat=1/single=0; Einzelwiederholung repeat=1/single=1; disable beide 0. | Diese Legacy-Schreiber dürfen den zentral kontrollierten Einzeltrackmodus nicht parallel umstellen. |
| _mpd_status_poll / playerstatus | status und currentsong werden getrennt gelesen und in wiederverwendetes Cache-Dict gemischt; playerstatus liefert dieses Dict. | Für neue Bestätigungen frisch und korreliert lesen; Cache kann alt oder gemischt sein. |
| mpd_retry_with_mutex | Tatsächlicher Code fängt Fehler ab und liefert None; der Kommentar kündigt Wiederholungen an, die dort nicht implementiert sind. | Keine Retry-/Bestätigungsgarantie aus dem Namen ableiten. |
| components.player | Liest music_directory aus MPD-Konfiguration; kein libraryId→Medium-Katalog. | Ein vertrauenswürdiger LibraryResolver existiert damit noch nicht. |

Defaultkonfiguration: MPD bindet localhost/6600 und speichert eigenen State. Audio ist ALSA mit device/mixer_device pulse; ein direkter Pulse-Ausgabepluginblock ist nur auskommentiert. Das konkrete Zielgerät kann abweichen. Eine MPD-State-Datei und externe lokale mpc-Aufrufer gehören zum späteren Wiederanlauf-/Hoheitstest.

Quellen: [PlayerMPD](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/playermpd/__init__.py), [Bibliothekspfadhelfer](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/player/__init__.py), [MPD-Konfiguration](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/resources/default-settings/mpd.default.conf).

## Protokolleinordnung

MPD unterscheidet seine laufende Queue von gespeicherten Playlists. Song-IDs sind innerhalb einer MPD-Laufzeit stabiler als Positionen, überstehen aber keinen MPD-Neustart. single=1 stoppt am Titelende nur ohne eingeschaltetes repeat; repeat zusammen mit single wiederholt denselben Titel. Die neue zentrale Queue darf daher MPDs Wiederholung nicht mitbenutzen. Status kann Werte auslassen. Ein Verbindungsabbruch beweist weder Stopp noch natürliches Ende. [Offizielles MPD-Protokoll](https://mpd.readthedocs.io/en/stable/protocol.html).

Die Pythonbibliothek bietet dafür ID-basierte Start-/Seekaktionen, explizites Pause/Resume sowie Queue-/Statusabfragen. Die offizielle Dokumentation wurde als Protokollreferenz gelesen; auf der Box installierte Version und freigegebene Befehle sind noch zu prüfen. [python-mpd2-Kommandos](https://python-mpd2.readthedocs.io/en/latest/topics/commands.html).

## P01a1 – vier vorgeschlagene Dateien, weiterhin keine Coderfreigabe

Der erste Slice enthält nur einen synchronen, transportfreien LocalProvider gegen injizierte Fakes. Vorgeschlagene neue Dateien: `src/jukebox/components/local_provider/__init__.py`, `src/jukebox/components/local_provider/adapter.py`, `test/local_provider/test_adapter.py` und `test/local_provider/fixtures/v1.json`. Fakeklassen bleiben in der Testdatei. Root legt diese Namen im Luna-Briefing verbindlich fest. Keine bestehende MPD-/Plugin-/RPC-/Service-/Timeoutdatei wird geändert, kein reales Gateway implementiert.

Kein zusätzlicher Player, MPDClient, Daemon, Eventthread, Pollingloop, Scheduler oder SQLiteledger. P04 besitzt Generation, Befehlsserialisierung und Nachfolgerwahl. Die nachfolgenden Bezeichnungen beschreiben ausschließlich die vorgeschlagene Python-API; Sol schreibt keine ausführbaren Interfaces oder Schemas.

## Feste injizierte Formen

LocalProvider erhält ausschließlich session, resolver, monotonic und capabilities. Konstruktion importiert/öffnet kein reales PlayerMPD und liest weder MPDkonfiguration noch Bibliothek. Vorgeschlagene Pythonmethoden sind start, pause, resume, seek, stop und observe; ihre Belegwerte sind entsprechend START, PAUSE, RESUME, SEEK, STOP und OBSERVE. Jede Methode bekommt lease und deadline; start zusätzlich media_ref als validierte LOCAL-MediaRef, seek zusätzlich position_ms mit der unten beschriebenen positionMs-Semantik. Dies sind vorgeschlagene APIoperationen, keine RPCmethoden.

| Form | Exakter Inhalt / Verantwortung |
| --- | --- |
| ExecutionIdentity | Geschlossene Felder bootId, generation, executionId, entryId. IDs verwenden die A02-Tokenregel; generation ist echte nichtnegative Ganzzahl bis 9007199254740991. Keine MPD-ID in diesen Feldern. |
| Lease | identity plus guard. guard ist ein injizierter vertrauenswürdiger Callable mit logischer Operation und derselben identity als Argumenten; Ergebnis ist genau Boolean. Er erzeugt keine neue Generation und besitzt keine eigene Queue. |
| Capabilities | Geschlossene Booleanfelder canPause, canResume, canSeek, canConfirmStop, canIdentifyNaturalEnd. Im P01a1-Fakeprofil muss canIdentifyNaturalEnd false bleiben. Start erfordert canConfirmStop true; sonst keine MPDmutation. Reale Fähigkeitsfreigabe wird daraus nicht abgeleitet. |
| Resolver | resolve erhält genau die bereits validierte libraryId und liefert entweder null für nicht verfügbar oder ein geschlossenes Objekt mit libraryId und mpdReference. libraryId muss der angefragten ID entsprechen; mpdReference ist eine nichtleere autorisierte relative MPD-Bibliotheksreferenz, ohne NUL/CR/LF, freie URL oder absolute Pfadangabe. |
| Session | transaction erhält genau die absolute deadline und liefert einen exklusiven Kontext. Warten auf dessen Sperre sowie alle I/O müssen dieselbe echte Frist einhalten. Der Kontext stellt epoch, die unten begrenzten Protokolloperationen und keine automatische Startwiederholung bereit. |
| monotonic | Injizierter Callable ohne Argumente, liefert eine endliche monotone Sekundenzeit. Er verwendet dieselbe Uhrbasis wie session.transaction. Keine UTC-/Wandzeit für Fristen. |

Resolverautorisierung einschließlich freigegebenem Musikroot, Symlinkgrenze, tatsächlicher Datei und libraryId-Katalog ist eine **fehlende reale Abhängigkeit**. P01a1 verwendet nur im Speicher liegende synthetische Zuordnungen. Ein syntaktisch plausibler Resolverwert beweist keine Dateiberechtigung; der Adapter ersetzt diese Verantwortung nicht durch ein zweites Verzeichnis-Scanning. Resolvernull ergibt MEDIA_UNAVAILABLE; Exception oder falsche Antwortform ergibt RESOLUTION_FAILED, ohne MPDeffekt. Auch nach Resolverrückkehr wird die Frist erneut geprüft. Ein blockierender realer Resolver wäre durch diesen äußeren Check nicht sicher begrenzt und ist hier ausdrücklich nicht angebunden.

### Sessionkontext und frischer Status

Der Kontext verwendet dieselbe schon vorhandene MPD-Session/Sperre bei späterer X-Bindung; im ersten Slice ausschließlich einen Fake. epoch ist ein live lesbarer opaker A02-Token für genau eine Verbindungs-/Daemonidentität. Beim Kontexteintritt wird er festgehalten und vor/nach jedem Protokollaufruf sowie vor Belegerfolg erneut verglichen. Reconnect/Daemonneustart muss epoch ändern. Ein Wechsel bricht die Operation mit unbekanntem Ergebnis ab; ein neuer epoch darf keine alte songid übernehmen. Keine automatische Fortsetzung der angebrochenen Operation auf einer neuen Session.

Zulässige Sessionmethoden sind exakt status, clear, addid, playid, pause, seekid, stop, random, repeat, single und consume. Status/clear/stop haben keine Nutzargumente. addid erhält die autorisierte mpdReference und liefert eine nichtleere ASCII-Ziffernfolge als songid. playid erhält diese songid; pause erhält echte Ganzzahl 0 oder 1; seekid erhält songid und absolute endliche nichtnegative Sekundenposition. Optionssetter erhalten echte Ganzzahl 0 oder 1. Schreibmethoden außer addid liefern keinen zusätzlichen Nutzwert; ihre Rückkehr ist lediglich Protokollabschluss. Keine second observer callback, Shellaktion, freie MPDmethodenauflösung oder neue Verbindung.

status liefert **einen frischen normalisierten Teilstatus** aus genau einem MPDstatusread mit exakt folgenden Feldern:

| Statusfeld | Typ / Bedeutung |
| --- | --- |
| state | play, pause oder stop |
| songid | ASCII-Ziffernfolge oder null, falls MPD sie nicht liefert |
| playlistlength | Echte nichtnegative Ganzzahl |
| repeat, random | Jeweils echte Ganzzahl 0 oder 1 |
| single, consume | Echte Ganzzahl 0/1 oder der Protokollwert oneshot; Zielprofil später exakt single 1 und consume 0 |
| elapsed, duration | Jeweils endliche nichtnegative Sekunden als Zahl oder null; Boolean ist keine Zahl |
| hasError | Boolean, ob MPD einen aktuellen Fehler meldet; kein ungefilterter Fehlertext |

Alle Felder sind vorhanden, fehlende optionale MPDwerte werden null. Das ist die vorgeschlagene Session-Fakeform; der reale python-mpd2-Status enthält unter anderem Zeichenketten und weitere/fehlende Schlüssel. Eine spätere Gatewaybindung muss diese kleine Teilmenge korrekt normalisieren. Es existiert noch kein solcher Gateway. transaction bezeichnet ausschließlich die exklusive, begrenzte I/O-Klammer; MPD bietet damit keinen SQLartigen Rollback. Bereits abgeschlossene Kommandos eines fehlgeschlagenen Ablaufs bleiben mögliche Wirkung. Kein Provider darf den vorhandenen gecachten PlayerMPD.playerstatus als frischen status ausgeben. Ein zweiter currentsong-/Observationcallback ist für diesen Slice nicht nötig.

Die Session meldet erwartbare Backendfehler über den vorgeschlagenen SessionFailure mit ausschließlich code TIMEOUT, UNAVAILABLE oder COMMAND_REJECTED. Raw-ACKtexte/Dateipfade werden nicht übernommen. Unerwartete Exception ergibt sichere PROVIDER_UNAVAILABLE-Diagnose; möglicherweise begonnene Wirkung bleibt unbestätigt. Falsche Status-/songid-Form ergibt PROVIDER_STATE_MISMATCH, keinen impliziten Erfolg.

### Frist und Guard

deadline ist eine absolute endliche Sekundenzeit aus derselben monotonic-Uhr, kein relatives Timeout; Boolean ist ungültig. Eine abgelaufene Frist erlaubt keinen neuen Protokollaufruf. Die Frist wird vor/nach Resolver, Kontexteintritt, jedem Protokollaufruf und vor Erfolg geprüft. Der Sessionkontext muss lock waits und I/O selbst abbrechbar begrenzen; äußerer Futuretimeout/Timer/Thread erfüllt das ausdrücklich nicht. Die gepinnte reale Session mit timeout None ist daher noch keine zulässige Bindung.

Vor **jedem** Protokollaufruf prüft der Adapter guard mit der logischen Provideroperation und identity, epoch und Frist. False oder Guardexception bedeutet STALE_EXECUTION. Die Operation darf dann keine weiteren Protokollkommandos senden. Zusätzlich wird vor einem bestätigten Beleg erneut geprüft. Ein Guard, der während Resolver oder Start umschlägt, kann so den nächsten Schritt sperren; bereits gesendete Wirkung wird nicht wegbehauptet.

Der Operationsparameter ist nötig: P04 kann START einer überholten Generation sperren und zugleich STOP der noch reservierten alten Ausführung für die Bereinigung erlauben. Dies ist weiterhin P04s Entscheidung. Die Providerprüfung verlangt für STOP zusätzlich exakt seine noch zugeordnete identity/epoch; ein alter STOP darf deshalb nie eine neue Ausführung treffen. Ein bloßer Boolean für generation gleich aktuell würde eine nötige Bereinigung verhindern und wird nicht vorgeschlagen.

## Exakte Beleg- und Fehlerform

ProviderReceipt besitzt ausschließlich provider, operation, identity, outcome, epoch, songid, state, positionMs, durationMs, observedAtMonotonic und error. provider ist LOCAL; operation ist START/PAUSE/RESUME/SEEK/STOP/OBSERVE; identity ist das oben beschriebene Objekt. epoch/songid sind Token bzw. Ziffernfolge oder null. state ist PLAYING, PAUSED, STOPPED oder UNKNOWN. Position/Dauer sind echte nichtnegative Ganzzahlen bis 9007199254740991 in Millisekunden oder null; nicht darstellbare Statuswerte ergeben PROVIDER_STATE_MISMATCH; beobachtete Sekunden werden durch Abrunden in Millisekunden überführt. observedAtMonotonic ist die endliche Zeit einer vertrauenswürdigen frischen Beobachtung oder null. Keine UTCbehauptung und keine Queue-/Playlistrevision im Providerbeleg.

outcome ist genau CONFIRMED, REJECTED oder UNCONFIRMED. CONFIRMED verlangt error null und die für die Operation unten definierte frische Bestätigung. REJECTED bedeutet Ablehnung ohne mutierenden MPDaufruf; UNCONFIRMED bedeutet mögliche bereits eingetretene Wirkung oder nicht belastbar bestätigten Zielzustand. Beide Fehlerarme verlangen error mit den nachfolgenden Feldern. Ein frischer OBSERVE-Beleg bestätigt nur Beobachtung und kein natürliches Titelende.

ProviderError besitzt ausschließlich code, message, retryable und operation. operation entspricht dem Receipt; message ist sichere eigene Anzeigediagnose, keine Raw-Exception-/MPDantwort. retryable ist in diesem ersten Slice stets false: P04 entscheidet ausdrücklich über Wiederherstellung, der Provider startet keine Wiederholungsschleifen. Codes sind abschließend:

- STALE_EXECUTION: Guard verweigert oder wirft; keine weitere Protokollaktion.
- EXECUTION_CONFLICT: fremde identity, andere MediaRef unter derselben aktiven identity oder ungeklärte vorherige Ausführung.
- MEDIA_UNAVAILABLE / RESOLUTION_FAILED: Resolvernull bzw. Resolverfehler/falsche Antwort.
- CAPABILITY_UNAVAILABLE: angeforderte Fähigkeit oder notwendige Stopfähigkeit fehlt.
- PROVIDER_UNAVAILABLE: Session nicht erreichbar oder unerwarteter sicher abgefangener Backendfehler.
- PROVIDER_REJECTED: Session meldet COMMAND_REJECTED oder SEEK überschreitet die bekannte Dauer; kein Raw-ACK im Fehler.
- PROVIDER_STATE_MISMATCH: unpassende Queue-/songid-/State-/Statusform oder falsche bestätigte Optionen.
- OPERATION_TIMEOUT: Frist oder Session-TIMEOUT außerhalb einer Stopoperation.
- SESSION_CHANGED: epochwechsel außerhalb einer Stopoperation; alte songid invalidiert.
- STOP_UNCONFIRMED: STOP konnte wegen fehlender Zustandsbestätigung, Frist, Sessionfehler oder epochwechsel nicht bestätigt werden.

Malformed öffentliche Eingaben/Leaseidentität/Capabilities/deadline ergeben vor Providerwirkung den bestehenden ContractValidationError mit VALIDATION_ERROR; deshalb muss kein Receipt mit ungültiger identity erfunden werden. ProviderError ist ein eigener vorgeschlagener Vertrag, kein stilles Erweitern des aktuellen Store-Errorvalidators. Belege halten ausschließlich frische Beobachtungen derselben Operation und epoch; nach epochwechsel werden state UNKNOWN und die Beobachtungsfelder null. Sie werden nicht als neuer Beleg aus dem alten Playercache gebaut.

## Präzise Operationsschritte ohne interne Warteschleife

Jede Operation hat einen exklusiven Sessionkontext und höchstens einen frischen Vorstatus sowie einen Nachstatus. Es gibt keine internen Statuspolling-/Retryloops; fehlende unmittelbare Bestätigung endet sichtbar, P04 kann später einen neuen expliziten Beobachtungs-/Stopwunsch entscheiden. Alle Zwischenaufrufe unterliegen Guard, epoch und derselben deadline.

| Operation | Vorschrift / erfolgreicher Beleg |
| --- | --- |
| START | LOCAL-only, Fähigkeit/Lease/Frist/Resolver prüfen. Eine neue identity ist nur zulässig, wenn keine ungeklärte vorige Ausführung reserviert ist. Vorstatus muss stop ohne Fehler zeigen. Dann repeat(0), random(0), single(1), consume(0), clear, addid der autorisierten Referenz, playid der erhaltenen ID. Nachstatus muss play, dieselbe songid, playlistlength 1 und genau das Zieloptionsprofil ohne Fehler zeigen. Erst dann CONFIRMED/PLAYING. Kein versteckter Folder-/Albumstart. |
| Doppelter aktiver START | Gleiche identity und gleiche libraryId werden durch frischen Status ohne irgendeinen Schreibaufruf beobachtet; kein zweites addid/playid. Derselbe Inhalt ist kein Resume. Eine andere libraryId unter derselben identity ist EXECUTION_CONFLICT. Nach bestätigtem STOP ist für neuen Start eine neue identity nötig. Dauerhafte commandId-Wiederholung bleibt P04-/Ledgerverantwortung. |
| PAUSE | Aktive identity/epoch und canPause prüfen. Vorstatus muss play oder pause mit derselben songid sein. Bereits pause: bestätigter wirkungsloser Beleg. Sonst pause(1); Nachstatus pause, gleiche songid und kein Fehler ergeben CONFIRMED/PAUSED. Kein Toggle. |
| RESUME | Aktive identity/epoch und canResume prüfen. Vorstatus pause oder play mit gleicher songid. Bereits play: bestätigter wirkungsloser Beleg. Sonst pause(0); Nachstatus play, gleiche songid und kein Fehler ergeben CONFIRMED/PLAYING. stop bedeutet keine wiederaufnehmbare Ausführung; kein play/Queue-Neuaufbau/Ordner-JSON-Resume. |
| SEEK | Aktive identity/epoch, canSeek und positionMs prüfen. Position ist echte nichtnegative Ganzzahl bis 9007199254740991; bei bekannter Dauer darf sie diese nicht überschreiten. Vorstatus play/pause mit gleicher songid. seekid erhält diese ID und absolute Sekunden. Nachstatus muss gleiche songid und denselben play-/pause-Zustand ohne Fehler zeigen; Receipt meldet die frisch beobachtete Position, keine erfundene exakte hörbare Millisekundenpräzision. |
| STOP | identity muss zur noch zugeordneten lokalen Ausführung gehören (einschließlich terminalem Stop bis zum nächsten Start); canConfirmStop und epoch prüfen. Frischer Vorstatus stop ohne Fehler ist bereits Bestätigung, auch wenn MPD keine songid mehr liefert. Sonst muss die laufende songid zur Ausführung passen; stop senden, Nachstatus stop ohne Fehler und stabiler epoch ergeben CONFIRMED/STOPPED. Erst dieser Erfolg löst die Reservierung für einen neuen Start. Protokoll-ACK allein genügt nicht. Fremde laufende songid wird nicht durch einen alten Stop angefasst. |
| OBSERVE | Zur noch zugeordneten identity genau einen frischen status lesen; keine Schreibaktion. Bei play/pause muss songid zur Zuordnung passen. stop bestätigt nur STOPPED-Beobachtung, nicht Ursache oder natürliche Beendigung; ein ungeklärter Vorgang wird dadurch nicht automatisch als erfolgreicher Stopauftrag umgeschrieben. |

Nach bestätigtem STOP ist die Reservierung frei; die letzte identity/epoch bleibt als terminale Zuordnung bis zum nächsten Start erhalten. Wiederholter STOP derselben identity darf einen frischen stop ohne Schreibaufruf bestätigen. Sobald eine neue identity startet, ist diese alte Zuordnung ersetzt und alter STOP wird vor jedem Sessionaufruf abgewiesen. Vor dem ersten START-Schreibaufruf reserviert der Adapter nur die zugeordnete Ausführung, nicht eine neue Generation/Queuehoheit. Ab dann bleibt ein nicht erfolgreich bestätigter Ablauf UNCONFIRMED und blockiert jede neue START-identity bis zu explizit bestätigtem STOP/Realitätsabgleich. Nach Guardverweigerung werden keine automatischen Cleanupkommandos an dessen Stelle gesendet; P04 muss die alte konkrete Ausführung gegebenenfalls mit einem erlaubten STOP-Guard bereinigen. Dies verhindert erfundene Erfolgsmeldung ebenso wie einen Stop gegen einen bereits neuen Titel.

Wenn START bei einem sehr kurzen Titel nur noch stop beobachtet, wird kein natürlicher Abschluss erfunden und kein Nachfolger gestartet. canIdentifyNaturalEnd bleibt false. Pause/Seek/Startbelege dürfen nicht aus alten 250-ms-Pollwerten entstehen. Globale Lautstärke, Shuffle/Repeat der zentralen Queue, SQLitezustand und Eventnummern sind außerhalb dieses Adapters.

## Fakeabnahme und Freigabegrenzen

Luna soll nach ausdrücklicher Freigabe unter anderem beweisen: keine Konstruktions-/Importeffekte; strikt LOCAL und Resolverautorisierungsform; exakte Options-/Einzeltrackfolge; addid-IDweitergabe; frischer Status statt Cache; explizite Pause/Resume und IDgebundener Seek; doppelte aktive STARTidentität ohne zweite Wirkung; Status-ACK mit weiter play liefert keinen Stopbeleg; Guardwechsel zwischen Schritten unterbindet den nächsten Aufruf; erlaubter Cleanup-STOP betrifft nur reservierte alte identity; epochwechsel zwischen Kommando und Beobachtung invalidiert die Bestätigung; abgelaufene Frist erlaubt keinen Aufruf; unklare Wirkung blockiert nächsten Start. Fakes müssen deklarierte Frist-/epoch-Eigenschaften tatsächlich simulieren und dürfen Erfolg nicht einfach unabhängig vom Ablauf zurückgeben.

Vor realer Bindung bleiben echte LibraryId-Auflösung, normalisierte frische Session, tatsächlich begrenzte Socket-/Lock-/Resolverwartezeit, Reconnectidentität und exklusiver X-Anschluss an genau den vorhandenen MPDClient offen. Die gepinnte MpdLock-/timeout-None-Situation wird hier nicht als bereits passend ausgegeben. Externe MPD-/RFID-/GPIO-/Web-/Timer-/Jingle-/Sprachschreiber sind noch nicht umgeleitet. Physische Audio-Stille, Seek-/Pausefähigkeiten, Endeerkennung, Neustart-State und zehn gemessene Quellenwechsel erfordern Zielgerät/P02/P04/P07. Fakekonformität schließt weder G1/G2 noch Runtime-/Hardwareabnahme.

Root muss die vier Dateien, Namen und diese injizierten Formen zuerst im engen Luna-Briefing freigeben. Dieses Dokument allein autorisiert keine technische Gateway-/Providerimplementierung oder Änderung bestehender Dienste.

## Root-Freigabe P01a1

Am 16.10.2026 fachlich für den exakt oben beschriebenen transportfreien Slice freigegeben. Basis ist Integrationscommit 5057f0b60c4e85f595fd09450be8341f1f377c48. Ausschließlich Luna darf vier neue Dateien unter components/local_provider und test/local_provider erstellen; die genau benannten Konstruktor-/Session-/Lease-/Belegformen sind maßgeblich. Der lokale Artefaktordner ist kein vollständiger Checkout. Keine reale MPD-Anbindung, Registrierung, Hintergrundarbeit, zusätzliche Abhängigkeit oder Geräteaktion. Fakes und CI beweisen den Adaptervertrag, keine Laufzeitfristen oder Audiofunktion am Zielgerät. Zentrale Instanzsperre, Single-Caller-Serialisierung und Recovery bleiben P04; die exklusive Sessionklammer darf nicht mit einem SQL-Rollback verwechselt werden.

Root-Präzisierung zur Erstimplementierung: Nach Guard- und Epochzugriff Frist unmittelbar vor jedem tatsächlichen Protokollaufruf erneut prüfen; auch ein True-Guard kann Zeit verbrauchen. Der initiale START verlangt play, ein bereits pausierter Nachstatus ist keine erfolgreiche Erststartbestätigung; nur der wiederholte aktive START darf den vorhandenen Pausezustand ohne Schreibwirkung beobachten. OBSERVE mit hasError=true liefert PROVIDER_STATE_MISMATCH statt eines fehlerlosen CONFIRMED-Belegs, weil der Beleg hasError nicht separat transportiert. Die Pythonbindung des Resolveraufrufs ist ein injizierter Callable mit genau libraryId als Argument; eine reale Resolverklasse wird dadurch nicht behauptet.

Root-Präzisierung nach unabhängigem Review am 7ede9cf: Session-Kontextabschluss gehört zur Operation. CONFIRMED-Beleg und interne Stopfreigabe erst nach erfolgreichem Abschluss sowie abschließender Guard-/epoch-/Fristprüfung. Exitfehler oder während Exit geänderte Session/abgelaufene Frist dürfen bestätigte VorExit-Beobachtung nicht als Gesamterfolg ausgeben. Bereits mögliche MPD-Wirkungen behalten ihre neue Ausführungsreservierung; kein Wiederherstellen einer vorherigen Identity nach begonnener neuer Mutation. Ein unbestätigter STOP blockiert den nächsten START. Die injizierte Session muss den eigenen Kontextabschluss selbst begrenzen; nachträgliche Checks sind keine Unterbrechungsgarantie eines blockierenden realen `__exit__`.

Die Stopfreigabe richtet sich nach dem letzten angenommenen STOP der zugeordneten Identity: auch ein wiederholter STOP nach früherem CONFIRMED/STOPPED darf bei aktuellem STOP_UNCONFIRMED die frühere Freigabe nicht weiterverwenden. Ein neuer START bleibt bis zu erneut bestätigtem STOP gesperrt. Ein fremder abgewiesener STOP ändert die aktuelle Zuordnung nicht.
