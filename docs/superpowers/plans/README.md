# Phoniebox-Entwicklung

Die Entwicklung ist nach dem abgestimmten Mehragentenplan gestartet.

- [Konzept](../specs/2026-10-16-phoniebox-design.md)
- [Mehragentenplan](2026-10-16-phoniebox-multi-agent-plan.md)
- [Arbeitspakete](multi-agent/backlog.md)
- [Agentenübergaben](multi-agent/handoffs.md)
- [Abnahmematrix](multi-agent/acceptance.md)
- [Aktueller Aufgabenstatus](../../../tasks/todo.md)
- [Git- und V3-Basisnachweis](../../../tasks/f01-environment-report.md)
- [Quelleninventur und CI](../../../tasks/f03-source-inventory.md)
- [CONTRACT 1 für Daten und Speicherung](../../../tasks/a01-contracts.md)

Die unveränderte V3-Releasebasis liegt auf feature/foundation. Der separate Branch future3/ci-baseline prüft denselben V3-Dateibaum mit den vorhandenen Upstream-Workflows. Dieser Dokumentationsbranch enthält die Pläne und Ausführungsnachweise, keine Produktcodeänderungen.

Luna schreibt alle ausführbaren Projektartefakte. Sol übernimmt Planung und Review. Astra ist ausgeschlossen.

## Implementierungsnachweise

Der geprüfte transportfreie Daten-/Speicherkern liegt auf [future3/modern-ui](https://github.com/Motrish/RPi-Jukebox-RFID/tree/future3/modern-ui). Die folgenden Berichte benennen jeweils den tatsächlich geprüften SHA; der aktuelle Gesamtstatus steht weiterhin ausschließlich in todo.md.

- [A02a-Verträge](../../../tasks/a02-contracts-report.md) und [Review](../../../tasks/a02-review.md)
- [P03a1-Speicherkern](../../../tasks/p03a1-store-report.md) und [Review](../../../tasks/p03a1-review.md)
- [P03a2-Playlistaktionen](../../../tasks/p03a2-playlist-report.md) und [Review](../../../tasks/p03a2-review.md)
- [P03b-Queues](../../../tasks/p03b-queue-report.md) und [Review](../../../tasks/p03b-review.md)
- [Unabhängige Storeproben](../../../tasks/q01-store-regressions-report.md) und [Review](../../../tasks/q01-store-review.md)

- [Zielgerät Zero W / ARMv6](../../../tasks/f04-hardware-profile.md)
- [Ressourcen- und Wiederaufnahmeregeln](../../../tasks/resource-policy.md)
- [ARMv6-Spotify-Optionen und offene Nachweise](../../../tasks/armv6-spotify-options.md)
- [B01a-PiSugar-Vertrag](../../../tasks/b01-pisugar-contract.md) und [Review](../../../tasks/b01-pisugar-review.md)
- [P01a1-Providervertrag](../../../tasks/p01-local-provider-contract.md)

- [P01a1-Implementierungsbericht](../../../tasks/p01-local-provider-report.md)

- [P01a1-Review einschließlich Folgecommit](../../../tasks/p01-local-provider-review.md)
- [P01-Stopgate-Regressionen](../../../tasks/p01-stop-gate-report.md)

- [U01-Design anhand der sichtbaren Nutzerreferenz](../../../tasks/u01-design-spec.md)

- [U02a-Designvorschau und Browsernachweise](../../../tasks/u02-preview-report.md) und [Review](../../../tasks/u02-preview-review.md)

- [U02b-React-Anschluss und Freigabegrenzen](../../../tasks/u02b-react-seam-plan.md)
