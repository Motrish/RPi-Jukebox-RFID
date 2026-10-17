# A01 – CONTRACT 1 für Bibliothek, Playlists und Queue

Stand: 16.10.2026. Verbindliche Implementierungsvorgabe für den begrenzten A02-V1-/P03-Slice. Dokumentationsauftrag; kein Produktcode, Schema, Test oder Transportanschluss. Das unabhängige A01-Review und die noch offenen F03-/Hardwareabnahmen werden dadurch nicht als bestanden erklärt.

## Geltung und Arbeitsgrenze

Basis ist V3.6.0, Commit `4fa84fd50750fd4b52984d51aa7c95466cf5b241`, Tree `14c8a895c4c5e6903315096a75c6b918228b6fa1`. Der gleichartige CI-Tree auf `58826fcf880f521292c56c43b682fa67cfdc2418` hat laut F03-Protokoll Web- und Pythonprüfungen bestanden; Installerabnahme bleibt offen. [Quelleninventur](f03-source-inventory.md) und [Backlog](../docs/superpowers/plans/multi-agent/backlog.md) bleiben die Nachweis- und Auftragsgrundlage.

A02-V1 implementiert ausschließlich transportfreie Datentypen, Validatoren und synthetische Konformitätsfixtures für MediaRef, PlaylistEntry, PlaylistSnapshot, QueueSnapshot, die nachfolgend freigegebenen Speicherkommandos, CommandResult und Error. P03 implementiert danach den lokalen SQLite-Store mit denselben Regeln. Beide brauchen weder UI noch MPD, Soloist, Netzwerk oder Hardware. Synthetische Bibliotheks-IDs sind als solche gekennzeichnet. Pfade `src/jukebox/components/playlists/` und eine gemeinsame Contractmodulgrenze sind Vorschläge für neue Module; hier genannte Typnamen sind Vertragssprache und keine Behauptung existierender Pythonklassen.

Nicht Teil dieses Slices: Registrierung in `plugs`, neue RPC-/HTTP-/WebSocket-Endpunkte, Änderungen bestehender Player-/GPIO-/RFID-Aufrufer, Audiostart, OAuth, PiSugaraktionen oder privilegierte Jobs. A02-V1 darf insbesondere keine weiteren Methoden über den bestehenden ungeschützten Raw-RPC erreichbar machen. Erst ein gesondertes X-Anschlussfenster nach Sicherheits-/Playervertrag darf solche Exposition freigeben. Bestehende V3-Playerstatusfelder werden nicht still umgedeutet.

## Allgemeine Datensemantik

Versionierte Wurzeltypen sind Schreibkommando, CommandResult, PlaylistSnapshot und QueueSnapshot; sie tragen `contractVersion` mit Ganzzahl 1. Ein Snapshot behält dieses Feld auch als eingebettetes Resultatobjekt. MediaRef, PlaylistEntry, QueueEntry, Error und Error.details besitzen kein contractVersion-Feld; dort wäre es ein unbekanntes und deshalb ungültiges Feld. Die lesende Playlistübersicht ist ein eigenes versioniertes Wurzeldokument, ihre einzelnen Übersichtszeilen sind unversioniert. Zeichenketten sind Unicode; IDs sind opaque ASCII-Token aus Buchstaben, Ziffern, Unterstrich und Bindestrich, Länge 1 bis 128. Keine ID darf als Dateisystempfad oder Shellargument interpretiert werden. Server-/Store-generierte Objekt- und Eintrags-IDs sind dauerhaft eindeutig und werden nicht wiederverwendet. Ein späterer Transport erzeugt eigene Korrelations-IDs zusätzlich zu commandId.

Revisionen sowie position/toPosition sind echte JSON-Ganzzahlen; Positionen sind zusätzlich nichtnegativ und an die jeweilige Listengröße gebunden. Revisionen sind nichtnegativ und höchstens 9007199254740991; Boolean, Float, negative Werte und numerische Zeichenketten sind ungültig. Bestehende Objekte beginnen mit Revision 0. Eine erfolgreiche materielle Änderung erhöht ausschließlich die betroffene Revision um genau 1; ein expliziter wirkungsloser Zustand lässt sie unverändert. Ein Überlauf ergibt REVISION_EXHAUSTED ohne Änderung. Zeitstempel sind UTC im RFC-3339-Format; sie dienen Anzeige und Diagnose, niemals Konkurrenzkontrolle oder Reihenfolge.

V1-Eingaben sind geschlossen: unbekannte Aktionen, unbekannte Quellarten, unbekannte Felder, falsche Typen, fehlende Pflichtfelder und unzulässige Nullwerte ergeben VALIDATION_ERROR. Eine andere echte Ganzzahl als contractVersion ergibt gesondert UNSUPPORTED_VERSION; Boolean, Float, Null und Zeichenkette bleiben als falscher Typ VALIDATION_ERROR. Pflichtfelder sind auch dann vorhanden, wenn ihr ausdrücklich erlaubter Wert null ist. Displaytexte sind Daten, keine HTML-/Shell-/Dateipfadanweisungen. Name: 1 bis 256 Zeichen mit mindestens einem Nicht-Leerzeichen; Titel: 1 bis 1024 Zeichen. Eine Liste enthält höchstens 10000 Einträge; Überschreitung ergibt LIMIT_EXCEEDED, kein Abschneiden. Diese technischen Grenzen gelten symmetrisch in beiden Validatoren und im Store.

## Datenobjekte für A02-V1 und P03

