# F05 / U01 – Designreferenz und visuelles Konzept

Stand des ursprünglichen Abrufberichts: 16.10.2026. Aktualisierung 17.10.2026: Nutzerkopie sichtbar, F05 erfüllt; die folgenden Abrufbefunde sind historisch.

## Ergebnis

Die angegebene Dribbble-Grafik war in dieser Ausführung nicht sichtbar. Der direkte Abruf der Original-PNG über den Webzugriff meldete, dass die URL nicht zugänglich ist. Eine Bildsuche nach Dribbble-ID und Dateiname ergab keinen Treffer zur Vorlage; die Suche nach der exakten ID/Dateikennung ergab keine Ergebnisse. Im lokalen `reference/`-Ordner liegt keine Nutzerkopie.

Quelle, deren Inhalt nicht geprüft werden konnte: [Dribbble-Originalgrafik](https://cdn.dribbble.com/userupload/5037629/file/original-c7e28b3f83c5daa85bc0ada2bfdc4578.png).

Damit ist die F05-Abnahme („Quelle sichtbar, Analyse am Bild nachvollziehbar“) nicht erfüllt. Es gibt hier keinen belastbaren Sichtnachweis. Aus der URL, dem Dateinamen oder Suchtreffern lassen sich weder Motiv noch Farben, Schrift, Abstände, Proportionen oder Layout der Vorlage ableiten. Eine Aussage dazu wäre erfunden.

## U01 – belastbarer Stand ohne Bild

Das Konzeptdokument `docs/superpowers/specs/2026-10-16-phoniebox-design.md` enthält bereits funktionale Strukturvorschläge, die unabhängig von der Grafik gelten:

- **Startseite:** aktueller Titel und Player, Favoriten, zuletzt verwendet, Batterie- und Verbindungsstatus.
- **Musik:** lokale Ordner und Titel, Suche und Upload.
- **Spotify:** Suche, verfügbare Playlists, Linkeingabe und Anmeldung.
- **Playlists:** gespeicherte gemischte Phoniebox-Listen und laufende Queue.
- **RFID, Akku/PiSugar und Einstellungen:** Gerätefunktionen sowie Audio-, Netzwerk-, Diagnose-, Sicherungs- und Updatebereiche.
- **Quellenübergreifende Aktionen:** jetzt spielen, als Nächstes einreihen, anhängen und zur Playlist hinzufügen. Jeder Queue-Eintrag zeigt seine Quelle. Der Playerzustand bleibt bei geschlossener Browserseite auf der Box erhalten.
- **Ansichten:** Desktop mit seitlicher Navigation, Suche/Akku im Kopfbereich, zentralem Inhalt und optionaler Queue; Smartphone mit einklappbarer Navigation, kompaktem Player und eigener Queue-Ansicht.

Das sind Konzeptvorgaben beziehungsweise Funktionsannahmen, keine Beobachtungen an der Dribbble-Vorlage. Es werden deshalb keine Farbwerte, Schriftrollen, Rundungen, Abstände, Größenverhältnisse, Komponentenstile oder visuellen Zustände für U01 festgelegt. U01 kann erst nach Sichtung der Grafik einen nachvollziehbaren Referenzvergleich und daraus abgeleitete visuelle Beschreibung liefern.

## Voraussetzung zum Fortsetzen

Eine lokal bereitgestellte Kopie der Originalgrafik wird benötigt. Nach Erhalt muss sie tatsächlich geöffnet und geprüft werden; anschließend können Referenzmerkmale für Startseite, Playlist und Smartphoneansicht beschrieben werden. Das Bild darf als Recherchebeleg im Referenzordner liegen, wird aber nicht als redistribuierbares UI-Asset übernommen.

## Nutzerkopie am 17.10.2026

Der Nutzer hat reference/template.webp im Gespräch bereitgestellt. Root hat das tatsächliche Bild gesehen: dunkle Muzes-Musikansicht mit linker Seitennavigation, violettem Playlist-Hero, Coverreihen und durchgehender Playerleiste unten. SHA-256 der lokalen Referenz: 23072BBA7F71AC62D1063379D1E6E716BE4ED093D0FF5C37FC9E8EB3D3A4DDEC. Der CDN-Zugriff bleibt ungeklärt, wird aber nicht mehr für die Designanalyse benötigt. F05 ist erfüllt; der konkrete U01-Entwurf steht in u01-design-spec.md. Künstlerfotos und Referenzbitmap werden nicht als Produktassets übernommen.
