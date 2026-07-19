# Mechanical Validation Handoff Prompt

This is a reusable template for the licensed Mechanical validation machine.
The development chat must replace every angle-bracket placeholder before
handing it off. Do not assume a Mechanical release that has not been observed.

```text
Arbeite im lokalen Windows-Checkout von `ansys-mechanical-mcp` auf dem Rechner
mit der lizenzierten interaktiven Mechanical-Installation.

Zu validierende Revision:

- Remote: <REMOTE>
- Branch: <BRANCH>
- Commit: <COMMIT>
- Zweck der Änderung: <CHANGE_SUMMARY>

Umgebungsgrenze
===============

Die Implementierung, Fake-Tests und der Push wurden auf einem separaten
macOS-Entwicklungsrechner ohne Ansys durchgeführt. Dieser Prompt ist dagegen
für den Windows-Rechner mit der lizenzierten Mechanical-Installation bestimmt.

Prüfe vor jeder anderen Aktion das Betriebssystem. Fahre nur fort, wenn es
Windows ist und dieser Checkout ausdrücklich als Mechanical-Validierungsrechner
verwendet wird. Stoppe bei macOS/Darwin und verwende dort stattdessen
`docs/development-chat-prompt.md`. Windows allein beweist noch keine verfügbare
Lizenz oder vorbereitete Testsession; prüfe diese Voraussetzungen separat.

Behandle die vom Mac übernommenen Fake- und Unit-Testergebnisse nicht als echten
Mechanical-Nachweis. Dieser Rechner dient der lizenzierten read-only
Integration.

Lies zuerst vollständig AGENTS.md, README.md,
docs/live-validation-workflow.md, docs/api-research.md,
docs/architecture.md, docs/selection-context-architecture.md und die für die
Änderung relevanten Quellen und Tests.

Checkout aktualisieren
======================

1. Prüfe `git status`, den aktuellen Branch und lokale Änderungen.
2. Bewahre fremde Änderungen; kein Reset, kein Force-Push und kein
   Überschreiben lokaler Arbeit.
3. Fetche den angegebenen Remote.
4. Aktualisiere den angegebenen Branch ausschließlich per Fast-Forward, sofern
   der lokale Zustand das sicher erlaubt.
5. Prüfe, dass `HEAD` exakt `<COMMIT>` entspricht. Fahre andernfalls nicht mit
   der Livevalidierung fort.
6. Verwende ausschließlich die Repository-`.venv` und installiere oder
   aktualisiere den ausgecheckten Projektstand samt benötigten Development- und
   Ansys-Abhängigkeiten darin.

MCP aktualisieren
=================

Übernimm nur die für `<CHANGE_SUMMARY>` erforderlichen Änderungen am
registrierten MCP-Server `ansys_mechanical`. Bewahre andere Codex-Einstellungen.
Verwende dabei diese vollständig eingesetzten, änderungsspezifischen Argumente:

<MCP_CONFIG_CHANGES>

Unterscheide den MCP-Transport `stdio` vom Mechanical-gRPC-Argument
`--mechanical-transport-mode`. Ein Treffer für `ansys-mechanical.exe` in
`.venv\Scripts` ist nur der PyMechanical-CLI-Launcher und kein Nachweis der
Mechanical-Produktinstallation. `mechanical-env` ist unter Windows nicht
anwendbar.

Wenn Prozess oder Konfiguration neu geladen werden müssen, bitte mich um einen
Codex-Neustart und setze danach in diesem Chat fort. Behaupte vor dem Neustart
und einem echten Tool-Aufruf keinen Liveerfolg.

Read-only Livevalidierung
========================

1. Prüfe, dass `check_environment`, `inspect_mechanical_model` und
   `capture_current_selection` verfügbar sind.
2. Rufe zuerst `check_environment` auf und sichere den strukturierten Befund.
3. Rufe `inspect_mechanical_model` auf.
4. Prüfe sichtbare GUI beziehungsweise die ausdrücklich vorbereitete
   Verbindung, tatsächliche Produktversion, strukturierte Modell-/Analysedaten,
   Session-Kontext und alle für die Änderung relevanten Diagnosefelder. Erfasse
   für Transportänderungen mindestens Policy, angeforderten/effektiven Modus,
   Security, Scope, Executable-/Revisions-Preflight, erforderlichen SP,
   Warnungen, Versuchszahl und Retry-Sperre; berichte einen erkannten SP nur,
   wenn der exakte Build-Metadatenpfad einen ausdrücklichen SP-Marker lieferte.
5. Falls ein lokaler `insecure`-Start verwendet wird, ermittle sofort mit einer
   rein lesenden Windows-Netzwerkabfrage die exakte lokale Listener-Adresse,
   den Port und den OwningProcess. Zeige mir diese Werte. Erkläre ausdrücklich,
   dass `selected_host=127.0.0.1` keine Loopback-Bindung beweist und dass
   `0.0.0.0` oder `::` potenzielle Erreichbarkeit über andere
   Netzwerkschnittstellen bei unverschlüsselter, nicht authentifizierter
   Kommunikation bedeutet.
6. Bei einer Nicht-Loopback-Bindung ist Stoppen die empfohlene Vorgabe. Falls
   `<LIVE_TEST_STEPS>` den dokumentierten experimentellen read-only Weg
   vorsieht, frage mich stattdessen klar und laienverständlich, ob ich das
   angezeigte Risiko ausdrücklich für genau diese eine harmlose Testsitzung auf
   diesem vertrauenswürdigen oder isolierten Rechner akzeptiere. Fahre ohne
   meine ausdrückliche Bestätigung nicht fort; leite die Zustimmung nicht schon
   aus der `insecure`-Konfiguration ab.
7. Erst nach sicherer Loopback-Feststellung oder meiner ausdrücklichen
   Einzelsitzungs-Bestätigung: Rufe `inspect_mechanical_model` erneut auf und
   prüfe, dass keine zweite unnötige Mechanical-Instanz entsteht.
8. Falls die GUI ein leeres Projekt zeigt, pausiere und bitte mich, ein
   ungefährliches vorbereitetes Testprojekt zu öffnen. Öffne oder verändere
   kein produktives Projekt selbstständig.
9. Führe danach die folgenden änderungsspezifischen read-only Prüfungen aus:

   <LIVE_TEST_STEPS>

10. Führe opt-in Integrationstests nur aus, wenn ihre dokumentierten
   Voraussetzungen mit der vorbereiteten Session übereinstimmen.
11. Schließe Mechanical nach dem Test kontrolliert über den normalen
    Betreiberweg und prüfe erneut, dass Prozess und getesteter Listener nicht
    mehr vorhanden sind.

Auto darf einen bestätigten Legacy-SP nicht unsicher starten, sondern muss ohne
Launch ein strukturiertes Opt-in verlangen. Wenn `<MCP_CONFIG_CHANGES>` dafür
bewusst den persistenten lokalen Modus `insecure` setzt, ist das noch keine
Zustimmung zu einer beobachteten externen Listener-Bindung; dafür gilt der
ausdrückliche Einzelsitzungs-Dialog oben. Nach einem Startfehler nicht wiederholt
Inspect aufrufen: sichere Prozess-/GUI-Zustand und Payload, korrigiere nur die
Konfiguration, starte Codex/MCP neu und versuche danach genau einmal erneut.

Sicherheits- und Scope-Grenze
============================

Keine Modellmutation. Nicht implementieren oder ausführen: Named Selections,
Highlighting, Target Resolution, Lasten, Lagerungen, Kontakte, Materialien,
Mesh-Aktionen, Solve-/DPF-Erweiterungen, build123d/OCP, Viewer oder neue
physikalische Funktionen.

Der experimentelle Risikoweg erlaubt ausschließlich ein leeres oder harmloses
Testprojekt auf einem vertrauenswürdigen oder isolierten Entwicklungsrechner.
Keine produktiven oder vertraulichen Modelle, keine Firewall-, Registry- oder
Systemänderung und keine stillschweigende Risikoannahme für einen späteren
Start.

Wenn die echte Laufzeit eine Annahme widerlegt, sichere Version, Build/SP,
PyMechanical-Version, Konfiguration, vollständige Fehlermeldung, Prozess-/GUI-
Verhalten und sichere strukturierte Payloads. Ändere im normalen Ablauf keinen
Projektcode auf diesem Rechner. Gib die Evidenz für einen fake-getesteten Fix
an den Entwicklungsrechner zurück.

Abschluss
=========

Führe mindestens aus:

.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m ansys_mechanical_mcp.server --check-environment
git diff --check

Berichte getrennt:

- Installation und MCP-Verbindung;
- vom Entwicklungsrechner übernommene Fake-/Unit-Validierung;
- echter Mechanical-Roundtrip;
- reale Selection- oder andere read-only Fälle;
- nicht verfügbare oder versionsabhängige Fälle;
- verbleibende technische Grenzen;
- genaue Rückgabe-Evidenz für den Entwicklungsrechner;
- den sinnvollsten nächsten Schritt.

Kein Commit und kein Push auf dem Mechanical-Rechner, sofern ich dies nach
einem live beobachteten Problem nicht ausdrücklich beauftrage.
```