| Objekt | Pflichtfelder | Semantik |
| --- | --- | --- |
| MediaRef LOCAL | kind = LOCAL, libraryId | libraryId bezeichnet ein vom Bibliotheksdienst ausgegebenes stabiles Medium. Keine freie Pfad-/URL-Eingabe. Der reine Validator prüft Tokenform; erst Bibliotheksauflösung prüft Existenz und erlaubten Root. Der Store darf synthetische oder derzeit nicht auflösbare IDs erhalten, markiert dadurch aber keine Datei als vorhanden. |
| MediaRef SPOTIFY | kind = SPOTIFY, uri | Ausschließlich kanonische Trackreferenz: Präfix spotify:track: gefolgt von genau 22 ASCII-Buchstaben/Ziffern. Keine URLs, Alben, Playlists oder spotify:local:-Einträge. S03 normalisiert zulässige Benutzerlinks vor dieser Grenze. Ein formal gültiger URI beweist weder Zugriffsrechte noch Abspielbarkeit. |
| PlaylistEntry | entryId, mediaRef, title, position | entryId bezeichnet genau ein Vorkommnis. position ist der nullbasierte, lückenlose Index im Array; beide Reihenfolgen müssen übereinstimmen. Gleiche MediaRef darf beliebig oft vorkommen, entryId innerhalb eines Objekts nur einmal. |
| PlaylistSnapshot | contractVersion, playlistId, name, revision, entries | Dauerhafte gespeicherte Phoniebox-Playlist. Titelanzeige und Reihenfolge sind Teil dieses Snapshots. Änderungen an Providerkatalogen überschreiben diesen Snapshot nicht automatisch. |
| QueueSnapshot | contractVersion, queueId, revision, sourcePlaylistId, sourcePlaylistRevision, entries, currentEntryId, repeatMode, shuffleMode | Dauerhafte Arbeitskopie für genau eine laufende Queue. sourcePlaylistId und sourcePlaylistRevision sind beide gesetzt oder beide null. Herkunft dokumentiert den beim Laden übernommenen Stand; sie wird bei späterer Queuebearbeitung nicht auf einen vermeintlich aktuellen Playliststand erhöht. |
| QueueEntry | Felder von PlaylistEntry sowie sourceEntryId | eigener entryId in der Queue; sourceEntryId ist der Eintrags-ID der geladenen Playlist zugeordnet oder null. Dadurch bleiben gleiche Titel und wiederholte Ladevorgänge unterscheidbar. |
| Error | code, message, retryable, operation, details | code ist stabil; message ist sichere Anzeigediagnose und kein Parsevertrag. details enthält nur die für diesen Fehler nachfolgend erlaubten Angaben. Keine Tracebacks, Dateipfade, Tokens, Keys, kompletten Providerantworten oder Shellausgaben. |

repeatMode ist OFF, ALL oder ONE. shuffleMode ist OFF oder ON. In V1 speichert der Store diese Werte nur; er mischt keine Einträge und spielt nichts ab. Der tatsächliche Shuffleablauf ist P06, nicht versteckter SQLite-Seiteneffekt. Der sichtbare entries-Array bleibt die explizite Queueordnung; P06 muss seinen Laufplan separat dokumentieren, bevor er Randomzustand ergänzt.

currentEntryId ist null oder verweist auf genau einen vorhandenen Queueeintrag. Null bedeutet keine Auswahl; ein vorhandener Wert bedeutet Auswahl, nicht hörbare Wiedergabe. Nur ein Controller schreibt diese Auswahl. Entfernen einer aktuell ausgewählten Zeile oder Ersetzen einer Queue mit Auswahl wird im V1-Store mit ACTIVE_ENTRY_REQUIRES_CONTROLLER abgewiesen. Deshalb kann P03 sicher unabhängig vom Player entstehen. Verschieben erhält die Auswahl-ID. Leere Queue hat immer currentEntryId null.

Playlistrevision und Queuerevision sind unabhängig. Ein Laden ändert nur die Queue; ein Speichern der Queue in eine Playlist nur die Playlist. Änderungen am Zeiger currentEntryId oder an Repeat/Shuffle erhöhen die Queuerevision, Positionsmessungen im Audiotitel dagegen nicht. Source-Playlistrevision ist Herkunft und kein weiterer Zähler. P04-Playbackereignisse tragen eine eigene Eventfolge.

MPD-songid, Dateiname, Spotify-trackid und Titeltext sind keine Ersatzwerte für entryId. Beim Laden erhalten Queueeinträge neue IDs, beim Speichern als Playlist erhalten Zielplaylist-Einträge neue IDs. Bestehende Einträge behalten ihre IDs bei append/remove/move; bloßes Laden/Speichern mutiert das Quellobjekt niemals.

## Kommandorahmen und atomare Wiederholung

Jedes freigegebene schreibende Kommando enthält contractVersion, commandId, action und die in der Kommandotabelle genannten Aktionsfelder. Erwartete Revisionen gehören zum unveränderlichen Inhalt. IDs für neue Objekte und neue Einträge erzeugt der Store und liefert sie im Ergebnis. Der Client muss bei Antwortverlust dieselbe commandId und denselben Inhalt wiederverwenden; ein neuer Benutzerwunsch erhält eine neue commandId.

commandId ist innerhalb einer Storeinstallation global eindeutig. Semantisch identische Eingaben vergleichen nach validiertem Feldinhalt: Objekt-Keyreihenfolge ist unerheblich, Arrayreihenfolge und Text sind erheblich. Optionale Felder werden vor Vergleich nach ausdrücklich dokumentiertem Default normalisiert; V1 verwendet für die freigegebenen Schreibkommandos ausschließlich Pflichtfelder. Derselbe commandId mit anderem Inhalt ergibt COMMAND_ID_REUSED ohne Seiteneffekt. Eine spätere Authgrenze bindet gespeicherte Resultate zusätzlich an die vertrauenswürdig festgestellte Berechtigung; Kenntnis einer commandId verleiht keinen Lesezugang.

