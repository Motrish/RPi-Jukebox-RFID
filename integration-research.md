# Recherche: Spotify und PiSugar für den Phoniebox-Fork

Stand: 16.10.2026. Primärquellenrecherche; keine Implementierung oder Gerätetests. gh CLI wurde versucht, scheiterte aber an lokaler Authentifizierung/Netzwerksandbox. GitHub-Inhalte wurden deshalb über Web gelesen. Keine Geheimnisse gespeichert.

## Empfehlung

Eine gemeinsame Oberfläche braucht eine gemeinsame Wiedergabesteuerung. Ein Reverse Proxy allein integriert keine Warteschlangen. Für eine neue V3-basierte Umsetzung zuerst **MPD für lokale Musik plus Spotify Soloist hinter einem eigenen Queue-Controller** prüfen. RFID, GPIO und GUI müssen denselben Controller ansprechen.

Spotify hat Soloist am 13.08.2026 offiziell für Headless-/DIY-Linux und Raspberry Pi vorgestellt. Es bietet Connect und lokale WebSocket-Steuerung. Das ist ein neuer, relevanter Kandidat gegenüber aktuell gestörtem Mopidy-Spotify. [Ankündigung](https://developer.spotify.com/blog/2026-08-13-introducing-spotify-soloist)

Diese Empfehlung steht unter dem Vorbehalt eines Hardwareversuchs, insbesondere bezüglich Audioausgabe, Titelwechsel und Bedienung im Single-Track-Modus. Die V3-Basis und deren tatsächliche Player-Anbindung prüft der Hauptplan gesondert.

## Soloist: belegte Fähigkeiten und Konsequenzen

- Persönlicher API Key bei jedem Start, Premium für dessen Erzeugung. Anmeldung durch Auswahl des Geräts in der Spotify-App im selben LAN; Session wird gespeichert. Key und Connect-Session sind unterschiedlich. Kein Spotify-Passwort in der Phoniebox-GUI abfragen. [Authentifizierung](https://developer.spotify.com/documentation/soloist/concepts/authentication)
- Builds für ARM64, ARMv7 und x86_64. ARMv6 ist nicht angeboten. Binärdateien nicht mit dem Fork weiterverteilen, auf offiziellen Download verweisen. [Downloads](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates)
- Ausgabe über PipeWire oder PulseAudio; keine direkte ALSA-Option dokumentiert. `--single-track URI` spielt einen Titel und beendet sich. Derselbe Datenordner kann nicht gleichzeitig von einem zweiten Prozess genutzt werden. [CLI](https://developer.spotify.com/documentation/soloist/reference/command-line)
- Single-Track benötigt zuvor gespeicherte Session mittels Pairing. Er deaktiviert Shuffle/Repeat und externe Steuerung/Übernahme des Playback-Kontexts und endet bei Titelende, Stop oder Titelwechsel. Ob lokale WS-Bedienung Pause/Seek in diesem Modus vollständig wie benötigt funktioniert, im PoC prüfen. [Features](https://developer.spotify.com/documentation/soloist/features)
- Jeder Build verfällt nach 90 Tagen ab Builddatum. Danach Exitcode 10. Damit sind Ablaufanzeige, rechtzeitige Updatehinweise und ein gepflegter Updatepfad Pflicht. Ein älteres bereits verfallenes Binary ist kein brauchbarer Rollback. [Build-Laufzeit](https://developer.spotify.com/documentation/soloist/concepts/overview)
- Optionale WS-API bietet Zustände, Events, Metadaten, Queue und Play/Pause/Seek/Lautstärke. Ohne eigene Clientauthentifizierung, TLS, Origin-Prüfung oder CSRF-Schutz. Befehlsannahme bestätigt noch keine erfolgte Zustandsänderung. [WebSocket-Referenz](https://developer.spotify.com/documentation/soloist/reference/websocket-api)

**Konzept:** Soloist nur an Loopback binden, Browser ausschließlich über die abgesicherte Phoniebox-API anbinden. Gemeinsame PulseAudio-Ausgabe mit MPD auf der unterstützten Pi-Konfiguration testen. Persönlichen Key serverseitig außerhalb des Repos speichern. Der Installer führt zum offiziellen Download und durch Key-Eingabe und Pairing. Releasepakete enthalten nur eigenen Adaptercode.

Für gemischte Listen den Single-Track-Modus zuerst prüfen: Spotify-Prozess spielt genau einen Eintrag, danach gibt der Controller an MPD weiter. Eine Prozessinstanz und ihre Events erhalten eine Ausführungs-ID. Verzögerte Exit-/WS-Ereignisse einer bereits übersprungenen Instanz dürfen nie den Nachfolgetitel erneut weiterzählen. Stop, Skip, normales Ende und Fehler getrennt behandeln; auf Stop/Wechsel kann ebenfalls ein erfolgreicher Exit folgen. Nur die aktuell zuständige Instanz darf Queue-Fortschritt auslösen. Endereignis und Prozessende müssen idempotent zusammengeführt werden.

Connect-Betrieb ist ein eigener sichtbarer Modus. Dort besitzt Spotify seine Queue; in einer gemischten Phoniebox-Liste besitzt der Controller die Reihenfolge. Eine externe Spotify-App-Übernahme pausiert/verlässt die eigene Liste nach klarer Regel. Kein paralleler Connect-Daemon mit gleichem Datenordner. Übergangszeiten und vollständige Tastenbedienung sind PoC-Abnahmepunkte; Gapless-Wechsel zwischen Engines nicht versprechen.

## Alternativen: Mopidy-Spotify und Raspotify

Mopidy hat eine Tracklist, die URIs verschiedener vorhandener Backends auflösen und geordnet einfügen kann. Prinzipiell passt das zu gemischter Wiedergabe. [Core API](https://docs.mopidy.com/stable/reference/core/)

Mopidy-Spotify warnt aktuell, dass Drittanbieter-Access-Tokens fürs Streaming nicht mehr akzeptiert werden; Workaround ist ein mit librespot erzeugter Credential-Cache. Spotify-Playlists sind dort lesend; Seek, Gapless, Normalisierung und Spotify Connect werden im README als nicht unterstützt geführt. Wiedergabe nutzt einen GStreamer-Plugin auf librespot-Basis und benötigt Premium. [Projektstatus](https://github.com/mopidy/mopidy-spotify)

Ein Maintainer nennt im August 2026 das librespot-Programm `get_creds` als Workaround. Der gemeldete Fehlerfall betrifft unter anderem Phoniebox V2 auf Bullseye; dies ist ein konkreter Issuebericht, kein eigener Test. [Issue 437](https://github.com/mopidy/mopidy-spotify/issues/437)

librespot ist ein inoffizieller Spotify-Client und benötigt Premium. Raspotify paketiert es als systemd-Dienst; dessen aktuelle README schließt ARMv6 aus. Ein Connect-Empfänger liefert allein keine gemeinsame lokale/Spotify-Queue. [librespot](https://github.com/librespot-org/librespot), [Raspotify](https://github.com/dtcooper/raspotify)

**Folgerung:** Keine große neue Lösung auf der Annahme aufbauen, Mopidy-Spotify funktioniere ohne Eingriff stabil. Es bleibt Vergleichskandidat für eine bereits funktionierende Installation. Raspotify als zweiter Spotify-Stack zusätzlich zum ausgewählten Standard würde den ersten Release unnötig vergrößern.

## Gemischte Playlists

Spotify kann lokale Dateien in seinen Desktop-Playlists repräsentieren. Die Web API kann solche Einträge lesen, aber keine lokalen Dateien zu Spotify-Playlists hinzufügen. Eine auf dem Pi bearbeitbare Liste „MP3 – Spotify – MP3“ ist deshalb eine eigene Phoniebox-Playlist. [Playlistkonzept](https://developer.spotify.com/documentation/web-api/concepts/playlists)

Einträge erhalten stabile ID, Quellentyp, interne Medien-ID beziehungsweise Spotify-URI und Anzeigemetadaten. Queue und Listen werden auf dem Pi persistiert. Der Controller verwaltet Reihenfolge, aktuelle Instanz, Position, Pause, Skip, RFID-Unterbrechung und Fehler. Lokale Musik muss bei fehlendem Spotify weiter bedienbar sein.

Spotify-Import als Snapshot kennzeichnen. Export nach Spotify kann nur zulässige Spotify-Einträge enthalten; lokale Einträge nicht still verlieren. Spotify-native Queue und eigene gemischte Liste in der GUI klar benennen. Der offizielle Web Playback SDK läuft im Browser und würde bei mobiler Bedienung das Handy zum Abspielgerät machen; für unabhängig spielende RFID-Box keine passende Hauptlösung. [SDK](https://developer.spotify.com/documentation/web-playback-sdk)

## Web API und OAuth im LAN

Neue Dev-Mode-Apps brauchen einen Premium-Appbesitzer und höchstens fünf freigeschaltete Nutzer. Für Fork-Nutzer eigene App-Zugangsdaten je Installation planen. [Quota Modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)

Seit Juli 2026 sind 25 Client IDs je Entwickler erlaubt; die Februar-Aussage „eine“ ist veraltet. Quoten zählen kontoweit; 429 kann `QUOTA_EXCEEDED` enthalten. [Juli-Update](https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates)

Für neue Apps gelten Einschränkungen: Playlistinhalte vor allem für eigene/kollaborative Listen, neue `/items`-Endpunkte und kleinere Suchseiten. Endpunktänderungen für bestehende Apps wurden im März verschoben, weshalb historische Dokumente unterschiedliche Geltungsbereiche haben. Konkrete App-Fähigkeiten testen; beliebige öffentliche Spotify-Playlists nicht zum garantierten Import machen. [Migration](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide), [Ankündigung mit März-Nachtrag](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)

OAuth-Redirects benötigen HTTPS außer expliziten Loopback-IP-Literalen. `localhost` ist unzulässig. HTTP-IP oder HTTP-`.local` der Box erfüllen diese Anforderung nicht. Am Handy verweist `127.0.0.1` auf das Handy. [Redirectregeln](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)

**Praktikabler Plan:** Authorization Code mit PKCE und einer exakt registrierten HTTPS-Callback-Adresse. Im LAN entweder ein eigener DNS-Name mit gültigem öffentlich vertrautem Zertifikat, das per DNS-Challenge ausgestellt werden kann, oder bewusst eingerichtete lokale CA mit auf jedem Bediengerät installiertem Vertrauen. Ein bloß selbstsigniertes Zertifikat ohne Vertrauenseinrichtung ist kein reibungsloser Wizard. Zertifikatsausstellung, DNS und Erneuerung sind eigene Voraussetzungen.

Für technische Desktop-Nutzer ist alternativ ein SSH-Tunnel zu einem exakt registrierten `http://127.0.0.1:PORT/callback` denkbar; der Browser läuft dann auf dem tunnelerstellenden Rechner. Dies muss Ende-zu-Ende getestet und als Desktop-Fallback dokumentiert werden. Es ist keine Lösung für den normalen Smartphone-Wizard. Ohne eingerichteten Web-API-OAuth funktioniert das Soloist-Pairing konzeptionell separat; Suche/Playlistimport bleiben bis zur Freigabe deaktiviert.

Refresh-Tokens laufen nach sechs Monaten ab, Refresh verlängert nicht. Für bestehende Apps seit 20.07.2026. `invalid_grant` führt zur erneuten Anmeldung. [Tokenablauf](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration)

## PiSugar

Der Rust-Manager unterstützt PiSugar 2/3, dokumentiert 2 mit zwei/vier LEDs, 2 Pro und 3. Schnittstellen: Unix-Socket `/tmp/pisugar-server.sock`, TCP 8423, WS 8422 und Web-GUI samt `/ws` auf 8421. Seit v2.3.0 gibt es HTTP-Kommandos mit Login-Token. Lesbare Werte umfassen Akkuprozent, Modell, Spannung, Netzteil, Ladefreigabe und Abschaltschwelle; Fähigkeiten sind modellabhängig. Es existieren auch Kommandos für Tasten-/Poweroff-Shellaktionen. [README/API](https://github.com/PiSugar/pisugar-power-manager-rs/blob/master/README.md)

**Empfehlung:** Native Seite „Akku & Strom“ über Backend-Adapter zum Unix-Socket. Hauptseite zeigt Prozent und Ladestatus nur bei aktivierter Integration, bei Ausfall „nicht erreichbar“ samt letztem Messzeitpunkt. Ein Verbindungsfehler wird nie zu 0 Prozent. Keine Prozentanzeige bei nicht installiertem Modul.

Native Unterseite: Status, Ladegrenzen soweit unterstützt, Shutdownschwelle/Verzögerung und RTC-Wecken. Nur typisierte freigegebene Aktionen anbieten; kein freies PiSugar-`exec` und keine frei eingabefähigen Shellkommandos. Modellfähigkeiten auswerten. PiSugar-Tasten und Phoniebox-Shutdown/GPIO dürfen einander nicht widersprechen.

Serveradressen und Socket-Modus sind konfigurierbar. Socketstandard ist `666`; im Installer Rechte/Dienstgruppe gezielt setzen. Automatische Abschaltung läuft unabhängig von der Browseroberfläche im PiSugar-Daemon. [Servercode](https://github.com/PiSugar/pisugar-power-manager-rs/blob/master/pisugar-server/src/main.rs)

Die originale PiSugar-GUI unter einem Unterpfad ist nur Übergangskandidat: relative Assets, Loginpfade, WS-URL, Upgrade-Header und HTTPS-Verhalten zuerst testen. Ein iframe allein integriert weder Rechte noch Design. Native Felder über den Adapter erfüllen das einheitliche Design besser. Vollständiger Funktionsumfang der Original-GUI ist bei Bedarf späterer Ausbau.

## Abnahmetests vor Hauptimplementierung

1. Reales Pi-/OS-/Audio-/PiSugar-Modell festlegen; V3-Release und OS-Matrix passend auswählen.
2. Zehn MPD → Soloist → MPD Wechsel ohne Audioüberlagerung, mit stabiler Lautstärke; Latenz messen.
3. Pause/Seek/Skip/Stop/RFID während Wechseln und verspätete Prozess-/WS-Ereignisse prüfen.
4. Browser schließen: Wiedergabe bleibt auf der Box. WLAN-/Spotify-/Playerfehler: lokale Musik bleibt nutzbar.
5. Connect-Übernahme und Rückgabe; Neustart mit Queue-/Resumezustand; keine doppelten Instanzen.
6. Buildablauf, Warnung und Updatepfad prüfen. Keine heruntergeladenen Spotify-Binaries im Fork.
7. PiSugar Laden/Netzteil/Verbindungsausfall mit realem Modell; sicherer Shutdown bleibt im Daemon.
8. Mobile OAuth-Anmeldung mit tatsächlichem vertrauenswürdigem HTTPS; Suche und eigener/fremder Playlistimport gegen tatsächliche Apprechte.

Offen bis Hardwareversuch: Single-Track-Steuerung, Übergangslatenz, Ressourcen auf kleinen Pis, gemeinsame PulseAudio-Konfiguration, konkrete Web-API-Rechte, Zertifikatsweg und PiSugar-Modellfähigkeiten.
DNS-01 kann auch nicht öffentlich erreichbare Webserver zertifizieren; eigene Domainkontrolle und Erneuerungsweg bleiben nötig. [ACME DNS-01 Primärquelle](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge)
