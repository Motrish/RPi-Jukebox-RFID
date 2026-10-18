# P01b – unabhängiges Testreview vor Produktimplementierung

Stand: 17.10.2026. Review des freigegebenen Plans einschließlich Root-Präzisierungen und der zwei eingefrorenen Testdateien im Teilstage G:/Entwicklung/phoniebox-staging/p01b. Zugeordneter Remotehead laut Root: afddd7a6934436304b3de107e1d930b4760d62bc, Tree d27c910afd16285d2d31a1b6963ea6eb2e20586f, Baseline ea87e4a7e0a4a6f16119e440f8c797c45d866d0c. Produktmodul und Export fehlen absichtlich.

## Ergebnis

Keine P1-/P2-Befunde. 21 kohärente deklarierte Tests: 19 Linuxfälle und zwei portable Import-/Plattformprüfungen. Die Linuxklassen skippen ausschließlich auf Nicht-Linux, nicht bei fehlenden sicheren Flags auf Linux. Die ausdrückliche src/jukebox-Pfadbereitstellung vor den Imports passt auch zum bestehenden Console-pytest/importlib-Modus. Keine Test-/CI-Ausnahme oder neue Produkt-API verlangt.

Geschlossene unabhängig veränderbare Rückgaben, persistente IDs, Alias-/Rename-Identitäten, Paging/Tombstones, sichere Argumentablehnung, Rootbindung, Busy/Konkurrenz und vorübergehendes UNKNOWN werden sinnvoll geprüft. Die Linuxprüfungen verwenden echte Tempdateien, Symlinks, Hardlinks, Verzeichnisse, FIFO, Ersatzdateien, Metadaten- und Rootänderungen. Der FIFO-Versuch ist durch einen separaten Kindprozess mit fünf Sekunden Timeout begrenzt. Der vorhandene Contractimport bleibt unverändert.

## Unabhängige Nachweise

Selbst ermittelte SHA256:

- test_catalog.py: 10e11b9430979536c78d0e93309bc5a5050bcbf41181cd14ee5ae9f709aaa283
- test_catalog_linux.py: 053f5f8d2001dcde75b8eab637d3e19539a0295eed368b32d07de85247076478

Cwd G:/Entwicklung/phoniebox-staging/p01b, PYTHONPATH ausschließlich G:/Entwicklung/phoniebox-tools/pytest-check, PYTHONDONTWRITEBYTECODE=1. Tatsächlicher Consoleaufruf G:/Entwicklung/phoniebox-tools/pytest-check/bin/pytest.exe --import-mode=importlib -p no:cacheprovider -q test/library_catalog: Exit 1, genau zwei erwartete Collectionfehler an den neuen Produktimports. Präzise lokale Meldung: No module named components, da im Teilstage der gesamte neue Komponentenpfad fehlt. Der vorhergehende Contractimport gelingt. Kein Verhaltenstestpass behauptet.

Mit PYTHONPATH=G:/Entwicklung/phoniebox-tools/python: python -B -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 test/library_catalog/test_catalog.py test/library_catalog/test_catalog_linux.py: Exit 0, keine Meldungen. Gezielter V3lint, kein vollständiger Repositorylint.

Root meldete anschließend tatsächlichen Linux-CI-RED für Run39030460679, Job117389696705, Python3.10: collected59items/2errors, beide neuen Imports scheitern am fehlenden library_catalog aus dem vorhandenen components-Paket. Der Reviewer hat dieses Remoteprotokoll nicht selbst abgerufen. Es passt zur bewusst fehlenden Implementierung.

## Grenzen und Übergabe

Nicht blockierende Grenzen fürs Quellreview: Die Konkurrenzprüfung nutzt dieselbe Kataloginstanz. Die Busyprüfung belegt keine Rücknahme nach bereits ausgeführten Schreibschritten. Der Importtest beobachtet nur sein Arbeitsverzeichnis. Descriptorflags, Fehlerpfad-Cleanup und dauerhaftes Tombstoning auch bei wieder exakt passendem alten Fingerprint sind zusätzlich am Produktcode zu beurteilen. Kein unbegrenzter neuer Testauftrag folgt daraus.