Bei einem neuen gültigen Kommando erfolgen atomar: eindeutige Beanspruchung der commandId, Prüfung aller Vorbedingungen, Mutation und Speicherung des vollständigen Ergebnisses. Zwei parallele gleiche Kommandos erzeugen genau eine Änderung. Der zweite Aufruf liefert nach Abschluss das gespeicherte Ergebnis. Kann er den Store innerhalb der konfigurierten begrenzten Wartezeit nicht lesen, liefert er STORE_BUSY mit retryable true; er darf nicht selbst erneut mutieren. Ein abgebrochener Prozess hinterlässt entweder alles oder nichts. Nach Commit und verlorenem Antwortkanal liefert Wiederholung dasselbe gespeicherte Resultat einschließlich derselben IDs und Revisionen.

Auch fachliche Ablehnungen nach gültiger Eingabe, insbesondere REVISION_CONFLICT, NOT_FOUND und ACTIVE_ENTRY_REQUIRES_CONTROLLER, werden für diesen commandId atomar gespeichert. Ihre Wiederholung wird nicht wegen inzwischen geänderter Daten plötzlich erfolgreich. Nach Korrektur des Wunsches ist eine neue commandId erforderlich. VALIDATION_ERROR vor Storezugriff und STORE_BUSY vor gesicherter Annahme sind nicht als erfolgreiche Beanspruchung verbucht. Technischer Commitfehler bedeutet Transaktionsrollback; bei unklarem Commitausgang zuerst über dieselbe commandId nachsehen, niemals blind einen neuen Schlüssel erzeugen.

V1 entfernt keine Idempotenzresultate automatisch. Sie bleiben bis zum ausdrücklich administrierten Zurücksetzen bzw. migrierten Archivieren der Storeinstallation vorhanden. Ein späterer Aufräumvertrag muss alte Schlüssel weiterhin gegen erneute Mutation sperren; eine still eingeführte TTL ist inkompatibel.

CommandResult enthält contractVersion, commandId, action, status und genau eines von result oder error. Bei APPLIED ist result vorhanden und error fehlt vollständig; bei REJECTED ist error vorhanden und result fehlt vollständig. Ein Gegenfeld mit null ist in beiden Fällen ungültig. Für den reinen Store ist status APPLIED oder REJECTED. APPLIED bedeutet dauerhaft gespeicherte Datenwirkung, niemals gestartete Wiedergabe. result enthält die betroffenen vollständigen Snapshots nach dieser Mutation; PLAYLIST_DELETE liefert stattdessen deletedPlaylistId und deletedRevision als Löschbeleg; deletedRevision ist die letzte geprüfte Revision vor Entfernung, kein neuer unsichtbarer Zähler; auch später liefert Wiederholung diesen ursprünglichen Snapshot, keinen unbemerkten aktuellen Stand. Wer den aktuellen Stand braucht, liest separat. Wirkungslose akzeptierte Aktionen liefern APPLIED und unveränderte Revision. Ablehnungen liefern REJECTED und Error.

## Freigegebene V1-Kommandos

Die folgenden Aktionsnamen sind Vertragsbezeichner, keine vorhandenen RPCmethoden. expectedRevision bezieht sich immer auf das ausdrücklich bezeichnete Ziel. Jede schreibende Aktion erhält den gemeinsamen Rahmen. Eine Aktion prüft alle referenzierten IDs/Revisionen vor der ersten Änderung. Kein Teilimport und keine stille Konfliktkorrektur.

