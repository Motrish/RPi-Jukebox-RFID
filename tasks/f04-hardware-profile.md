# F04 – bestätigtes Zielgerät

Stand: 16.10.2026. Nutzerangaben: ursprünglicher Raspberry Pi Zero W, Raspberry Pi OS Lite 32 Bit und PiSugar 2 mit zwei LEDs. Kein Zero 2 W. Noch kein Gerätezugriff und keine Installation auf der Box erfolgt.

Der ursprüngliche Zero W verwendet ARMv6. Raspbian-basierte 32-Bit-Pakete müssen dafür gebaut sein; die Bezeichnung armhf alleine beweist diese Eignung nicht. Der bisher erfolgreiche Bookworm-ARMv7-Container bestätigt den vorhandenen Installer auf seiner Containerarchitektur, nicht auf dieser Zielbox. [Offizielle Architektureinordnung](https://www.raspberrypi.com/news/raspberry-pi-os-64-bit/), [Zero-Dokumentation](https://www.raspberrypi.com/documentation/computers/zero.html).

Spotify Soloist bietet in der gelesenen Downloadmatrix ARMv7, ARM64 und x86-64, keinen ARMv6-Build. Soloist ist deshalb für dieses Ziel ausgeschlossen, solange kein offizieller passender Build vorliegt. Keine Hardwareaufrüstung unterstellen. Ein alternatives Backend braucht einen eigenen aktuellen Auth-, Build-, Einzeltrack- und Stopnachweis. [Offizielle Soloist-Downloads](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates).

Noch offen: genaue OS-Version/Codename und Abbild, Audioausgang/Audio-Stack, RFID-Reader und Tasten/GPIO, PiSugar-Manager/Firmware/Socketrechte, Bestandsversion und separate Test-SD. Die Bitte nach OS-Release und Audioausgang wurde bereits gestellt; fehlende Antworten werden nicht durch Vermutungen ersetzt. Eine Neuinstallation auf der Bestandskarte ist nicht freigegeben.

Für die spätere Abnahme: ARMv6- und OS-Erkennung vor Paketinstallation, passenden Raspbian-Paketpfad nachweisen, Browserartefakte extern bauen, Laufzeitlast und Speicher am Zero messen. Lokale Musik, PiSugar und optionales Spotify getrennt testen. Erst tatsächliche Hardwaremessung kann das Gerätegate schließen; Unit- und Dockerprüfungen bleiben eigene Nachweisarten.