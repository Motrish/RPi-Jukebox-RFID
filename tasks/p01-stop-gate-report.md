# P01 Stopfreigabe-Nachweis

Die Stopfreigabe beschreibt jetzt den letzten angenommenen STOP-Versuch der zugeordneten Identity. Nach öffentlicher Eingabevalidierung, Zuordnungsprüfung und Capabilityprüfung entzieht `stop` die bisherige Freigabe vor Sessioneintritt und Statuszugriff. Nur ein vollständig bestätigter STOP nach erfolgreichem Kontextabschluss gibt sie erneut frei. Ein fremder STOP oder eine ungültige öffentliche Eingabe verändert die bisherige Zuordnung nicht.

Die Regressionen decken Sessioneintrittsfehler mit TIMEOUT und UNAVAILABLE, einen frischen Status mit `hasError=true` sowie eine bereits abgelaufene Deadline nach einem zuvor bestätigten terminalen STOP ab. Jeder dieser Wiederholungsversuche endet unbestätigt und blockiert START einer neuen Identity. Ein erfolgreicher Wiederholungs-STOP gibt START wieder frei. Ein zusätzlicher sequenzieller Test prüft, dass fremde STOP-Identity und ungültige Deadline die zuvor bestätigte Freigabe erhalten.

Die neuen Sessioneintritts- und Statusregressionen schlugen vor der Korrektur an der stehengebliebenen Freigabe fehl. Für den Deadlinefall scheiterte der erste RED-Lauf zunächst an einer fehlerhaften Erwartung zu den Sessionereignissen; nach deren Korrektur wurde der alte Adapterstand isoliert erneut ausgeführt und scheiterte am erwarteten Freigabeassert. Auf dem korrigierten Stage bestanden alle 25 Adaptertests. Der angeforderte Flake8-Aufruf endete ebenfalls erfolgreich.

Der Diff bleibt auf `adapter.py` und `test_adapter.py` im P01-Stage begrenzt. `__init__.py`, `fixtures/v1.json` und die Stagekopien der Contracts wurden nicht geändert. Es gab keinen Livegerätezugriff.

SHA-256 der finalen Stagedateien:

`src/jukebox/components/local_provider/adapter.py`: `09709C3013B01CF273E7BFE3CC60048073883D0F8C40FD07D453372BF43771BD`

`test/local_provider/test_adapter.py`: `73949475A9A2C34E378FAB5FCA0AA72B84AC53A36A7E5E570771AA3A93F5A0AE`