| Aktion und Pflichtfelder | Erfolg | Konflikt / Fehler | Wiederholung |
| --- | --- | --- | --- |
| PLAYLIST_CREATE: name, items | Neue playlistId, Revision 0; items enthalten jeweils mediaRef und title, daraus neue Einträge in Eingabereihenfolge | Ungültige Referenzform/Name oder zu viele items; leere Liste zulässig | Liefert dieselbe playlistId und alle ursprünglichen entryIds |
| PLAYLIST_RENAME: playlistId, expectedRevision, name | Neuer Name erhöht Playlistrevision; gleicher Name ohne Erhöhung | NOT_FOUND, REVISION_CONFLICT, VALIDATION_ERROR | Dasselbe ursprüngliche Ergebnis; keine zweite Erhöhung |
| PLAYLIST_APPEND: playlistId, expectedRevision, items | Neue Eintrags-IDs am Ende; vorhandene Duplikatmedien bleiben erlaubt; leere items sind wirkungslos | NOT_FOUND, REVISION_CONFLICT, LIMIT_EXCEEDED | Hängt nichts erneut an |
| PLAYLIST_REMOVE: playlistId, expectedRevision, entryId | Genau dieses Vorkommnis entfernt, verbleibende Positionen normalisiert; Playlistrevision +1 | NOT_FOUND bei fehlender Playlist oder Eintrags-ID; REVISION_CONFLICT | Ursprünglicher Erfolg, kein Fehler wegen inzwischen fehlender Zeile |
| PLAYLIST_MOVE: playlistId, expectedRevision, entryId, toPosition | Eintrag zuerst aus Ordnung entfernen, dann am angegebenen finalen Index einsetzen; gültiger Index 0 bis N-1; gleicher Index wirkungslos | NOT_FOUND, REVISION_CONFLICT, POSITION_OUT_OF_RANGE | Kein zweites Verschieben |
| PLAYLIST_DELETE: playlistId, expectedRevision | Playlist und ihre Einträge entfernt; existierende Queuekopien bleiben erhalten | NOT_FOUND, REVISION_CONFLICT | Gespeicherter Löschbeleg; kein neuer NOT_FOUND |
| QUEUE_CREATE: items | Neue queueId, Revision 0, neue Queueeinträge mit sourceEntryId null; currentEntryId und beide sourcePlaylistfelder null; repeatMode/shuffleMode OFF | VALIDATION_ERROR, LIMIT_EXCEEDED | Dieselbe Queue und IDs |
| QUEUE_LOAD_PLAYLIST: queueId, expectedQueueRevision, playlistId, expectedPlaylistRevision | Ersetzt nur eine Queue ohne Auswahl (currentEntryId null) durch genaue Playlistkopie; neue Queueeintrags-IDs, sourceEntryId gesetzt; currentEntryId null; Modi OFF; Herkunft gesetzt; Queue-Revision +1 | NOT_FOUND, Konflikt eines der beiden Revisionswerte, ACTIVE_ENTRY_REQUIRES_CONTROLLER | Ursprünglicher geladener Stand; nicht späterer Playlistinhalt |
| QUEUE_APPEND: queueId, expectedRevision, items | Neue Queueeinträge mit sourceEntryId null hinten anhängen; Auswahl/Herkunft bleiben; leer wirkungslos | NOT_FOUND, REVISION_CONFLICT, LIMIT_EXCEEDED | Keine zweite Anhängung |
| QUEUE_REMOVE: queueId, expectedRevision, entryId | Nicht ausgewähltes Vorkommnis entfernen, Positionen normalisieren; Queue-Revision +1 | NOT_FOUND, REVISION_CONFLICT, ACTIVE_ENTRY_REQUIRES_CONTROLLER | Derselbe ursprüngliche Erfolg oder dieselbe Ablehnung |
| QUEUE_MOVE: queueId, expectedRevision, entryId, toPosition | Wie PLAYLIST_MOVE; aktuelle Auswahl-ID bleibt erhalten | NOT_FOUND, REVISION_CONFLICT, POSITION_OUT_OF_RANGE | Keine zweite Bewegung |
| QUEUE_SET_MODES: queueId, expectedRevision, repeatMode, shuffleMode | Gewünschte Werte speichern, bei Änderung einmalige Queue-Revisionerhöhung; keine Neuordnung | NOT_FOUND, REVISION_CONFLICT, VALIDATION_ERROR | Keine erneute Änderung |
| QUEUE_SET_CURRENT: queueId, expectedRevision, entryId | Nur interne Controlleroperation; entryId null oder existierendes Queuevorkommnis; Auswahländerung erhöht Queuerevision, kein Ton | NOT_FOUND, REVISION_CONFLICT; keine externe Registrierung | Keine zweite Auswahländerung |
| QUEUE_SAVE_NEW_PLAYLIST: queueId, expectedQueueRevision, name | Neue gespeicherte Playlist mit Revision 0 und neuen Eintrags-IDs aus der exakten Queueordnung; Modi/Auswahl nicht übernommen; Queue unverändert | NOT_FOUND, REVISION_CONFLICT, VALIDATION_ERROR | Dieselbe neue playlistId; keine zweite Playlist |
| QUEUE_SAVE_PLAYLIST: queueId, expectedQueueRevision, playlistId, expectedPlaylistRevision | Zielplaylist-Einträge durch Queuekopie mit neuen IDs ersetzen; Name bleibt; Playlistrevision +1, Queue/Herkunft unverändert | NOT_FOUND, Konflikt eines der beiden Objekte | Ursprüngliches Ergebnis; kein zweites Ersetzen |

QUEUE_LOAD_PLAYLIST erzeugt immer eine neue Kopie, auch bei gleicher Herkunft; QUEUE_SAVE_PLAYLIST erzeugt immer neue Eintragsidentitäten und zählt daher stets als materielle Änderung. Bei Zielplaylistlöschung darf die Queue ihre ursprüngliche Herkunft als historischen Hinweis behalten; diese Referenz ist kein Eigentums-/Löschcascade. Revisionskonflikte bezeichnen in details eindeutig objectType, objectId, expectedRevision und actualRevision. Schlägt eine zweifache Revisionsprüfung fehl, nennt der Fehler alle festgestellten Konflikte innerhalb derselben Transaktionssicht.

Nicht freigegeben sind Bulk-Patches, freie SQL-/Dateipfadfelder und zusätzliche RPCbefehle. Neue Wünsche erfordern einen ergänzten Vertrag und gezielte Schnittstellenprüfung.

## Lesende Operationen und Bibliotheksauflösung

PLAYLIST_GET und QUEUE_GET verlangen die jeweilige ID und liefern einen vollständigen atomaren Snapshot oder NOT_FOUND. COMMAND_GET verlangt commandId und liefert das gespeicherte Resultat oder COMMAND_NOT_FOUND; vorübergehende Nichterreichbarkeit des Stores ist STORE_BUSY/STORE_UNAVAILABLE und kein unbekannter Befehl. Leseoperationen benötigen keine commandId und verändern keine Revisionen.

PLAYLIST_LIST liefert ID, Name und Revision mit limit 1 bis 200, Default 50, plus opaque nextCursor oder null. Ordnung ist aufsteigende playlistId. Cursor bezeichnet die letzte gelieferte ID, niemals einen Dateipfad. Die Übersicht ist keine feste Momentaufnahme über mehrere Seiten; konkrete Bearbeitung lädt vor Schreiben den einzelnen Snapshot und verwendet dessen Revision.

