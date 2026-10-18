# U03a1 – unabhängiges Testreview vor Produktimplementierung

Stand: 17.10.2026. Gelesen: tasks/u03-library-api-plan.md einschließlich Root-Freigabe und der eingefrorene Teilstage test/library_api/test_server.py. Selbst ermittelter Test-SHA256: 7b62bb020a94b9b00cba0e41db797a8171b101ddf6d213e23ed868a30740dbf8. APIproduktquellen sind absichtlich noch abwesend. Ausschließlich statisches Testreview; keine Produktimplementierung beurteilt und keine ausführbaren Probes, Tests oder Diagnoseskripte durch den Reviewer verfasst.

## P2 – Requesthelper erzeugt doppelte Hostheader bei erlaubten Requests

Ort: test/library_api/test_server.py:98–105 und :113–117.

HTTPConnection.putrequest wird ohne skip_host=True aufgerufen. Der Standardwert ist False, weshalb die Standardbibliothek einen Hostheader erzeugt. Anschließend fügt der Helper den Host aus valid_headers ausdrücklich erneut hinzu. Eine planmäßig korrekte API muss diese scheinbar erlaubten Requests wegen mehrfachen Host ablehnen. Damit treffen die Erfolgs-, Auth-, Paging- und Backendfehlertests den vorgesehenen Codepfad nicht; manche Ablehnungstests können zudem aus dem falschen Grund bestehen.

Der Standard wurde direkt in der vorhandenen Python3.12-Quelldatei Lib/http/client.py:1138–1146 und :1189–1238 gelesen; kein Netzwerkprobe benötigt. Der enge Fix ist, die automatische Hostausgabe im Helper auszuschalten und sämtliche Hostheader ausschließlich aus den expliziten Testheadern zu senden. Die gezielte Doppel-Host-Gegenprobe muss weiterhin zwei Header erzeugen und abgewiesen werden. Keine Abschwächung der Single-Host-Produktgrenze.

## P2 – Zweite Autorisierungsprüfung wird durch behaltene Aufrufhistorie falsch getestet

Ort: test/library_api/test_server.py:230–245, im Zusammenhang mit :81–83.

Die Schleife für False/None/1/yes leert auth_calls vor jedem Request. Nach ihrem letzten Request bleibt ein Aufruf gespeichert. Der folgende Autorisierer verlangt len(auth_calls)==1, während `_authorize` bereits vor der Delegation einen neuen Aufruf anhängt. Der nächste Request beginnt daher bei Länge2, scheitert sofort an der ersten Autorisierung und erreicht den Katalog nicht. Die spätere Erwartung genau eines list_media-Aufrufs kann bei korrektem Produktcode nicht erfüllt werden.

Vor dem separaten Zweitpass-Szenario die Authhistorie leeren. Dann liefert der erste Gateaufruf exakt True, der Katalog wird einmal gelesen und erst die zweite Gateprüfung verweigert die Ausgabe. Die bestehenden Erwartungen 401, keine Metadaten und genau ein Katalogaufruf bleiben erhalten.

## P2 – Effektfreier Import und sicherer CLIstart sind noch ohne Tests

In der vorliegenden Datei wird ausschließlich das Servermodul für die Testausführung importiert; es gibt keinen frischen Import unter beobachteter Effektgrenze und keinen CLItest. Der Plan verlangt dagegen ausdrücklich effektfreie Exporte und Imports, TTYpflicht vor Secretgenerierung/-ausgabe, keinen automatischen Ersatzkatalog bei fehlender/leerer/fremder Datenbank sowie finally-Cleanup des manuell gestarteten Servers und selbst erzeugten Katalogs.

Vor Quellenimplementierung ist dafür eine kleine begrenzte Gruppe von Tests erforderlich: Import der vorgesehenen API-/CLI-Module ohne Katalog-/Socket-/Secretwirkung; CLIablehnung ohne interaktive TTY ohne Secretleck oder Listeneröffnung; vorhandener gültiger Katalog als Startvoraussetzung ohne Erzeugung eines fehlenden/ungültigen Ersatzes; Cleanup der vom Runner selbst erzeugten Ressourcen bei Ende oder Startfehler. Synthetische Werte und kontrollierte CLIabhängigkeiten genügen; keine echte Zugangsausgabe, kein Gerätestart und keine neue öffentliche Schnittstelle zur Testbequemlichkeit. Dies ist ausdrücklich planverlangte Sicherheitsabnahme, kein zusätzlicher Funktionsumfang.

## Begrenzte Abdeckung und Übergabe

