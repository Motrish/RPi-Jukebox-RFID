# U01 – Design aus der bereitgestellten Vorlage

Stand: 17.10.2026. Der Nutzer hat reference/template.webp im Gespräch bereitgestellt; Root hat das Bild tatsächlich gesehen. F05 ist damit erfüllt. Die frühere fehlgeschlagene CDN-Recherche bleibt als historischer Bericht erhalten. Die Referenz bleibt lokal und wird nicht als Produktasset verteilt.

## Beobachtung am Bild

Muzes zeigt eine breite Desktopansicht mit schmaler fester Navigation links, einem ruhigen dunklen Kopfbereich, einer großflächigen violetten Playlistfläche, großzügigen quadratischen Covern in Reihen und einer dauerhaft sichtbaren Playerleiste unten. Flächen sind überwiegend flach; Rundungen konzentrieren sich auf Cover, Suchfeld und kleine Karten. Weiße kräftige Überschriften stehen über zurückhaltendem grauem Text. Die Schrift wirkt wie eine neutrale Sans; die genaue Familie ist aus dem Bild nicht belegbar. Der Musiker im Hero, Künstlerfotos und die äußere dekorative Bildumgebung sind Referenzinhalt, keine Phoniebox-Anforderung.

## Abgeleitete Gestaltung

Die folgenden Farbwerte sind bewusste Annäherungen, keine gemessenen Originalpixel: Seitenfläche #1b2033, Navigation #100d22, erhöhte Fläche #292842, Akzent #a456ed, Haupttext #f7f5fb, Neben-/Hilfstext #c3bed1. Die große Mixfläche darf wie die Vorlage von tiefem Violett zu wärmerem Magenta übergehen; weitere Flächen bleiben ruhig. Spotifygrün dient ausschließlich der Quellenkennzeichnung. Fokus erhält eine deutlich sichtbare helle Kontur und wird nicht nur durch Farbe vermittelt.

Titel: kräftige neutrale Sans, kurze Überschriften mit klarer Hierarchie. Fließtext: dieselbe offline verfügbare System-Sans in normalem Gewicht. Zeit-/Zählerwerte: tabellarische Ziffern. Keine zusätzliche Webfont und kein CDN. Abstände folgen 4/8/12/16/24/32/48; Cover etwa 16–20 px gerundet, übrige Flächen zurückhaltend. Keine permanente Wellenformanimation oder Glas-/Blurflächen.

Desktop: etwa 224 px Navigation, darüber hinaus flexible Hauptfläche mit Kopfzeile/Suche, großem Lieblingsmix, Coverreihe und zuletzt verwendeten Listen. Der feste Player überspannt die gesamte Breite; Inhaltsabstand berücksichtigt seine Höhe. Die Referenz bildet das Grundlayout, nicht einen zusätzlichen zentrierten Screenshotrahmen.

Tablet: kompaktere Abstände und Cover; Navigation klappt bei Platzmangel ein. Smartphone: Kopfzeile mit Menü und Suche, Hero untereinander, zwei Cover pro Reihe, kompakter fester Player in zwei Zeilen. Alle Ansichten funktionieren ab 320 px ohne horizontales Pflichtscrollen; normale Seitenbewegung bleibt erlaubt. Keine abgeschnittenen Titel als alleinige Informationsquelle.

## Phoniebox-Inhalte und Zustände

Navigation: Start, Musik, Spotify, Playlists, RFID, Akku & PiSugar, Einstellungen. Die gemeinsame Liste ist das zentrale Motiv: jeder Titel zeigt Eigene Musik oder Spotify als Text/Badge. Der bevorzugte Mix und sichtbare Player bleiben bei Seitenwechseln erhalten. Suche, Queue, Pause, Vor/Zurück und Lautstärke benutzen konsistente Bezeichnungen; echte Aktionen werden später ausschließlich an den gemeinsamen Controller gebunden.

Die große Lieblingsmix-Fläche zeigt eigene Cover-/Schallplattenformen statt übernommener Künstlerfotos. Kleine Cover verwenden originale einfache Illustrationen mit realistischen deutschen Titeln. Ein Quellenmix im Hero ist das kennzeichnende Element. Profilfotos, Benachrichtigungszähler und dekorative Karussellpunkte werden nicht ohne Funktion kopiert.

PiSugar deaktiviert: kein Akkuindikator im Kopf. Aktiv und bekannt: Prozent plus verständlicher Name, anklickbar zur Energieansicht. Aktiv aber nicht erreichbar: Akku unbekannt, keine alten Prozentwerte und kein erfundener Ladezustand. Energieaktionen bleiben außerhalb der Vorschau. Leere Suchergebnisse bieten Suche zurücksetzen; Platzhalterseiten zeigen ihren simulierten Zustand und vermitteln keine erfolgreiche Geräteaktion.

## U02a – freigegebene isolierte Designvorschau

Root gibt Luna eine statische, im Browser ausführbare Designvorschau unter src/webapp/public/design-preview frei. Sie ist ein früher U02-Teilschritt, kein fertiger React-/Router-/Backendanschluss. Vorhandene App, RPC, MPD, PiSugar und Installationsdienste werden nicht geändert. Die CRA-Buildpipeline übernimmt öffentliche Assets und prüft weiterhin den vollständigen bestehenden Webclient.

Genau vier neue Projektdateien: index.html, styles.css und preview.js im genannten public-Verzeichnis sowie tests/design-preview/browser_smoke.py. Alle ausführbaren Inhalte schreibt Luna. Der lokale Artefaktordner phoniebox-staging/u02-preview ist kein vollständiger Checkout. Die Vorschau kennzeichnet Beispieldaten dauerhaft sichtbar. Playeraktionen ändern nur diese Vorschau; keine Netzwerk-/Host-/OAuth-/Audioaktion. Keine externe Bibliothek, Webfont, Remote-Cover oder neue Dependency. Responsive Ansicht, semantische Navigation, sichtbarer Fokus, Escape/Menuverhalten und reduzierte Bewegung gehören dazu.

Abnahme: echte Playwright-Prüfung und Screenshots bei 390, 768 und 1440 px; zusätzliche Überlaufprüfung bei 320 px. Menü und alle Navigationspunkte, Quellbadge, Suchleerzustand, durchgängiger Player sowie aktive/deaktivierte/nicht erreichbare PiSugar-Anzeige prüfen. Screenshots tatsächlich ansehen und mit diesem Bild vergleichen. Vollständigen vorhandenen Webbuild und unabhängiges Review am veröffentlichten SHA getrennt nachweisen. Gesamt-U02 bleibt bis zum späteren React-/Routeranschluss offen.

Präzisierung nach erstem unabhängigem U02a-Review: Die Vorschau-Warteschlange muss aus derselben lokalen Reihenfolge wie Vor/Zurück und Coverwahl entstehen. Sichtbare nächste Titel dürfen nicht als feste dekorative Liste stehen bleiben. Das beschriftete Phoniebox-Startlogo führt aus allen Unteransichten tatsächlich zurück, ohne den gewählten Titel zu verlieren. Die Akkuillustration verwendet einen konsistent definierten inneren Füllbereich zum selben Beispiel-Prozentwert; sie ist kein Gerätebeleg.
