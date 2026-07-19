# macOS Development Chat Prompt

This reusable template starts a development task on the Mac without Ansys. The
requesting chat must replace every angle-bracket placeholder before use.

```text
Arbeite im lokalen Checkout von `ansys-mechanical-mcp` auf dem
macOS-Entwicklungsrechner ohne Ansys Mechanical.

Ausgangsrevision:

- Remote: <REMOTE>
- Branch: <BRANCH>
- Mindestens erwarteter Commit: <BASE_COMMIT>
- Entwicklungsauftrag: <CHANGE_REQUEST>

Rechner und Rolle verifizieren
==============================

Prüfe vor jeder anderen Aktion das Betriebssystem. Fahre nur fort, wenn der
Host macOS/Darwin ist und keine lizenzierte Mechanical-Installation für diesen
Arbeitsgang vorausgesetzt wird. Stoppe unter Windows und verwende auf dem
Mechanical-Rechner stattdessen `docs/next-chat-prompt.md`.

Dieser Rechner ist die primäre Entwicklungsumgebung. Hier sind Quelländerungen,
Fake-/Unit-Tests, Dokumentation, Commit und Push vorgesehen. Behaupte hier
keinen echten Mechanical-, Lizenz-, GUI-, gRPC- oder Selection-Roundtrip.

Repository synchronisieren
===========================

1. Lies AGENTS.md, README.md und docs/live-validation-workflow.md vollständig.
2. Prüfe `git status`, aktuellen Branch, Remote und lokale Änderungen.
3. Bewahre fremde Änderungen; kein Reset, kein Force-Push und kein
   Überschreiben lokaler Arbeit.
4. Fetche `<REMOTE>`.
5. Wechsle auf `<BRANCH>`, sofern das ohne Verlust lokaler Arbeit möglich ist.
6. Aktualisiere ausschließlich per Fast-Forward. Stoppe bei Divergenz oder
   Konflikten und berichte den Zustand, statt ihn automatisch aufzulösen.
7. Prüfe, dass `<BASE_COMMIT>` in der Historie von `HEAD` enthalten ist.
8. Verwende ausschließlich die Repository-`.venv`; installiere nichts global.

Entwicklung
===========

Bearbeite anschließend diesen Auftrag:

<CHANGE_REQUEST>

Prüfe API-abhängige Entscheidungen anhand aktueller offizieller Quellen. Triff
die konkrete technische Entscheidung anhand der Evidenz und der bestehenden
Architektur; erfinde keine Mechanical-Laufzeitergebnisse. Ergänze positive und
negative Fake-Regressionstests sowie passende CLI-, Konfigurations- und
In-Process-MCP-Tests.

Halte den fachlichen Scope des Auftrags ein. Keine unbestellte Modellmutation,
keine neue Physik und keine simulierten Solver- oder Mechanical-Ergebnisse.

Prüfungen, Commit und Push
=========================

Führe mindestens aus:

.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python -m ansys_mechanical_mcp.server --check-environment
git diff --check

Prüfe danach den vollständigen Diff. Wenn die Entwicklung und alle auf diesem
Mac möglichen Prüfungen erfolgreich sind, committe ausschließlich die
Auftragsänderungen mit einer aussagekräftigen Nachricht und pushe den aktuellen
Branch ohne Force-Push.

Windows-Übergabe erzeugen
=========================

Erstelle abschließend einen vollständig kopierbaren Prompt für den Windows-
Mechanical-Rechner. Verwende `docs/next-chat-prompt.md` als Vorlage und setze
den tatsächlichen Remote, Branch, Commit, Änderungszweck und konkrete read-only
Liveprüfungen ein.

Berichte getrennt:

- auf dem Mac geprüfte Implementierung;
- Fake-, Unit-, CLI- und In-Process-MCP-Ergebnisse;
- mangels Ansys nicht live validierte Annahmen;
- geänderte Dateien;
- Branch, Commit und Push-Ergebnis;
- vollständiger Windows-Übergabeprompt.
```