Die vorhandenen HTTPfälle decken nach Helperkorrektur einen sinnvollen Kern ab: zwei erlaubte Reads, Auth vor/nach Katalog, TTLgrenze, feste Routen/Methoden, Bodyablehnung, Größenlimits, sichere Backendfehler und geschlossene Header-/Antwortfelder. Die zwei konkreten Testfehler dürfen nicht durch Lockerung dieser Erwartungen umgangen werden.

Zusätzlich fehlt noch der ausdrücklich geplante Linuxfall mit echtem P01b-Tempkatalog und registrierter regulärer Datei. Die bisherigen 16 Fälle verwenden nur FakeCatalog. Root hat nach der Rückmeldung genau eine solche begrenzte Interopergänzung zusammen mit den drei P2-Testkorrekturen autorisiert; weiterhin keine APIproduktquellen in diesem Schritt. Keine breitere neue Testmatrix oder Player-/GUI-/Geräteabnahme gefordert.

Handoff: drei P2-Befunde, keine P1-Befunde. Tests nach den engen Änderungen neu einfrieren und seriell nachprüfen; tatsächlicher lokaler Console/importlib-RED vor Quellenstart bleibt Roots TDDcheckpoint. Dieses Review behauptet keinen ausgeführten HTTPpass, Linux-Interopass oder vollständigen CIpass. Danach Produktimplementierung und eigene Quellenprüfung; vollständige bestehende Python3.9–3.13-/Lint-CI vor Integration bleibt erforderlich. Ausschließlich diese Prosa geschrieben, keine Remoteänderung.

## Enges Phase1-Folgereview – eingefrorener Teststand8d45da34

Stand: 17.10.2026. Testdatei erneut gelesen; selbst bestätigter SHA256 8d45da345c965f9169983a20300dacf83170db0cb78f0ab9b00ade04dca0ab03. Produktquellen weiterhin absichtlich abwesend. Keine neuen blockierenden Testbefunde.

Die zwei konkreten Helper-P2 sind korrigiert: request (:110) setzt skip_host=True; die ausdrücklich gelieferten Header kontrollieren damit exakt die Hostanzahl, einschließlich der erhaltenen Doppel-Host-Gegenprobe. Das Zweitpass-Szenario (:258–264) leert Auth- und Kataloghistorie vor seinem eigenen Request. Der erste Authorizeraufruf kann nun genau True liefern, der Katalog wird einmal gelesen und die zweite Prüfung verweigert die Ausgabe. Die ursprünglichen Erwartungen wurden dafür nicht abgeschwächt.

Die fehlende CLI-/Importsicherheitsabdeckung ist für diesen begrenzten Testcheckpoint ergänzt. Ein frischer Kindprozess (:507–539) verbietet Bind/Listen, SQLiteöffnung und Secretgenerierung vor dem Import aller drei vorgesehenen Module; er verlangt fehlerfreien Import und keine stdout-Ausgabe. Der echte nichtinteraktive CLIaufruf (:541–576) ist auf fünf Sekunden begrenzt und verlangt fehlgeschlagenen Start, keine Datenbankanlage, keinen tokenförmigen Output und keinen zurückbleibenden Listener. Die kontrollierte TTYprüfung (:578–638) fordert Ablehnung des uninitialisierten Schema0-Stores vor jedem Bind, erhält dessen Tabellen-/Versionszustand und verlangt keine Tokenausgabe. Dies beseitigt den bisherigen vollständig ungetesteten CLI-/Importpfad, ohne echte Secrets zu verwenden.

Der eine geplante Linux-Interopfall (:641–679) verwendet einen echten P01b-Tempkatalog und eine ausdrücklich registrierte reguläre Datei. List und Get laufen über echte Loopback-HTTPrequests und müssen exakt die realen geschlossenen Katalogwerte liefern. Nur Nicht-Linux skippt diesen Fall. Server und aufrufereigener Katalog werden in getrennten finally-Blöcken geschlossen. Insgesamt nun 20 deklarierte Fälle, davon 19 portable und ein tatsächlicher Linux-Katalogfall.

Begrenzte Restprüfgrenze: Ein eigener Test für das finally-Cleanup des produktiven CLIrunners wurde nicht ergänzt. Dessen Ressourcenbesitz und Cleanup bei Startfehler/Ende werden im anschließenden Quellreview ausdrücklich geprüft; hieraus wird kein weiterer vorgezogener Testmatrixauftrag abgeleitet. Keine Aussage zu Produktcode, der in diesem Stand noch nicht existiert.

