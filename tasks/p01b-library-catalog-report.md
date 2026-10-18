# P01b1 – LibraryCatalog phase 2 implementation report

Implementation is frozen in the two approved new source files. The source adds an effect-free public export, a SQLite catalog bound to a canonical Linux root identity, per-operation root descriptor verification, descriptor-relative `O_PATH` probes, UUID-backed media IDs, fingerprint-based tombstones, pagination, and safe `CatalogError.safe.code` / `message` values. The two phase-1 test files initially remained unchanged; two review regressions were subsequently added to test_catalog.py. Database setup uses its own versioned schema and a 250 ms SQLite busy timeout. The resolver returns the stored relative reference after a fresh descriptor probe; it does not pin a future MPD open or claim TOCTOU protection.

The local environment is Windows and does not provide the Linux descriptor backend. The actual local pytest result is therefore **2 passed, 19 skipped**. The 19 skips are the Linux-only catalog and descriptor cases; this run is not the acceptance result. The complete Linux CI matrix must run all 21 cases green before integration. The prior CI RED was collected before these source files existed and only confirmed the intended missing-module failure.

V3 flake8 passed with maximum complexity 12 using this exact command:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; & 'G:\Entwicklung\phoniebox-tools\python\bin\flake8.exe' --max-complexity=12 'G:\Entwicklung\phoniebox-staging\p01b\src\jukebox\components\library_catalog\__init__.py' 'G:\Entwicklung\phoniebox-staging\p01b\src\jukebox\components\library_catalog\catalog.py' 'G:\Entwicklung\phoniebox-staging\p01b\test\library_catalog\test_catalog.py' 'G:\Entwicklung\phoniebox-staging\p01b\test\library_catalog\test_catalog_linux.py'
```

The local Windows pytest command and result were:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\pytest-check'; $env:PYTHONDONTWRITEBYTECODE='1'; & 'G:\Entwicklung\phoniebox-tools\pytest-check\bin\pytest.exe' -q 'G:\Entwicklung\phoniebox-staging\p01b\test\library_catalog'
```

```text
ssssssssssssss..sssss                                                    [100%]
2 passed, 19 skipped in 0.10s
```

Initial source-freeze SHA-256 values (before the review fixes below):

| File | SHA-256 |
| --- | --- |
| `src/jukebox/components/library_catalog/__init__.py` | `A6AB8559ACA3C4A5E9EBCEA003145E305202E4E31A3C60FA41232D4BCBF2DC52` |
| `src/jukebox/components/library_catalog/catalog.py` | `2B0B59008CA0E6C3DE15DF8E37EBE8E60F0CE55D7E69738A4B9EF59A597E42E5` |
| `test/library_catalog/test_catalog.py` | `10E11B9430979536C78D0E93309BC5A5050BCBF41181CD14EE5AE9F709AAA283` |
| `test/library_catalog/test_catalog_linux.py` | `053F5F8D2001DCDE75B8EAB637D3E19539A0295EED368B32D07DE85247076478` |

## Root – tatsächliche RED- und Folgestände

Die beiden Testdateien wurden vor der Implementierung alsafddd7a6934436304b3de107e1d930b4760d62bc veröffentlicht. Echter vollständiger Linux-RED39030460679/117389696705 (Python3.10): beide neuen Importe scheitern am absichtlich fehlenden Modul. Unabhängiges Testreview ohne Blocker; erst danach zwei Produktquelldateien freigegeben.

Erste Implementierung7a1dd4098054b9a28da0349061f88daeb444a8b9: beide vollständigen Pythonmatrices39030950262/39030953204 grün, Job117391105912 bestätigt173 bestandene Tests einschließlich aller21 neuen Linux-/portablen Fälle ohne Skip. Das unabhängige Quellreview fand trotzdem zwei nicht abgedeckte P2: Registerbefund einer fehlenden Datei war nicht dauerhaft invalidierend; eine fremde View-only-Datenbank galt als leer. Daher kein Merge.

Luna ergänzte ausschließlich zwei Regressionen alsd0ebb8598c8dc1fe584dea370389564475ed0772. Root las die echten Linuxlogs39031175203/117391760598 (3.11) und39031172465/117391752153 (3.12): exakt beide neuen Assertions scheitern (AVAILABLE statt MISSING; fremde View akzeptiert). Erst danach wurde ausschließlich catalog.py korrigiert. Quellfix beendet die erfolgreiche Invalidierungstransaktion vor der MEDIA_UNAVAILABLE-Exception; technische Ungewissheit invalidiert weiter nicht. Leere und eigene Schemas werden anhand sämtlicher nichtinterner Objekte geprüft; nur das wörtliche SQLite-intern-Präfix wird ausgenommen.

Aktueller geprüfter Headb4a4294353eb27d0bdda5c24d742262eff3804ab, Tree8ccedafaab19e7d748d5a814c341e0b0912341a3, Draft-PR14. Quellhashcatalog.py ac42e035adf8f9c23232bcb26f254cad9196c401b23df7213f6df3fa1c6371c0; Testhash4251c8d064600ce541a55e34e047a4d9e3940de15b0db612c8e59c612b555a18. Export und Linuxdatei bleiben bei den obigen Hashes. Alle vier Inhalte von Root identisch zurückgelesen. Serien-Folgereview schließt beide P2 ohne neuen Blocker; V3lint grün. Finale volle Matrix39031347317/39031345429 noch offen; kein Merge am Berichtcheckpoint. Windowsnachweis am korrigierten Stand: zwei portable Tests grün,21 Linuxfälle ausdrücklich geskippt. Die spätere MPD-open-/TOCTOU-Grenze bleibt offen. Nachträglich beschädigte interne Integer-TEXT-Felder sind ein dokumentierter kleiner Robustheitshinweis unter der eigenen vertrauenswürdigen Storevoraussetzung, keine heimlich behauptete Fehlerabdeckung.

## Root – Integration bestätigt

Am finalen Head b4a4294353eb27d0bdda5c24d742262eff3804ab bestehen beide vollständigen Pythonmatrices 39031347317 und 39031345429 mit je3.9–3.13 plus finish. Job117392253949 bestätigt175 bestandene Tests ohne Skip, einschließlich aller23 Katalogfälle und beiden neuen Regressionen. Das letzte unabhängige Folgereview schließt beide P2 ohne neue Blocker, alle vier finalen Inhalte wurden identisch zurückgelesen.

PR14 wurde als e2eecd531618389e05f61939ba432a3357e9980d in future3/modern-ui integriert; Root hat den identischen Tree8ccedafaab19e7d748d5a814c341e0b0912341a3 bestätigt. Damit ist der begrenzte Katalog-/Resolver-Slice verified, kein Liveplayer-, Backend-/GUI-/Gerätenachweis. Der folgende authentifizierte Loopback-Lesezugriff ist ein eigener U03a1-Auftrag; die bekannten MPD-Übergabe-/TOCTOU- und Hardwaregrenzen bleiben bestehen.