LIBRARY_RESOLVE ist ein künftiger interner Bibliotheksvertrag, kein in A02-V1 implementierter Scanner. Eingabe ist eine LOCAL-MediaRef; Ausgabe enthält dieselbe libraryId, title und availability AVAILABLE, MISSING oder UNKNOWN. Der Dienst löst erst hinter dieser Grenze auf einen freigegebenen Musikroot auf und verwirft Ausbrüche über Pfade/Symlinks. Pfadnamen sind keine Medienidentität; Umbenennungen/Migration können Zuordnung erhalten, müssen es aber ausdrücklich nachweisen. Persistierte Playlists dürfen MISSING-Referenzen enthalten, um Offlinebestände nicht zu löschen. Der spätere Player verweigert Start mit MEDIA_UNAVAILABLE statt beliebige Pfade zu akzeptieren.

V3 unterstützt außerdem M3U, Podcast-/Livestreamreferenzen. Diese sind in CONTRACT 1 bewusst keine zusätzliche MediaRef-Art. M01/S03 müssen solche Quellen als nicht übertragbar bzw. noch nicht unterstützt anzeigen; kein Verstecken einer URL in libraryId und keine Behauptung vollständiger V2-/V3-Bestandskompatibilität.

## Fehlerkatalog für V1

| Code | retryable | Erlaubte details / Behandlung |
| --- | --- | --- |
| VALIDATION_ERROR | false | field und sichere reason; Inhalt korrigieren |
| UNSUPPORTED_VERSION | false | supportedVersions; keine automatische Umdeutung |
| NOT_FOUND | false | objectType und objectId; IDs prüfen |
| COMMAND_NOT_FOUND | false | commandId; kein Beleg für Wirkung eines unklaren externen Audio-/Setupbefehls |
| REVISION_CONFLICT | false | conflicts mit Objekt, erwarteter/tatsächlicher Revision; neu lesen und neuen Wunsch mit neuer commandId senden |
| COMMAND_ID_REUSED | false | commandId; ursprünglicher Inhalt bleibt unverändert |
| POSITION_OUT_OF_RANGE | false | entryId und erlaubte Indexgrenze |
| LIMIT_EXCEEDED | false | field und limit; keine teilweise Übernahme |
| ACTIVE_ENTRY_REQUIRES_CONTROLLER | false | queueId und currentEntryId; Wirkung über spätere Controlleroperation ausführen |
| REVISION_EXHAUSTED | false | objectType und objectId; administrierte Migration erforderlich |
| STORE_BUSY | true | operation; gleiche commandId nach begrenztem Backoff wiederholen |
| STORE_UNAVAILABLE | true | operation; bei Wiederherstellung zuerst denselben commandId nachsehen |
| INTERNAL_ERROR | false | sichere Diagnose-ID; keine Details des internen Fehlers |

HTTPstatuscodes sind in diesem transportfreien Slice nicht definiert. Später bedeutet REVISION_CONFLICT HTTP 409 an einer wirklichen HTTP-Grenze; über vorhandenes ZMQ-RPC bleibt es ein stabiler strukturierter Fehler. Upstream-RPC-error.code -1 ist kein hinreichender öffentlicher Vertrag.

## Anschlussregeln für P04–P08 – kein Bestandteil des ersten Stores

PlaybackState enthält contractVersion, bootId, eventSequence, queueId, queueRevision, state, mode, currentEntryId, activeProvider, executionId, generation, positionMs, durationMs, capabilities und error. state ist STOPPED, PREPARING, PLAYING, PAUSED, SWITCHING oder ERROR; mode ist PHONIEBOX oder CONNECT. provider ist LOCAL oder SPOTIFY bzw. null ohne aktive Ausführung. Position/Dauer sind nichtnegative Ganzzahlen in Millisekunden oder null für unbekannt. Anzeige bleibt ohne bestätigtes Anbieterereignis PREPARING/SWITCHING; Befehlsannahme ist kein PLAYING.

bootId wird pro Controllerprozessstart neu erzeugt. generation ist ein monotoner Zähler innerhalb dieses Boots und wird bei jeder ersetzenden Start-/Stop-/Skip-/Modusabsicht vor Anbieterarbeit erhöht. executionId wird pro konkretem Startversuch neu erzeugt, auch bei gleichem entryId. Jedes Anbietereignis trägt diese drei Identitäten. Alte bzw. doppelte Ereignisse dürfen weder State noch Queue fortschalten. Innerhalb einer Generation wird natürlicher Abschluss höchstens einmal verarbeitet. ProviderStop, Benutzerstop, Skip, Fehler und natürliches Ende sind verschiedene Ursachen.

Ein Controller und eine Instanzsperre besitzen Audio. Er serialisiert Annahme und Zustandsübergänge auch bei direkt dereferenzierten GPIO-/Bluetoothcallbacks. Asynchroner Start prüft seine Generation vor dem Start und bei Rückkehr; nach Abbruch muss eine verspätet gestartete Instanz gestoppt und ihr Ende bestätigt sein. Vor Quellenwechsel bestätigt der bisherige Anbieter den Stopp. Timeout/Verbindungsabbruch sind keine Stopbestätigung: ERROR mit STOP_UNCONFIRMED, kein nächster Audiostart. MPD darf im PHONIEBOX-Modus nicht unabhängig über die zentrale Queue fortschalten. Jingle, Sprachansage und Testton sind ebenfalls Audioproduzenten und brauchen explizite Ausgabereservierung oder eine exklusive Start-/Shutdownphase.

Providerfähigkeiten sind canPause, canResume, canSeek, canConfirmStop und canIdentifyNaturalEnd, jeweils Boolean aus geprüfter Adapterkonfiguration. Seek verlangt canSeek und gültige Position; fehlende Fähigkeit ergibt CAPABILITY_UNAVAILABLE, kein stiller Ersatz durch Skip. Prozessende allein ist kein natürlicher Abschluss. Soloistfähigkeit und Quellenwechsel bleiben bis P02/S01 real unbestätigt.