Phase1-Testreview ohne blockierenden Befund abgeschlossen; die von Root bestätigte tatsächliche Linux-RED-Evidenz ergänzt den lokalen Nachweis. Luna kann im engen Rootauftrag die zwei Produktdateien implementieren. Vor finaler Integration bleiben unveränderte Tests in der vollständigen Python3.9–3.13-Matrix, vollständiger V3lint und serielles unabhängiges Quellreview erforderlich. Keine Geräte-/ARMv6-/Audio-/GUI-/Integrationsfreigabe. Ausschließlich Prosa geschrieben; keine Produkt-, Test- oder Diagnoseskriptdatei und keine Remoteänderung.

## Serielles Phase2-Quellreview – Head7a1dd409

Stand: 17.10.2026. Geprüfter Sourcehead laut Root PR14: 7a1dd4098054b9a28da0349061f88daeb444a8b9, Tree cea7e5be66c7976ad3ce50fc9398884f31888f96, Elternstand afddd7a6934436304b3de107e1d930b4760d62bc. Die beiden neuen Quellen wurden vollständig gelesen und gegen den freigegebenen Plan geprüft; die zwei Testdateien sind unverändert. Keine ausführbare Probe geschrieben oder Produkt-/Testdatei geändert.

Selbst bestätigte SHA256: __init__.py a6ab8559aca3c4a5e9ebcea003145e305202e4e31a3c60fa41232d4bcbf2dc52; catalog.py 2b0b59008ca0e6c3de15df8e37ebe8e60f0ce55d7e69738a4b9ef59a597e42e5. Beide Testhashes entsprechen dem obigen Phase1-Stand.

### P2 – Definitiv fehlender Registerpfad invalidiert die alte ID nicht

Ort: src/jukebox/components/library_catalog/catalog.py:458–462, im Zusammenhang mit :463–474 und der Rollbackbehandlung :323–325.

register_file prüft zuerst den Dateipfad. Liefert der Probe None für einen definitiv fehlenden, nichtregulären oder symlinkbehafteten Eintrag, wird sofort MEDIA_UNAVAILABLE ausgelöst. Die bestehende aktive Zuordnung wird gar nicht gelesen oder tombstoniert. Damit verletzt dieser Registeraufruf die geplante dauerhafte Invalidierung durch beobachtete definitive Entfernung; der Plan nennt ausdrücklich die Beobachtung durch get/list/resolve/register und das Committen beobachteter Invalidierungen.

Konkreter Ablauf ohne Fingerprintmanipulation: album/song.mp3 registrieren; das Elternverzeichnis album innerhalb desselben Dateisystems vorübergehend umbenennen; register_file am alten Pfad aufrufen und MEDIA_UNAVAILABLE erhalten; das Elternverzeichnis zurückbenennen. Der Fingerprint des enthaltenen regulären Dateieintrags bleibt bei dieser Verzeichnisumbenennung gleich. get_media/resolve und erneutes register_file können deshalb wieder die alte aktive ID verwenden, obwohl der Katalog ihre definitive Abwesenheit bereits beobachtet hatte.

Erforderlich ist die dauerhafte Invalidierung einer vorhandenen aktiven Zuordnung bei diesem definitiven Registerbefund und anschließend weiter die sichere MEDIA_UNAVAILABLE-Ablehnung. Eine Tombstone-Aktualisierung unmittelbar vor dem bisherigen raise reicht allein nicht: Der Kontextmanager würde sie zurückrollen. Die enge Autorenregression sollte genau die Registerbeobachtung und die anschließende Rückkehr desselben Blattfingerprints abdecken. Bei technischer Ungewissheit darf weiterhin keine dauerhafte Invalidierung entstehen.

### P2 – Fremdes Schema mit ausschließlich Views wird als leere Datenbank initialisiert

Ort: src/jukebox/components/library_catalog/catalog.py:189–192 und :206–211; spätere Prüfung :244–249.