Gezielter V3lint der eingefrorenen Datei mit den zuvor dokumentierten Repositoryparametern unabhängig ausgeführt: Exit0 ohne Meldungen. Root meldet tatsächlichen lokalen Console/importlib-RED am fehlenden APIproduktmodul. Der Reviewer behauptet weder einen ausgeführten HTTP-/CLI-Gesamtpass noch Linux-Interop-Green an diesem Quellenlosstand. Die drei bisherigen Test-P2 blockieren nach diesem Folgereview den engen Quellenstart nicht mehr. Übergabe an Roots TDDcheckpoint und anschließende serielle Quellenprüfung; ausschließlich Prosa geschrieben, keine ausführbare Datei und keine Remoteänderung.

## Erstes serielles U03a1-Quellreview – eingefrorene Produktquellen

Stand: 17.10.2026. Plan erneut gelesen; `__init__.py`, server.py und `__main__.py` vollständig gegen die eingefrorenen Tests und den engen Devloopback-Vertrag geprüft. Selbst bestätigte SHA256: `__init__.py` f543855fc907cde27d798970704eb4407d156425c732f77a88d57152012a0b1d; server.py 94326c7911b423c3f3b29609e6ad22f810821c583073d464020fb31560a2c5de; `__main__.py` 6c3f89f93e77b3af2eba29fe70a6a2266926e5a9302710a87f483a18bdc43328; test_server.py unverändert 8d45da345c965f9169983a20300dacf83170db0cb78f0ab9b00ade04dca0ab03.

### P2 – CLI schließt seinen HTTPserver nicht

Ort: src/jukebox/components/library_api/`__main__.py`:63–68 und :125–127.

Der finally-Block übergibt sowohl den Server als auch den Katalog an `_close_quietly`. Dieser Helper ruft ausschließlich value.close auf und unterdrückt sämtliche Exceptions. Der von make_server gelieferte HTTPServer besitzt server_close, aber keine close-Methode. Damit wird AttributeError verschluckt, ohne den Listening-Socket ausdrücklich zu schließen. Der eigene Katalog wird zwar geschlossen, der selbst erzeugte Listener bleibt beim Rückweg aus main beziehungsweise bei Start-/Laufzeitfehlern bis zu späterer Objektfreigabe oder Prozessende offen. Dies verletzt die ausdrückliche Runner-finally-Anforderung und ist insbesondere bei kontrollierten Startfehlern oder erneutem Aufruf von main relevant.

Der enge Autorenfix muss die tatsächliche server_close-Methode aufrufen und den Katalog unabhängig davon weiter schließen. Kein shutdown-Aufruf aus demselben noch laufenden serve_forever-Thread als Ersatz erforderlich. Eine kleine kontrollierte CLIregression mit synthetischem, aufgefangenem Token und fake/gezählten Ressourcen genügt: serve_forever beenden oder auslösen lassen und server_close sowie catalog.close auch auf dem Fehler-/Interruptpfad nachweisen. Dafür keine neue API, kein echtes Secret und keine neue Netzwerkdiagnostik einführen.

Die Standardbibliotheksquelle socketserver.py:489–495 wurde gelesen: TCPServer.server_close schließt den Socket. Kein ausführbarer Reproducer vom Reviewer geschrieben. Root hat den Befund nach eigener Quellenlesung ebenfalls bestätigt und hält die Veröffentlichung bis zum Test-RED/Fix zurück.

### Übrige eng begrenzte Quellenprüfung

Keine P1-Befunde und keine weiteren P2-Befunde. Der Factoryexport ist effektfrei; nur die zwei Katalogreads sind über die festen Routen erreichbar. Der Listener ist ein serieller IPv4-HTTPServer auf 127.0.0.1 mit Queue4 und fünf Sekunden Inaktivitätstimeout. Die rohe Requestline wird ausdrücklich für das Target verwendet, sodass die stdlib-Normalisierung führender Doppelslashes keine erlaubte Route erzeugt. Kanonische ASCIIparameter, feste Hostauthority und Origin, einzelne Authorization, Body-/Header-/Targetlimits und die geschlossenen Nicht-GET-Pfade sind im gelesenen Code nachvollziehbar. HEAD gibt keinen Body aus. Keine CORSantwort und keine produktiven Request-/Tracebacklogs.

Das Gate verlangt exakt True und wird vor dem Backend sowie nach Projektion und JSONserialisierung erneut geprüft. Ein inzwischen abgelaufener Read wird somit vor Datenausgabe in401 umgewandelt. Backend-/Projektions-/Serialisierungsfehler erhalten feste sichere503-Texte; Zusatzfelder werden abgewiesen, Get muss dieselbe angefragte ID liefern, Cursor muss zum letzten Listeneintrag passen. Kein Rawexception-/Token-/Pfadtext wird absichtlich in Fehlerantworten übernommen. Die ausdrücklich dokumentierte Inaktivitäts- statt Gesamtdeadline und die spätere LAN-/Proxygrenze werden hier nicht zu neuen Anforderungen erweitert.

