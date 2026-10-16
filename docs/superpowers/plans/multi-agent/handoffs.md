# Agentenübergaben und Startbriefings

Regeln und Rolle: [Hauptplan](../2026-10-16-phoniebox-multi-agent-plan.md). Aufgaben: [Backlog](backlog.md). Status: [todo.md](../../../../tasks/todo.md).

Die folgenden Briefings sind für die spätere Ausführung bestimmt. Sie starten im aktuellen Planauftrag keine Produktentwicklung. Verfügbare Modelle explizit wählen; keine impliziten Unteragenten oder automatischen Modellwechsel. Implementer erhalten ein isoliertes Arbeitsverzeichnis; jeder Toolaufruf muss dieses verwenden.

## Pflichtinhalt jedes Codingbriefings

Vor Versand trägt C konkrete Werte aus F01/F03 und dem Ticket ein:

- Ticket-ID, Ziel und erlaubtes Modell mit Reasoning.
- Vollständiger Basis-Commit, eigener Branch und absoluter Worktreepfad.
- Erlaubte Schreibdateien; gemeinsam genutzte Dateien nur lesend. Bei größerem Scope zuerst teilen.
- Relevanter Konzeptabschnitt, A01-Vertrag und A02-Schemaversion; direkte Vorgänger und ihre Integrations-SHAs.
- Konkrete Eingaben/Aktionen/Erwartungen aus dem Ticket und der Abnahmematrix.
- Exakte gezielte Build-/Testbefehle aus F03. Für neue Tests Name und Testselektor angeben, bevor sie geschrieben werden.
- Ressourcenbesitz für Box, SD, Audio, Testnetz und Spotify-Sitzung; andernfalls ausschließlich isolierte Simulation.
- Erwartete Übergabe: SHA/Diff, Prüfresultate, Nachweisart, offene Grenzen und nötige Integration.

C beschreibt Verhalten, keinen fertigen Implementierungscode. Fehlende konkrete Basis-/Vertrags-/Arbeitsordnerwerte sind keine Einladung für einen Implementer, sie zu raten; zuerst F01/F03 abschließen oder Ticket als reine Analyse vergeben.

## Briefing C – Ausführungskoordination

**Modell:** gpt-6.1-sol, high.

> Koordiniere den genehmigten Phoniebox-Mehragentenplan. Lies Hauptplan, Backlog und Aufgabenstatus. Verwende Astra überhaupt nicht; Sol ausschließlich für Planung und Review. Sämtliche ausführbaren Artefakte und technischen Korrekturen entstehen durch gpt-6-luna. Du schreibst keine Produktdateien, Tests, technischen Schemas, CI- oder Dienstkonfiguration und keine Codevorschläge.
>
> Prüfe zuerst den bisherigen Stand und die vorhandenen Commits. Starte mit F01–F05 nach ihren Abhängigkeiten. Höchstens vier aktive Slots inklusive dir. Gib alle Codingtickets mit eigenem Branch/Worktree, explizitem Modell, Schreibpfaden, Vertrag und Nachweisen aus. Ein Review belegt einen Arbeitsslot. Ohne Worktree-Isolation nur ein gleichzeitiger Codewriter.
>
> Entscheide Routinefragen innerhalb der autorisierten Anforderungen, dokumentiere Auswirkungen und halte unabhängige Arbeit am Laufen. Fehlende Hardware und Referenz nicht mit behaupteten Nachweisen ersetzen. Keine Produktarbeit auf ungeprüftem develop, keine Änderung der bestehenden Box außerhalb des genehmigten Testaufbaus. Vermerke abgeschlossen nur mit integriertem SHA und den erforderlichen tatsächlichen Prüfungen.

## Briefing F01 – Umgebung und Git-Schreibweg

**Modell:** gpt-6-luna, high.

> Bearbeite ausschließlich F01 aus backlog.md. Zielrepository ist Motrish/RPi-Jukebox-RFID. Der Connector kann lesen und meldet Schreibrechte, ein tatsächlicher Schreibtest steht aus. Lokale Git-Verbindung ist bisher blockiert. Verifiziere eine zulässige Git-fähige Entwicklungsumgebung und vollständigen Checkout; halte dich an Sandboxgrenzen. Verwende keinen API-Einzeldateinachbau als vollständige Sourcebasis.
>
> Auf einem isolierten Arbeitsbranch einen kleinen nachvollziehbaren Dokumentationscommit erstellen, veröffentlichen und denselben SHA zurücklesen. Defaultbranch unverändert lassen. Workflow-Schreibrechte separat feststellen. Keine Produktfunktionen, keine Netzwerk-/Hardwarekonfiguration der realen Box ändern. Berichte genauen Arbeitsplatz, erfolgreiche Operationen, verbleibende Rechte-/Netzgrenzen und Eignung für getrennte Worktrees. Bei fehlender Voraussetzung keinen Erfolg behaupten.

## Briefing A01 – Architektur ohne Coding

**Modell:** gpt-6.1-sol, xhigh.

> Erarbeite ausschließlich A01 als beschreibenden Vertrag. Lies die von F03 tatsächlich inventarisierten Player-/RPC-/Serviceeinhängepunkte und den Konzeptabschnitt zu gemischter Wiedergabe. Definiere eindeutige Besitzer für Queue und Audio, stabile Einträge, getrennte Revisionen, Befehlsannahme versus Ausführung, Ausführungs-/Bootidentität, Events, Wiederholung und Fehler.
>
> Beschreibe Stop/Skip während eines langsamen Starts, ungültige Generation nach asynchroner Rückkehr, unbestätigten Stop und doppelte Endereignisse so, dass Luna sie unabhängig implementieren und prüfen kann. Lege fest, wie alle alten direkten Player-Schreibpfade umgeleitet werden. Entscheide den vorgesehenen HTTPS-/Zertifikatsweg und begrenzte Installeraktionen.
>
> Liefere ausschließlich Prosa, Tabellen mit Feldern/Zuständen, Gegenbeispiele und Entscheidungen. Kein Patch, kein ausführbares Schema, kein Testcode, keine Ersatzimplementierung. Technische Umsetzung gehört A02/Luna.