Die Initialisierungsentscheidung prüft nur user_version und Objekte vom Typ table. Eine existierende fremde SQLite-Datenbank mit user_version0 und einer eigenen View, aber ohne Tabellen, gilt dadurch als leer. Der Katalog fügt seine Tabellen und Metadaten hinzu, setzt user_version1 und committet. Die fremde View bleibt erhalten und wird auch von der späteren Schemaüberprüfung ignoriert.

Dies widerspricht der ausdrücklichen Plananforderung, ausschließlich eine leere/neue eigene Datenbank zu initialisieren und fremdes Schema sicher abzulehnen. Der vertrauenswürdige Datenbankpfad ersetzt diese Inhaltsprüfung nicht; genau dafür gibt es die Schemaablehnung. Vor dem Bootstrap müssen vorhandene eigene/fremde Schemaobjekte insgesamt beurteilt werden, unter angemessener Behandlung SQLite-interner Objekte. Eine fremde View darf keine erfolgreiche Initialisierung und keine Datenbankmutation auslösen. Die enge Autorenregression sollte eine solche bestehende Datenbank unverändert zurückgewiesen sehen.

### Übrige Prüfung und Nachweise

Keine P1-Befunde und keine weiteren P2-Befunde. Die neue API bleibt innerhalb der vier freigegebenen Dateien. Der Import öffnet weder Dateien noch SQLite. Linuxfähigkeit wird vor Konstruktionseffekten geprüft. Root und Unterverzeichnisse werden descriptorrelativ mit O_DIRECTORY/O_NOFOLLOW geöffnet, letzte Einträge mit O_PATH/O_NOFOLLOW und fstat auf reguläre Dateien geprüft; alle normal und über OSError verlassenen Probe-/Operationspfade schließen ihre übernommenen Descriptoren. Rootidentität wird je Operation gegen persistierten Pfad/dev/inode geprüft. Es gibt keinen portablen Dateifallback.

BEGIN IMMEDIATE pro Operation serialisiert konkurrierende Register auch über getrennte Verbindungen. Commit-/SQLitefehler führen über Rollback und Verbindungsschluss zu festen sicheren Codes. UUIDkollisionen werden nicht durch Überschreiben gelöst. Rückgaben enthalten nur die freigegebenen Felder, Statwerte bleiben verlustfreie interne Dezimalstrings. Bereits tatsächlich gesetzte Tombstones werden von get/list/resolve nicht reaktiviert. Die verwendete Python-Syntax ist mit 3.9 vereinbar. Diese statische Einschätzung ersetzt die tatsächliche Matrix nicht.

Bestehende Befehle unabhängig erneut ausgeführt: Console-pytest mit importlib-Modus und deaktiviertem Cacheprovider liefert auf diesem Windows-Host Exit0, 2passed/19skipped. Der oben dokumentierte gezielte V3lint wurde auf alle vier Dateien erweitert und liefert Exit0 ohne Meldungen. Die zwei P2-Abläufe wurden statisch aus dem gelesenen Code abgeleitet, nicht durch vom Reviewer verfasste Diagnoseskripte ausgeführt. Tatsächliche Linux-CI für den Produkthead ist in diesem Review nicht als abgeschlossen belegt.

Handoff: Zwei enge P2-Korrekturen samt zugehöriger Autorenregressionen sind vor Integration erforderlich. Danach eingefrorenen Folgestand seriell nachprüfen und vollständige Python3.9–3.13-Matrix/V3lint abwarten. Die bekannte spätere MPD-Stringübergabe-/TOCTOU-Grenze bleibt ausdrücklich außerhalb dieses Slices; keine zusätzlichen Player-, GUI-, Geräte- oder Audioanforderungen durch dieses Review.

