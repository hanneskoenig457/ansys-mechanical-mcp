# Prompt For The Next Development Chat

Copy the text below into a new coding chat when a licensed Mechanical 2026 R1
GUI session is available.

```text
Arbeite im lokalen Root-Verzeichnis deines Checkouts von
`ansys-mechanical-mcp` (ersetze `<REPOSITORY_ROOT>` durch diesen Pfad):

<REPOSITORY_ROOT>

Ziel dieses Arbeitsgangs ist genau ein technischer Schritt: Validiere den
bereits implementierten persistenten MCP-/Mechanical-Lifecycle und den
read-only SelectionSnapshot gegen eine echte lizenzierte, interaktive
Mechanical-2026-R1-Session. Implementiere keine Mutation und erweitere den
fachlichen Scope nicht.

Lies zuerst vollständig AGENTS.md, README.md, pyproject.toml, CHANGELOG.md,
docs/api-research.md, docs/architecture.md,
docs/selection-context-architecture.md, docs/v0.1-implementation-plan.md, alle
Mechanical-Quellen unter src/ und die zugehörigen Tests. Prüfe anschließend
git status und git diff. Bewahre vorhandene Änderungen; kein Reset, Commit oder
Push ohne ausdrückliche Aufforderung.

Verifiziere live den erwarteten Ausgangspunkt:

- Öffentliche MCP-Tools: check_environment, inspect_mechanical_model und
  capture_current_selection.
- FastMCP v1 stdio-Lifespan mit genau einem lazy MechanicalSessionManager.
- Explizite Start-/Connect-, GUI-/Batch-, Ownership- und Cleanup-Konfiguration.
- SelectionSnapshot v1.0 mit Capture-/Vollständigkeitsstatus, 1.000er
  Rückgabelimit sowie capability-geprüfter CurrentSelection-, Entities-,
  ElementFaceIndices- und Tree.ActiveObjects-Erfassung.
- Unit- und In-Process-MCP-Tests funktionieren ohne Ansys.
- Die realen Integrationstests sind opt-in und bisher nicht erfolgreich gegen
  echtes Mechanical validiert.

Nutze ausschließlich .venv. Richte eine echte Testsession entweder so ein:

1. bevorzugt connect zu einem vom Benutzer vorbereiteten Mechanical-gRPC-Server
   mit GUI und cleanup_on_exit=false; oder
2. start mit batch=False und einem ausdrücklich für den Test verwendeten leeren
   Projekt.

Hänge dich nicht an eine beliebige normale Workbench-/Mechanical-Sitzung, wenn
kein offiziell unterstützter gRPC-Server läuft. Verändere kein Nutzerprojekt.

Führe zuerst den bestehenden read-only Modellinspektions-Roundtrip aus. Prüfe
Session-Wiederverwendung und Cleanup/Ownership ohne eine nutzereigene verbundene
Instanz zu beenden.

Validiere danach CurrentSelection mit expliziten, kurzen Captures für:

- keine Auswahl;
- eine Geometriefläche;
- mehrere gleichartige Geometrieentitäten;
- mindestens eine Knoten- und eine Elementauswahl, sofern im vorbereiteten
  Modell vorhanden;
- eine Elementflächenauswahl, sofern sicher herstellbar;
- ein oder mehrere aktive Tree-Objekte;
- allgemeines ISelectionInfo versus verfügbare reichere
  IMechanicalSelectionInfo-Capabilities.

Dokumentiere für jeden real beobachteten Fall:

- exakten nativen SelectionType-Text;
- tatsächliche Befüllung und Längen von Ids, Entities und ElementFaceIndices;
- den nativen Typtext der Entities;
- Tree.ActiveObjects-Felder;
- Produkt-/Projekt-/Modellfelder;
- JSON-Kompatibilität;
- Mechanical-Version, Start-/Connect-Modus und GUI-Konfiguration;
- ob der Fall erfolgreich, nicht verfügbar oder versionsabhängig war.

Wenn eine aktuelle Codeannahme durch die echte Laufzeit widerlegt wird, ändere
nur den kleinsten Adapter-/Normalisierungsbereich und ergänze einen
entsprechenden Regressionstest mit Fake-Payload. Erfinde keine Revision-Hashes,
Geometriedeskriptoren oder Semantik.

Nicht implementieren: Named Selections, Highlighting, Target Resolution,
LLM-Erklärung, Lasten, Lagerungen, Kontakte, Materialien, Mesh Controls, Solve-
oder DPF-Erweiterungen, build123d/OCP, Viewer, CAD-/Preprocessing-Funktionen oder
eine Entscheidung zum ersten physikalischen Phänomen.

Führe abschließend mindestens aus:

.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python -m ansys_mechanical_mcp.server --check-environment
git diff --check

Berichte getrennt, was mit Fakes, im MCP-Roundtrip und gegen echtes Mechanical
validiert wurde. Aktualisiere docs/api-research.md und Statusdokumente nur mit
tatsächlich beobachteten Ergebnissen. Kein Commit oder Push.
```