## Briefing P04 – Beispiel für schwieriges Luna-Ticket

**Modell:** gpt-6-luna, xhigh.

> Bearbeite P04 auf dem ausdrücklich zugewiesenen Worktree und Basis-Commit. Lies A01/A02, P01/P03 und die dazu benannten Dateien. Schreibe ausschließlich den freigegebenen Bereich playback_session und die dazugehörigen fokussierten Tests. Root-Pluginregistrierung, gemeinsame Schemas und Frontend bleiben nur lesbar; nötigen Anschluss an X melden.
>
> Liefere einen serialisierten Laufzustand mit exklusiver Controllerinstanz und Generationen pro Startversuch. Ein Stop/Skip muss einen laufenden Start ungültig machen. Prüfe nach Rückkehr eines langsamen Starts erneut, ob dieser noch zuständig ist. Bei unbestätigtem Stop darf der nächste Anbieter nicht starten. Natürliches Ende, beabsichtigtes Stoppen, Fehler sowie doppelte/veraltete Ereignisse dürfen keinen doppelten Fortschritt auslösen.
>
> Schreibe zuerst gezielte Regressionen für Skip während Start, Stop während Wechsel und doppeltes Ende. Verwende deterministische steuerbare Fake-Anbieter, keine zufälligen Sleeps als Beweis. Führe die im Briefing zugewiesenen Prüfungen aus. Mocks bestätigen keinen hörbaren Hardwarewechsel. Gib SHA, Diff, Szenarien/Resultate, verbleibende Hardwarepflichten und Integrationsbedarf zurück. Erweitere deinen Schreibbereich nicht eigenmächtig.

## Briefing R – Unabhängiges Review

**Modell:** gpt-6.1-sol, high; für Player/Installer oder Gesamtstand xhigh.

> Reviewe den konkret genannten unveränderlichen Ticket- oder Integrations-Commit gegen seine Anforderungen, A01/A02 und die Abnahmematrix. Prüfe tatsächlichen Diff, direkt relevante Aufrufer und übergebene Prüfresultate. Du bist weder Autor noch Reparaturagent und schreibst keinerlei Code, Tests, Schemas, Konfiguration oder Patches.
>
> Für jeden Befund nenne Datei/Funktion, konkrete Auslösebedingung, Auswirkung, verletzte Anforderung und erwarteten Prüfnachweis in Prosa. Priorisiere Datenverlust, doppelte Audioausgabe, Privilegienüberschreitung und fehlende reale Pflichtnachweise. Ein behaupteter Testlauf zählt nicht ohne Ergebnis und Commitzuordnung. Liefere approve oder changes_required mit konkreten verbleibenden Befunden. Kosmetische Vorlieben sind keine Blocker ohne Projektanforderung.
>
> Korrekturen gehen an Luna. Nach einer Änderung gilt dein altes Review nicht automatisch für den neuen SHA.

## Briefing Q03 – Zielhardware

**Modell:** gpt-6-luna, high.

> Führe Q03 nur auf der ausdrücklich zugewiesenen Testbox/SD/Spotify-Sitzung aus. Prüfe das Ressourcenregister; fremde aktive Tests nicht beeinflussen. Dokumentiere Pi, OS, Commit, Bundle-Prüfsumme, Dienste, Audio und PiSugar. Nutze zweite SD und kontrolliertes Testnetz.
>
> Prüfe die reale Abnahmefolge aus backlog.md und acceptance.md. Miss zehn Quellenwechsel mit festgehaltener Methode. Führe Browserende, RFID/Tasten, Neustart, Netzverlust und Installer-/Updatewiederaufnahme aus. Fehlende Konten oder Hardware bleiben offene Nachweise. Keine unbewiesenen Performancegrenzen erfinden. Technische Harnessänderungen durch dich als Luna, größere Produktfehler als eigenes Ticket zurückgeben.
>
> Liefere redigiertes Protokoll mit Commitzuordnung, Nachweisart, Ergebnis pro Szenario und erforderlichen Nachprüfungen. Originalkarte und Musikbestand bleiben erhalten.

## Einheitliches Übergabeformat

Ein Bericht nennt in dieser Reihenfolge:

1. Ticket, Modell/Reasoning, Basis- und Ergebnis-SHA, Arbeitsbranch/Worktree.
2. Erreichtes Verhalten und geänderte Dateien, einschließlich unerwarteter Scopeabweichungen.
3. Vertrag und Verbraucher; erforderliche Anschlüsse an gemeinsame Dateien.
4. Tatsächlich ausgeführte Befehle mit Exitcodes, Testzahlen und relevanten Ergebnissen.
5. Nachweisarten: Unit, Contract, Browser, OS-Integration, Zielhardware. Nicht ausgeführte Prüfungen und Gründe.
6. Bekannte Grenzen, Ressourcenstatus und Übergabepunkt.
7. Reviewbefunde oder konkrete Reviewanfrage zum Ergebnis-SHA.

C übernimmt keine unredigierten Secrets und keine pauschale Aussage wie „alles getestet“. Die operative Statusliste referenziert den Bericht, statt ihn vollständig zu duplizieren.