Nicht blockierender Hinweis zu beschädigten internen Daten: int-Konvertierungen in `_stored_fingerprint` und `_verify_root_binding` können bei nachträglich fehlerhaftem TEXT einen ungefilterten ValueError auslösen. Der freigegebene eigene, vertrauenswürdige Store schreibt diese Felder selbst als Dezimalwerte; keiner der unterstützten Aufrufe erzeugt diesen Zustand. Ohne belegten Entstehungsweg im autorisierten Slice wird dies als zurückgestellter kleiner Robustheitshinweis und nicht als dritter P2-Blocker gewertet. Eine künftige Prüfung beschädigter eigener Stores kann solche Konvertierungsfehler sicher auf STORE_UNAVAILABLE abbilden.

## Enges Regressionstestreview – Headd0ebb859

Stand: 17.10.2026. Zugeordneter Head laut Root d0ebb8598c8dc1fe584dea370389564475ed0772, Tree 942ca401973d0314ef9ceef09bf14100d85a924e. Selbst bestätigter SHA256 von test_catalog.py: 4251c8d064600ce541a55e34e047a4d9e3940de15b0db612c8e59c612b555a18. catalog.py ist noch unverändert 2b0b59008ca0e6c3de15df8e37ebe8e60f0ce55d7e69738a4b9ef59a597e42e5; die Linuxdatei unverändert 053f5f8d2001dcde75b8eab637d3e19539a0295eed368b32d07de85247076478.

Keine blockierenden Befunde an den zwei neuen Regressionen. test_missing_register_tombstones_the_old_id_before_rejecting (:136) verschiebt ausschließlich das Elternverzeichnis, lässt register_file die definitive Abwesenheit feststellen und stellt das Elternverzeichnis vor der nächsten Abfrage wieder her. Die anschließenden Anforderungen MISSING, Resolver-None und neue ID prüfen genau die dauerhafte Registerinvalidierung bei zurückkehrendem identischem Blattfingerprint. Am unveränderten gelesenen Produktcode ist statisch AVAILABLE statt MISSING zu erwarten; die Regression trifft damit P2 Nummer1.

 test_view_only_database_is_rejected_without_mutation (:240) erstellt eine echte fremde View ohne Tabelle, fordert ausdrücklich STORE_UNAVAILABLE und nach Ablehnung unveränderte Datenbankbytes. SQLite wird vor dem Bytevergleich geschlossen; eine unerwartet akzeptierte Kataloginstanz wird ebenfalls geschlossen und als Fehler gewertet. Der unveränderte gelesene Produktcode akzeptiert diesen Fall statisch und erreicht das explizite Testfail; damit trifft die Regression P2 Nummer2. Keine Abschwächung der bisherigen Vertragsassertionen in den gelesenen Abschnitten, keine zusätzlichen Skips, Fakes oder Produktionsschnittstellen. Insgesamt nun 23 deklarierte Fälle, davon 21 unter Linux und zwei portable.

Der gezielte bestehende V3lint für test_catalog.py wurde unabhängig mit den oben dokumentierten Parametern erneut ausgeführt: Exit0 ohne Meldungen. Kein tatsächlicher Linux-RED dieser zwei Assertionen wird hier behauptet; diesen Nachweis wartet Root separat ab, bevor Luna die Produktkorrektur beginnt. Kein ausführbarer Artefakt durch den Reviewer verfasst oder geändert. Übergabe ohne Testblocker; die zwei bisherigen Produkt-P2 bleiben bis zum Quellenfix offen.

## Abschließendes serielles Quellenfolgereview – Headb4a42943

Stand: 17.10.2026. Zugeordneter Head laut Root b4a4294353eb27d0bdda5c24d742262eff3804ab, Tree 8ccedafaab19e7d748d5a814c341e0b0912341a3, Elternstand d0ebb8598c8dc1fe584dea370389564475ed0772. catalog.py erneut vollständig gelesen; die Auswirkungen des begrenzten Fixes auf den gesamten bisherigen Vier-Dateien-Slice geprüft. Selbst bestätigte SHA256: catalog.py ac42e035adf8f9c23232bcb26f254cad9196c401b23df7213f6df3fa1c6371c0; __init__.py a6ab8559aca3c4a5e9ebcea003145e305202e4e31a3c60fa41232d4bcbf2dc52; test_catalog.py 4251c8d064600ce541a55e34e047a4d9e3940de15b0db612c8e59c612b555a18; test_catalog_linux.py 053f5f8d2001dcde75b8eab637d3e19539a0295eed368b32d07de85247076478.