Die CLI verlangt interaktive stdin/stdout-TTYs vor Secretgenerierung. Vor LibraryCatalog und Listener wird die ausdrücklich vorhandene Datenbank über mode=ro geöffnet und user_version1 verlangt; fehlende/uninitialisierte Stores führen nicht zum automatischen Katalogbootstrap. Der Katalog prüft danach seine volle Schema-/Rootbindung. Der generierte Wert kommt aus secrets.token_urlsafe(32), wird geprüft und nur einmal auf die bestätigte TTY ausgegeben. Der selbst erzeugte Katalog besitzt einen funktionierenden finally-close; der Serverfehler oben ist der einzelne offene Lifecycleblocker.

Gezielter V3lint aller vier Dateien mit den zuvor dokumentierten Repositoryparametern einschließlich max-complexity12 unabhängig ausgeführt: Exit0 ohne Meldungen. Root meldet lokalen bestehenden HTTP-/CLItestlauf19passed/1Linuxskip; der Reviewer hat dafür keinen zusätzlichen ausführbaren Probe verfasst und behauptet keinen vollständigen Linux-Green. Tatsächliche vollständige Python3.9–3.13-/Lint-CI bleibt vor Integration nötig.

Handoff: genau ein P2-Quellenblocker. Erst enge Lifecycle-Regressionsprüfung einfrieren und tatsächlich RED belegen, dann Quellenfix und serielles Folgereview. Kein LAN-/Produktivauth-/React-/Geräteumfang hinzugefügt. Ausschließlich diese Prosa geschrieben; keine Produktdatei, Testdatei, Diagnoseskript oder Remoteänderung durch den Reviewer.

## Abschließendes enges Lifecycle-Folgereview

Stand: 17.10.2026. Selbst bestätigte eingefrorene SHA256: `__main__.py` 899c48d311c1d376bb6905f623fa203f04caf793020a9c44b6554319429c55d4; test_server.py 12bd077d97b1701e0391b0e066cf225910254f959c1c7712420f69a1855b1cf6. `__init__.py` und server.py entsprechen unverändert den oben geprüften f543855f-/94326c79-Hashes. Nur den begrenzten Cleanupfix und die neue Regression nachgeprüft; keine ausführbaren Änderungen oder Probes vom Reviewer.

Der einzelne Lifecycle-P2 ist im gelesenen Source ADDRESSED. `_close_server_quietly` (:63–68) ruft nun server.server_close auf, während `_close_catalog_quietly` (:71–76) catalog.close verwendet. Der abschließende verschachtelte finally-Block (:133–137) sichert den Katalogabschluss auch bei einem unerwarteten Abbruch des Serverabschlusses. Normales serve_forever-Ende, KeyboardInterrupt und Laufzeitfehler erreichen denselben Cleanup. Die vorhandenen frühen TTY-/Schemasperren bleiben unverändert.

Die neue Regression test_cli_closes_owned_server_and_catalog_on_every_exit_path (:641–719) ist kohärent: Drei getrennte Subfälle verwenden einen normal endenden, unterbrochenen beziehungsweise fehlschlagenden gezählten Server und einen eigenen gezählten Katalog. Jeder Fall verlangt exakt einen server_close- und einen catalog.close-Aufruf sowie den vorgesehenen Rückgabestatus. Ausschließlich das bekannte synthetische Testtoken wird injiziert und aufgefangen; stdout muss es genau einmal enthalten und stderr darf es nicht enthalten. Der Fake besitzt bewusst keine close-Methode am Server und reproduziert damit den ursprünglichen Fehler, statt ihn zu verdecken. Kein neu erkennbarer Helperfehler und keine Abschwächung der bisherigen Auth-/HTTP-/CLIassertionen.

Root meldet den tatsächlichen vorherigen RED: Alle drei neuen Lifecycle-Subfälle scheiterten vor dem Fix an0 statt1 Serverabschlüssen. Der Autor meldet nach dem Fix20passed/1Linuxskip einschließlich der Regression und erfolgreichen Lint; Root prüft diesen finalen Lauf und die Veröffentlichung selbst erneut. Der Reviewer hat diese Statusangaben nicht als eigenen Testlauf ausgegeben. Tatsächliche vollständige Linux-Python3.9–3.13-/Lint-CI bleibt vor Integration nötig und belegt erst dort auch die reale Kataloginterop.

Serielles Quellenreview abgeschlossen: kein offener P1-/P2-Befund nach dem eingefrorenen Fix. Kein zusätzlicher Umfang für LAN, Produktivauth, React, Geräte oder Audio. Root übernimmt Remote-Readback, tatsächliche CI-Abnahme und Publikation. Ausschließlich Reviewprosa ergänzt.