Der spätere Controllerkommandovertrag umfasst PLAY_ENTRY, PAUSE, RESUME, STOP, NEXT, PREVIOUS, SEEK, REMOVE_CURRENT, LOAD_AND_PLAY_PLAYLIST, RFID_TRIGGER, ENTER_CONNECT und RETURN_PHONIEBOX. Alle verlangen commandId; Queueänderungen zusätzlich die erwartete Queuerevision. Aktionsnamen sind Vorschläge bis zum separaten P04-/P07-Briefing. Erfolg bedeutet zunächst ACCEPTED mit Ausführungsstatus, anschließend SUCCEEDED oder FAILED. Externes Audio ist nicht zusammen mit SQLite atomar: ein Crash nach Wirkung wird als UNKNOWN/RECOVERING abgeglichen, niemals als sicher fehlgeschlagen neu abgespielt. Bereits angenommene gleiche commandId liefert denselben Auftrag, keine weitere Aktion. Noch nicht unterstützte Aktion wird vor Anbieterwirkung mit CAPABILITY_UNAVAILABLE abgewiesen. Veraltete Queuebezüge ergeben REVISION_CONFLICT oder NOT_FOUND.

P06-Regel für aktiven Eintrag: Verschieben erhält executionId und Ton; Entfernen des laufenden Eintrags bestätigt zuerst Stopp und entfernt erst danach transaktional. Nachfolger ist der vor Entfernung folgende Eintrag in der definierten Laufordnung; bei Listenende gilt Repeat ALL, sonst STOPPED; Repeat ONE hält einen entfernten Eintrag nicht am Leben. Stopfehler erhält den Eintrag und zeigt ERROR. Gleichzeitige Queueänderung während Stopp wird gegen aktuelle Revision neu bewertet und darf keinen fremden Nachfolger starten. Gespeicherte Playliständerungen beeinflussen laufende Queue nie automatisch.

RFID unterbricht eine bestehende Wiedergabe nur nach bestätigtem Stoppen. Second Swipe richtet sich nach Karten-/Listenidentität und kanonischem Playbackzustand. Kartenentfernung darf ausschließlich die noch zu dieser Karte gehörende Ausführung verändern. Resume speichert Liste, Auswahl, Position und Fähigkeiten; Neustart gleicht reale Anbieterinstanz und gespeicherten Zustand ab und startet keine zweite Instanz. Ohne gesicherte Wiederanlaufentscheidung beginnt der Controller STOPPED; fehlende Seekfähigkeit startet keinen behaupteten exakten Resume.

CONNECT ist bewusste Übergabe: gemischten Zustand sichern, bisherige Ausführung stoppen, externe Hoheit aktivieren. Rückkehr bestätigt Connectstopp, stellt gespeicherte Queue her und setzt nur soweit geprüft fort. Unerwartete externe Übernahme wird sichtbar; sie darf keine parallele Engine erzeugen. Exakte Connect-/Offline-/Shuffleabläufe werden erst nach P02/P06/P08 freigegeben. Beim Internetausfall bleibt gespeicherte Liste erhalten; begrenztes Warten endet in PAUSED mit MEDIA_UNAVAILABLE, automatische unbeschränkte Skip-/Retryschleifen sind verboten.

## Snapshot und Ereignisse für späteres A02/P04/U05a

Ein atomarer Laufzeitsnapshot enthält bootId, eventSequence, QueueSnapshot und PlaybackState aus derselben Controllersicht. eventSequence erhöht sich für jedes sichtbare Zustandsereignis; derselbe Cachepayload behält seine Nummer. Ereignisse tragen bootId, eventSequence, executionId/generation soweit betroffen und vollständige betroffene Zustandsteile. Reconnect/Bootwechsel oder Sequenzlücke laden erneut den Snapshot; Last-Value-Cache ist kein Eventjournal.

Anschlussverfahren: zuerst Eventverbindung herstellen und Empfang puffern, dann Snapshot mit Sequenz S holen, danach gepufferte Events desselben Boots mit Nummer über S lückenlos anwenden. Nicht überbrückbare Lücke oder Puffergrenze erzwingt neuen Snapshot. Der Consumer verwirft ältere/doppelte Ereignisse. Das Verfahren ist Vertrag, keine hier behauptete Fähigkeit des unveränderten jszmq-Clients. UI hält keinen maßgeblichen eigenen Playerlaufzustand.

## Batteriestatus und SetupJob – vorläufige Anschlussverträge

Diese Objekte sind für B01/I01/I02 beschrieben, werden in A02-V1/P03 nicht implementiert oder als Hardwarefunktion behauptet.

BatteryStatus enthält contractVersion, enabled, detected, reachable, model, percent, charging, measuredAt, capabilities und error. detected ist true, false oder null bei noch unbekannt; reachable ist Boolean; model ist Modellbezeichner oder null; percent ist Zahl 0 bis 100 oder null; charging ist Boolean oder null; measuredAt ist UTC-Zeitstempel der letzten erfolgreichen Messung oder null. Deaktiviert bedeutet enabled false, detected null, reachable false, alle Messwerte null, capabilities leer und kein Badge. Fehlgeschlagene aktuelle Messung bedeutet reachable false und percent/charging null; optional separat ausgewiesene historische Daten sind ausdrücklich lastKnown und niemals frisch. Nur bestätigte Modelle liefern Aktionen in capabilities. B01 startet mit fünf Sekunden Intervall und begrenztem Backoff; Abschaltung bleibt dem lokalen Systemdienst vorbehalten.

