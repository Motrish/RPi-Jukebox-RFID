# R01b – unabhängiges Source-/Gesamtreview

Vier P2 vor Integration zu korrigieren. Vollständiger Plan samt Rootruling, Testreview/Bericht, beide eingefrorenen Dateien und R01a-Abhängigkeit gelesen. Source589a572c038eab4b91490750fb01fd292f6b845af2e19e6e6ad743c2848d99bb, Testsaaede173d17bdcb5ecd8043afc1fc63d6293ade3585c1114aa1bfba3b45463a9, unverändertesR01a-Toolb45005aa629c2ed7ed2b66a0bdb02acb3f4f636395d1d84063c3e04df8fc48ee. Kein Code/Probe/Test/GitHubzugriff durch Reviewer verändert. Prosa-Schreibversuch scheiterte; Root speichert den Handoff.

1. P2 – bundle.py:354–358: Consumer-Exceptions ändern Typ/Identität. yield liegt in der Intake-Fehlerübersetzung; ValueError/OSError/TypeError/KeyError/OverflowError des Aufrufers werden BundleError. Intakeübersetzung vor yield beenden, eigene Bereinigung im finally behalten. Regression mit denselben ValueError-/OSError-Objekten im Context, Identität und Cleanup verlangen.

2. P2 – bundle.py:322–323: Ungültiger DEFLATE kann zlib.error ungefiltert liefern. Dies ist ein dokumentierter gzip-Formatfehler: [Python3.9 gzip](https://docs.python.org/3.9/library/gzip.html#gzip.BadGzipFile). An der Dekompressionsgrenze sicher in BundleError übersetzen. Regression mit gültigem gzip-Header/ungültigem DEFLATE und passendem Manifest; BundleError und Cleanup verlangen.

3. P2 – bundle.py:304–307: Dateimodus0644wird durch Caller-umask077zu0600, verletzt den festen Outputvertrag. Finalen POSIXmodus explizit setzen, Caller-umask nicht global verändern. POSIX-Regression: gültiges Bundle unter umask077bereitstellen,0644verlangen, Testumask im finally wiederherstellen.

4. P2 – bundle.py:91–92: NurC0/DEL geprüft, C1-Steuerzeichen U+0080–009F bleiben erlaubt. R01a-Produzent verwirft alle Unicode-Cc-Zeichen. Effektive Pfade mit derselben Definition prüfen. Regression mit U+0085-Dateiname und passendem Manifest, Ablehnung und Cleanup verlangen.

Review endet am eingefrorenen Stand. Root hat denselben2Dateiinhalt in PR19als f4de3536036346e350c154ab961f970a97c1cfb4/Baumcc06a493c69b01170f4ea8e43207ac4c0930b05d publiziert und bytegleich zurückgelesen. Lokale35R01b-/15R01a-/10I01a-Suites bestanden mit OSskips, V3lint bestanden; tatsächliche neue Vollcheckout-CI läuft. Laufende alte Quelle ist noch keine Abnahme der notwendigen vier Korrekturen.

## Enger Abschlussreview an korrigiertem Freeze

Unabhängiger Reviewer bestätigt Source6e66a3b49cb5c71240cecbb046bfd136bc069d8cd950490f23b1fe1fa874dd9d und Testsd7a3176bf8d300a4fa0d2348d5c5b0496658a783f54f16ecc54103584f40b465. Alle4P2geschlossen: Consumer-Exceptions unverändert außerhalb Intakeübersetzung, finally-Cleanup erhalten; zlib.error behandelt; POSIXfchmod0644ohne Caller-umaskänderung; sämtliche Unicode-Cc-Zeichen abgewiesen. Vier neue Regressionen decken Befunde direkt. Keine Rest-P1/P2in den Korrekturen und betroffenen Kontrollflüssen. Review rein lesend, keine Probes/Tests/Codeänderungen. Tatsächliche Linux-CI an617d2fd1 bleibt separate Root-Abnahme vor Integration.

Root-Ausführungsabschluss: Beide vollständigen tatsächlichen Pythonmatrizen39058605235/39058602622 einschließlich aller3.9–3.13undfinish bestanden;3.9Log250/250inklusive aller39Intakefälle samt Linux-FIFO/umask. PR19als2002cc2cintegriert, geprüfter Sourcebaum unverändert3dd4b224..., Eltern/Produktref/develop bestätigt. Damit auch separate Runtimeabnahme am überprüften Sourcehead erfüllt. Keine weitergehende Installer-/Geräte-/Webbootstrapbehauptung.
