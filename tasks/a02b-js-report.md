# A02b1 – JavaScript-Verträge ohne Transport

Stand: 17.10.2026. Der freigegebene Bereich sind dekodierte JS-Werte mit endlichen sicheren Ganzzahlen. Jede akzeptierte kanonische Ausgabe muss vom unveränderten Python-V1-Vertrag angenommen werden und ihre Daten erhalten. Beliebige Raw-JSON-Parität und ein Geräte-/Transportanschluss sind nicht Bestandteil dieses Slices.

## Stand und Umfang

Draft-PR12 enthält jetzt 18428caf43e461e287f6e3f14de0a241b562aee6, Tree314e7b057bd811f3b578e3791dc531b2c8e0755f. Der mechanische Zwei-Eltern-Commit erhält den bereits unabhängig geprüften I01a-Integrationsstand87ee99b42d2debbaf4a1bea9264793c168f39f31 und die eingefrorenen Luna-Vertragsdateien. Root hat alle acht A02b-/I01a-Dateien identisch zurückgelesen. An diesem exakten Head bestanden anschließend Webbuild, 22 Pythonvertragstests, alle12 Jesttests und alle6 Chromiumgruppen (39027938090) sowie Python3.9–3.13 plus finish (39027938119). PR12 wurde als ea87e4a7e0a4a6f16119e440f8c797c45d866d0c integriert; Root hat den identischen Mergebaum bestätigt. develop blieb unverändert.

Vier A02b1-Pfade, keine neue Dependency oder geänderte Pythonsemantik:

| Pfad | Finaler SHA256 |
| --- | --- |
| src/webapp/src/contracts/v1.js | 4413dcbed9325b0e412b7bcaa34b77c8c37d5821bc20b31fdbc050d5ca3aa8ea |
| src/webapp/src/contracts/v1.test.js | 0785e92b4bc77e55bb582772706bfe6d647e9d8520b6f27e0a1446dbc07255df |
| test/contracts/fixtures/v1.json | 239bde183e5c12e5993626554110bc8ca825ec981980b338b460a686176b1a0b |
| .github/workflows/test_build_webapp_v3.yml | dc72a2b4796eddd5b6d27fca9ae3e1d5667f459446281a5c3a7fdac3985b6c3c |

Das JS-Modul exportiert neun öffentliche Validatoren und ContractValidationError. Es hat keine UI-/Transportimporte. Geschlossene Strukturen, eigene Pflichtfelder, Unicodecodepoints, Python-Whitespace, Ganzzahlen und getrennte Kopien folgen dem bestehenden Vertrag. Der feste Pythonbridge-Quelltext erhält ausschließlich JSON-stdin und begrenzte Prozesszeit/Ausgabe. Positive Tests prüfen sowohl Originalinput als auch Mutation und kanonische Ausgabe unabhängig. Alle vier bisherigen Fixturewurzeln bleiben unverändert; js_conformance ergänzt das gemeinsame Corpus. Der Workflow erhält Build und echte Chromiumabnahme.

## Tatsächliche RED- und Folgeprüfungen

Die erste Testveröffentlichung6aaebb2c scheiterte in Lauf39026873757/Job117379492045 erwartungsgemäß am fehlenden Modul. Nach unabhängiger Härtung des Testorakels bestätigt der abschließende Phase1-Stand0508ef45f075976f4b0ab8a831c693fae8aa9a77 im tatsächlichen Lauf39027441324/Job117381108372 erneut genau dieses RED. CRA-Build und 22 unveränderte Pythonprüfungen bestanden. Erst danach wurde die Implementierung freigegeben.

Die erste Implementierung77793a2364f06b6c405eb908aa6437e265c575c4 hatte zwei unabhängige P2-Befunde: löchrige Arrays umgingen die Elementprüfung, und negative Null blieb im Rückgabewert nicht kanonisch. Der echte Jestlauf39027661137/Job117381723415 bestätigt neun bestandene und eine fehlgeschlagene Prüfung am bestehenden Rawnullfall. Sparsearray-RED wurde zusätzlich vom Autor mit Node tatsächlich nachgewiesen.

Luna hat ausschließlich v1.js/v1.test.js korrigiert: alle Arraypositionen werden vor der Elementiteration auf eigene vorhandene Indizes geprüft; akzeptierte negative Null wird im Ergebnis zu positiver Null. Gezielte JS-only-Regressionen betreffen Playlist-/Queueentries, Commanditems, supportedVersions und Konflikte. Der bestehende Rawfall bleibt erhalten. Fixture, Workflow und Pythonvertrag änderten sich dabei nicht.

Node-Syntaxprüfung und 22 Pythonprüfungen bestehen lokal. Root hat den unten unverändert übernommenen Luna-Nodebefehl erneut mit Exit0 ausgeführt. Lokales Jest wird mangels node_modules nicht behauptet. Vollständige Abnahme erfolgt am neuen gemeinsamen CI-Head; der Teilstage ist kein Vollcheckout oder Zielgerät.

## Repeatable author regression command

Run from `G:\Entwicklung\phoniebox-staging\a02b` in PowerShell. This is the exact post-fix Node command used for the GREEN author check; it exercises sparse playlist/queue entries, command items, supportedVersions, revision conflicts, and negative-zero normalization without modifying project files:

```powershell
node --input-type=module -e "import fs from 'node:fs'; const m=await import('data:text/javascript;base64,'+fs.readFileSync('src/webapp/src/contracts/v1.js').toString('base64')); const f=JSON.parse(fs.readFileSync('test/contracts/fixtures/v1.json','utf8')); const sparse=()=>Array(1); const cases=[()=>m.validatePlaylistSnapshot({...f.valid_playlist,entries:sparse()}),()=>m.validateQueueSnapshot({...f.valid_empty_queue,entries:sparse()}),()=>m.validateCommand({contractVersion:1,commandId:'cmd_1',action:'PLAYLIST_CREATE',name:'Mix',items:sparse()}),()=>m.validateError({code:'UNSUPPORTED_VERSION',message:'safe',retryable:false,operation:'TEST',details:{supportedVersions:sparse()}}),()=>m.validateError({code:'REVISION_CONFLICT',message:'safe',retryable:false,operation:'TEST',details:{conflicts:sparse()}})]; for(const check of cases){try{check();throw Error('sparse array was accepted')}catch(e){if(!(e instanceof m.ContractValidationError))throw e}} const out=m.validatePlaylistSnapshot({...f.valid_playlist,revision:-0}); if(Object.is(out.revision,-0)||out.revision!==0)throw Error('negative zero was not normalized'); console.log('JS author regression checks: PASS');"
```

The pre-fix command ran against the original A02b `v1.js` and exited 1 with: `sparse playlist.entries was accepted; sparse command.items was accepted; sparse supportedVersions was accepted; sparse conflicts was accepted; revision -0 was returned without normalization`. The post-fix command above exited 0 and printed `JS author regression checks: PASS`.