SetupJob enthält contractVersion, jobId, commandId, status, stepId, desiredConfigSummary, appliedSteps, revision, createdAt, updatedAt, nextAction und error. status ist QUEUED, RUNNING, WAITING_USER, REBOOT_REQUIRED, SUCCEEDED, FAILED oder CANCELLED. desiredConfigSummary und nextAction sind typisierte, redigierte Anzeigeinformation; sie enthalten keine Secrets, freien Befehle, Skriptpfade oder SQL. appliedSteps hält bestätigte Wirkung mit Schritt-ID und sicherer Diagnose; ein begonnener Schritt ist noch nicht angewendet. Jobrevision steigt bei jedem dauerhaften Zustandswechsel, unabhängig von Player-/Queuerevision.

Ein privilegierter Worker besitzt genau einen aktiven Installationsjob; neuer anderer Auftrag erhält JOB_CONFLICT. Gleiche commandId mit gleichem Inhalt liefert dieselbe jobId; anderer Inhalt COMMAND_ID_REUSED. Intent wird vor Wirkung gespeichert, Wirkung danach beobachtet und protokolliert. Nach Crash wird Realität geprüft; ein unbekannt abgeschlossener Schritt wird nicht blind wiederholt. Browserende beendet keinen Job. Abbruch wird erst an sicherer Schrittgrenze bestätigt; schon angewendete Schritte bleiben sichtbar. Auth-/Worker-/Reboot-Integration erfordert I01/I02/I06 und keine Produktfreigabe aus diesem Vertrag.

## HTTPS, Privilegien und Remote-CI-Arbeitsweise

A01-Entscheidung: vorhandenes nginx als gemeinsame Geräteorigin beibehalten; HTTPS mit auf jedem Bediengerät vertrauenswürdigem Zertifikat ist Voraussetzung für echte OAuth-/Verwaltungsfreigabe. Für lokale Installation ist ein dedizierter lokaler Vertrauensanker mit gerätespezifischem Zertifikat der Zielweg; privater Schlüssel bleibt auf der Box, die Vertrauenseinrichtung muss auf Desktop und Smartphone real nachgewiesen werden. Eine bereits vorhandene vertrauenswürdige HTTPS-Proxyorigin ist zulässig, sofern Callback, WS und PiSugar dieselbe geschützte Origin verwenden. Die konkrete Zertifikats-/Trustbereitstellung ist I05; A02-V1 blockiert sie nicht. Bis zu ihrem Nachweis bleiben OAuth und externe Verwaltung unfreigegeben, keine .local-HTTP-Ausnahme.

Raw-RPC/Pub/Sub hinter dieser Grenze müssen auf lokale Erreichbarkeit begrenzt und sämtliche administrativen Methoden authentifiziert/autorisiert werden; nur Setupcode auf einem neuen Endpunkt zu prüfen genügt nicht. Logroute darf weder Einmalcodes noch Session-/Providersecrets offenlegen. Setupdienst und privilegierter Worker werden getrennt vom Player betrieben. Worker akzeptiert nur bekannte typisierte Schritte, besitzt eng begrenzte Systemrechte und akzeptiert keine freie Browser-Shellaktion. Vorhandene `sudo shutdown`- und Netzwerkmethoden gehören in die gesonderte X-/I05-Prüfung.

Remote-isolierte Featurebranches mit vollständigem GitHub-Actions-Checkout sind als eingeschränkter Entwicklungsweg vertretbar: jedes Codingticket startet von benanntem SHA, besitzt eigene Dateien/Branch, wird am exakten erzeugten Integrations-SHA vollständig ausgecheckt und mit vorhandenen plus neuen gezielten Tests geprüft. Lokale neue Moduldateien sind Stagingartefakte; sie sind kein vollständiger Checkoutnachweis. Root-Dateien/Registry/Router/Dependencies bleiben exklusiver serieller X-Besitz. API-Multifilecommits müssen auf überprüftem Head aufsetzen; konkurrierende Headbewegung bedeutet Konflikt und erneutes Lesen, keine blinde Überschreibung. Schematests auf isolierten Modulen ersetzen nie den integrierten CI-Lauf.

Diese Arbeitsweise ersetzt keine Hardware-/Installer-/Browserabnahme und belegt keine Workflow-Schreibrechte. Tests erhalten keine Produktionssecrets und wirken nicht auf die bestehende Box. Neue Actions-/Release-/Secretrechte werden nicht aus allgemeinem Connector-Schreibrecht abgeleitet. Releaseworkflow wird nicht als Testinstrument missbraucht. Offene Installerbaseline bleibt eigenes Ticket; V1-Speicherentwicklung darf keine erfolgreiche Gesamtinstallation behaupten.

## Abnahme des ersten Slices

Luna A02-V1 implementiert zunächst Python-stdlib-Verträge und Unitprüfungen; sprachunabhängige synthetische Fixtures bleiben für die spätere Reactgrenze wiederverwendbar. Der erste Slice verlangt keinen neuen JavaScriptvalidator und keine Nodeabhängigkeit. Zu bestätigen sind: LOCAL/SPOTIFY-Trennung, unbekannte Quellart, fehlende/zusätzliche Felder, Null-/Boolean-/Floatrevisionen, doppelte Medien mit verschiedenen IDs, inkonsistente Positionen, ungültige Auswahl und zulässige Snapshotkopien. Es wird kein transportöffentlicher Anschluss erzeugt.

Luna P03 muss insbesondere nachweisen: Speicherung/Laden mit doppelten Medien, getrennte Playlist-/Queuerevision, Auswahl-ID nach Verschieben, Ablehnung aktiver Entfernung, zwei konkurrierende Änderungen auf derselben Revision, parallele gleiche commandId, abweichender Inhalt derselben commandId, Antwortverlust nach Commit, gespeicherte Konfliktablehnung und vollständiger Rollback vor Commit. Tests laufen mit temporärer SQLite-Datenbank und synthetischen Medienreferenzen, ohne Netz/Audio/Hardware. Unabhängiges Review prüft exakt den so getesteten Commit.