P2 Nummer1 ist im gelesenen Source ADDRESSED. register_file (:462–515) liest die aktive Zuordnung auch bei definitiv fehlendem/unzulässigem Ziel. Der None-Zweig setzt deren Tombstone, legt keine neue Zuordnung an und verlässt `_operation` regulär. Erst nach erfolgreichem Commit sowie Verbindung-/Descriptorschluss folgt MEDIA_UNAVAILABLE außerhalb des Kontextmanagers. Eine fehlgeschlagene SQLite-Aktualisierung oder ein Commitfehler führt weiterhin zum sicheren Storefehler und Rollback. Der technisch ungewisse OSError-Zweig bricht vor der Invalidierung ab und bewahrt die aktive Zuordnung. Unveränderter Erfolg und regulärer Ersatz behalten ihre bisherige Identitätsentscheidung.

P2 Nummer2 ist im gelesenen Source ADDRESSED. `_schema_objects` (:206–215) betrachtet sämtliche Objekttypen von sqlite_master und entfernt ausschließlich Namen mit dem wörtlichen internen Präfix sqlite_. Bootstrap verlangt version0 und keine verbleibenden Objekte. `_verify_schema` (:248–282) fordert exakt die zwei eigenen Tabellen und den benannten aktiven Index und prüft die vorhandenen Spalten-/Indexeigenschaften weiter. Damit wird eine fremde View ohne Tabelle vor Schemaanlage abgelehnt; zusätzliche fremde Views, Trigger oder Indizes einer bestehenden Katalogdatenbank werden ebenfalls abgelehnt. Die normale SQLite-Autoindexbehandlung bleibt möglich.

Keine neuen P1-/P2-Befunde im Fix oder im damit erneut bewerteten Vier-Dateien-Branch. Die bestehende geschlossene API, descriptorrelative Linuxgrenze, Rootbindung, kurzen serialisierten SQLite-Transaktionen, dauerhaft gesetzten Tombstones und festen sicheren Fehlertexte werden durch den Fix nicht erweitert oder abgeschwächt. Der vorher vermerkte ValueError bei nachträglich beschädigten internen Integer-TEXTwerten bleibt ein zurückgestellter kleiner Robustheitshinweis unter der eigenen vertrauenswürdigen Storevoraussetzung, kein offener P2.

Root meldet tatsächlichen Regression-RED vor diesem Quellenfix in Run39031175203/Job117391760598 (Python3.11) und Run39031172465/Job117391752153 (Python3.12): genau die zwei neuen Assertions scheiterten mit AVAILABLE statt MISSING beziehungsweise akzeptierter fremder View. Diese Remoteprotokolle wurden nicht vom Reviewer selbst abgerufen. Die Regressionen bleiben im finalen Testhash unverändert erhalten.

Unabhängig frisch ausgeführt am finalen Stage: Console-pytest mit importlib-Modus und deaktiviertem Cacheprovider liefert auf Windows Exit0, 2passed/21skipped. Gezielter V3lint aller vier Dateien mit den oben dokumentierten Parametern liefert Exit0 ohne Meldungen. Dies belegt keine Linux-Verhaltensfreigabe. Keine ausführbaren Probes, Tests oder Produktänderungen vom Reviewer; ausschließlich diese Prosa ergänzt.

Quellreview abgeschlossen: beide bisherigen P2 im Source adressiert, kein verbleibender blockierender Reviewbefund. Die tatsächliche vollständige Python3.9–3.13-Linuxmatrix und vollständiger Repository-V3lint am eingefrorenen Head bleiben vor Integration erforderlich; ein Grün wird hier nicht vorweggenommen. Root übernimmt Remote-Readback, CI-Abnahme und Publikation. Keine zusätzliche MPD-, GUI-, ARMv6-, Geräte- oder Audiofreigabe durch diesen Reviewabschluss.
