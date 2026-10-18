# Lokale Codingkapazität: Ollama und RTX5080

Stand18.10.2026. Nutzervorgabe: lokale Rechenleistung für Coding einsetzen, spätestens bei höchstens10% verbleibendem Codexkontingent ausschließlich lokale Coder; unabhängige Reviews weiterhin ausdrücklich gpt-6.1-sol.

## Tatsächlich geprüft

| Bestandteil | Nachweis |
| --- | --- |
| GPU | NVIDIA GeForce RTX5080,16303MiB VRAM, Treiber610.88 |
| Ollama | Version0.40.6, bestehender lokaler API-Dienst |
| Modell | qwen2.5-coder:14b, durch den Nutzer installiert |
| Modellformat | 14.8B, Q4_K_M,8988124298Bytes laut lokalem Modellregister |
| Digest | 9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849 |
| Lokalität | /api/show meldet keinen remote_host; exakter lokal installierter Modellname verwendet |
| Laufzeit | 8192Kontext-Tokens, ungefähr10GB Modell-/Laufzeitbelegung,100%GPU laut ollama ps |
| Reale Generierung | Vollständige lokale API-Antwort mit done=true und done_reason=stop,2220Ausgabetokens in rund31Sekunden; weitere kleine Antwort rund19Sekunden |

Die Laufzeitangaben belegen lokale Inferenz, keine allgemeine Produktcodequalität. Die initiale größere Zwei-Dateien-Probe war syntaktisch/protokollseitig ungeeignet. Ein zusätzliches Transportskript bestand das unabhängige6.1-sol-Review nicht vollständig und wird nicht eingesetzt. Sämtliche Probequellen sind als .rejected.txt unter G:/Entwicklung/phoniebox-tools/local-coder erhalten; sie sind weder aktive Tools noch Teil des Phonieboxforks. Ungeprüfter Code wurde nicht in das Produkt übernommen.

## Verwendeter Arbeitsweg

Der Koordinator übergibt kleine schriftliche Aufgaben und nur explizit benötigte öffentliche Projektquellen direkt an die bestehende Ollama-Chat-API unter `http://127.0.0.1:11434`. Modellname bleibt `qwen2.5-coder:14b`, Kontext8192, höchstens4096Ausgabetokens pro kleinem Auftrag. Qwen erhält keinen Thinkingparameter; dessen lokale Modellcapabilities enthalten kein Thinking. Strukturierte Antwortformate begrenzen den Rückgabevertrag, ersetzen aber keine Syntax-, Test- oder Reviewprüfung.

Lokale Antworten werden als Kandidaten gespeichert. Kein Modell erhält automatische Shellausführung, GitHubschreibrechte oder die Befugnis, seine eigenen Tests/Reviews zu umgehen. Übernahme erfolgt nur auf exklusiven Dateipfaden nach den vorhandenen Prüfregeln. Sol schreibt weiterhin keinen Code. Bei komplexen Aufgaben zuerst weiter zerlegen, statt ungeprüfte große Komplettmodule anzufordern.

Reviews verwenden gpt-6.1-sol mit begrenztem Diff und relevantem Testnachweis. Bereits bestandene unveränderte Prüfungen werden nicht ohne neuen Grund wiederholt. Koordination und Reviews benötigen weiterhin Codexkontingent; lokale Codegenerierung allein verbraucht dafür keine Codex-Modellaufrufe.

## 10%-Regel

Die Schwelle meint höchstens10% verbleibendes Codexkontingent. Ein verlässlicher Restwert ist in diesem Toolkontext nicht verfügbar. Kontextfensterfüllung, Ausgabetokenzahl und Taskbudget sind dafür keine Ersatzwerte. Deshalb gilt bereits jetzt vorsorglich: alle neuen Codingaufträge lokal. Eine automatische Kontingentüberwachung oder Umschaltung anhand eines ausgelesenen Prozentwertes ist nicht eingerichtet oder behauptet.

Luna ist nur bei zuverlässig bestätigtem Restwert über10% und ausdrücklich gewählter Ausnahme möglich; ohne solchen Nachweis kein Cloud-Codingfallback. Reviews bleiben auch unter10% bei6.1-sol. Ist das gesamte Codexkontingent erschöpft, sind weitere Koordination/Reviews dieses Threads nicht garantiert; es existiert kein Scheduler zur selbstständigen Wiederaufnahme.

## Download und Arbeitsplatz

Der erste autorisierte Downloadversuch für Qwen scheiterte an der Sandbox-Netzwerksperre. Der Nutzer hat das Modell anschließend mit seinem bestehenden Ollama installiert. Der allein für den ersten Versuch gestartete separate Loopbackdienst PID55852 wurde beendet. Bestehende Ollama-Einstellungen wurden nicht dauerhaft geändert.

Modellgewichte und rohe Generierungsartefakte werden nicht in GitHub veröffentlicht. Der Produktbranch bleibt741085f902c88aaa2fa74ef5dcd473ba993427e3. Die neue Ressourcenregel und dieser Nachweis sind Prosa; die einzige operative Aufgabenliste bleibt tasks/todo.md.

## Quellen

- [Ollama-Modellkarte](https://ollama.com/library/qwen2.5-coder:14b)
- [Ollama-Chat-API](https://docs.ollama.com/api/chat)
- [GPU-/Kontextanzeige](https://docs.ollama.com/faq)
- [Offizielle Codex-Befehle](https://learn.chatgpt.com/docs/developer-commands?surface=cli)

Hardware, Modellinstallation und Antwortstatistiken wurden lokal tatsächlich abgefragt. Externe Dokumentation ist keine Messung der eigenen GPU oder des Codex-Restkontingents.

## Aktualisierte Aufgabenverteilung nach Nutzersteuerung

Neueste Vorgabe18.10.2026 ersetzt die frühere vorsorgliche Sperre von Cloudcodern bei unbekannter Restquote: einfache Aufgaben lokal mitQwen, komplexere Aufgaben dürfen wieder anLuna/Subagents gehen, unabhängige Reviews6.1-sol. Bestätigt höchstens10% Restkontingent bleibt eine lokale Codinggrenze; kein zuverlässig auslesbarer aktueller Wert. Keine Astra- oder Sol-Codingrolle. Ressourcenpolicy und einzige operative Liste tasks/todo.md sind maßgeblich.

Tatsächlicher erster Produktbeitrag: vier kleine unittest-Vertragstests für I02a, nach lokaler Qwen-Generierung, begrenzter Nacharbeit und unabhängigem Review integriert als PR21/ec56e0c1. Der Koordinator normalisierte nur zwei Leerzeilen ohne Änderung der Codetokens. Vollständige Source- und Merge-CI bestanden. Große Erstentwürfe blieben verworfen; generische Probewrapper sind weiterhin nicht freigegeben.