A01 für das Gesamtsystem bleibt bis Anbieter-/Player-/Sicherheits-/Hardwareanschlussreview offen. CONTRACT 1 gibt den oben abgegrenzten Daten-/Store-Slice fachlich vor und bildet keine Freigabe ungeprüfter Wiedergabe oder öffentlicher Verwaltung.

## Präzisierung für A02a und getrennte Storetickets

A02a ist der erste transportfreie Python-stdlib-Slice. Freigegebene neue Schreibpfade: `src/jukebox/jukebox/contracts/__init__.py`, `src/jukebox/jukebox/contracts/v1.py`, `test/contracts/test_v1.py`, `test/contracts/fixtures/v1.json`. Sie werden ausschließlich durch Luna erstellt; dieser Prosa-Vertrag enthält keine Ersatzimplementierung. A02b prüft später die JavaScriptgrenze gegen dieselben semantischen Fixtures. A02 als Gesamtticket bleibt bis dazu und bis zum gesonderten gesicherten Transportanschluss offen. Die im Vertrag genannte Symmetrie von Validatoren ist die spätere Gesamtanforderung, keine zusätzliche JavaScriptarbeit in A02a.

Die exakten result-Felder sind geschlossen; keine abweichende Einzelobjektausgabe und kein dynamischer Feldname. Nicht veränderte Quellobjekte werden nicht zusätzlich als Resultat ausgegeben.

| Operationen | Exakte result-Felder |
| --- | --- |
| PLAYLIST_CREATE, PLAYLIST_RENAME, PLAYLIST_APPEND, PLAYLIST_REMOVE, PLAYLIST_MOVE | playlist mit vollständigem PlaylistSnapshot |
| QUEUE_CREATE, QUEUE_LOAD_PLAYLIST, QUEUE_APPEND, QUEUE_REMOVE, QUEUE_MOVE, QUEUE_SET_MODES, QUEUE_SET_CURRENT | queue mit vollständigem QueueSnapshot |
| QUEUE_SAVE_NEW_PLAYLIST, QUEUE_SAVE_PLAYLIST | playlist mit vollständigem Ziel-PlaylistSnapshot; unveränderte Queue fehlt im result |
| PLAYLIST_DELETE | deletedPlaylistId und deletedRevision, wie oben definiert |

PLAYLIST_GET und QUEUE_GET liefern den jeweiligen Snapshot direkt als eigenständiges versioniertes Dokument; COMMAND_GET liefert das gespeicherte CommandResult direkt. PLAYLIST_LIST liefert contractVersion, playlists und nextCursor; jede Zeile in playlists besitzt ausschließlich playlistId, name und revision. Transportfreie Getter melden Lesefehler über eine Exception mit dem unversionierten Error-Mapping in error; sie erfinden weder einen Lesefehlerrahmen noch eine Schreib-commandId. Eine spätere Transportabbildung ist gesondert festzulegen. Lesefehler werden nicht im Idempotenzregister gespeichert. Schreib-Kommandoframes besitzen nur contractVersion, commandId, action und exakt ihre Tabellenfelder.

P03 wird seriell in P03a und P03b geteilt: P03a liefert Playlistpersistenz, allgemeine Revisions-/Idempotenztransaktion sowie die sechs PLAYLIST-Schreibaktionen und ihre Lesefälle. P03b ergänzt Queuepersistenz, Queueaktionen und transaktionale Load-/Save-Übergänge über beide Objektfamilien. Gemeinsame Storedateien wechseln ausdrücklich den Schreibbesitz; kein paralleles unabhängiges Erfinden zweier Commandregister oder Transaktionsgrenzen. P03a muss schon Wiederholung/Parallelanfrage/Rollback nachweisen, P03b prüft zusätzlich die Transaktion über Playlist und Queue. Konkrete technische Dateien/Befehle stehen erst im jeweiligen Luna-Briefing.

### Präzisierungen aus dem A02a-Review

Die öffentliche transportfreie Identifierprüfung verwendet dieselbe Tokenregel für Kommandos, Snapshots und Store-Getter; es entsteht kein zweiter regulärer Ausdruck im Store. Fehler aus den Validatoren müssen selbst dem Error-Vertrag entsprechen, einschließlich LIMIT_EXCEEDED mit field und limit. Falsch typisierte Ergebnisstatuswerte ergeben VALIDATION_ERROR und keinen internen Pythonfehler.

Ein lesender Playlist-Snapshot umfasst Revision und Einträge aus derselben SQLite-Transaktionssicht. Zwei unabhängige autocommit-Leseabfragen genügen dafür nicht. Ein vorhandener Command-Ledgereintrag ohne vollständiges Ergebnis ist ein Storeproblem, kein COMMAND_NOT_FOUND.

### P03a2 – Playlistübersicht

Die transportfreie Leseoperation list_playlists nimmt limit mit Standard 50 (echte Ganzzahl 1 bis 200) und cursor mit Standard null. Ein gesetzter Cursor erfüllt dieselbe opaque Tokenregel wie playlistId und bezeichnet die zuletzt gelieferte ID; er ist kein Pfad. Das Ergebnis besitzt exakt contractVersion, playlists und nextCursor. Jede Zeile in playlists besitzt playlistId, name und revision. Sortierung erfolgt aufsteigend nach playlistId; nextCursor ist nur bei vorhandener Folgeseite die letzte gelieferte ID, sonst null. Seiten sind keine dauerhafte gemeinsame Momentaufnahme. Ungültige Argumente ergeben vor SQL-Zugriff VALIDATION_ERROR. Die Mutation einer gespeicherten Playlist bleibt von der laufenden Queue getrennt.
