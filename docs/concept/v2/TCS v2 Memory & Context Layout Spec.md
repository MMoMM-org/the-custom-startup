Summary  
Ich schreibe dir einen Rohentwurf für eine „TCS v2 Memory & Context Layout“-Spec, die Claude‑Memory (CLAUDE.md + Auto‑Memory), dein 3‑Layer‑Modell (global/project/repo), die Lifetime‑Layer und einen optionalen Context/MCP‑Layer (context-mode + Kairn) integriert.[1][2][3][4][5][6]

NOTE: Alle Verzeichniss und Skill Namen etc sind noch nicht final beschlossen.

***

## 1. Zweck und Ziele

- Ziel: Einheitliches Design für **CLAUDE.md**, Memory‑Bank und Context‑Layer, das  
  - mit Claude Codes bestehendem Memory‑System kompatibel ist (CLAUDE.md, Auto‑Memory, rekursive Discovery),[4][7]
  - TCS‑Vision (3 Layer, progressive disclosure) respektiert,[2]
  - und optional einen Context/MCP‑Layer (context-mode, Kairn) nutzen kann, ohne TCS hart daran zu koppeln.[5][6]

***

## 2. Scopes, Pfade und Discovery

### 2.1 Scopes

Wir unterscheiden drei inhaltliche Scopes (TCS) und mappen sie auf Claude Codes Filesystem‑Verhalten.[2][4]

- **Global Scope (User)**  
  - Speicherort: `~/.claude/`.[4]
  - Dateien:  
    - `~/.claude/CLAUDE.md` – globale Präferenzen, Arbeitsphilosophie, universelle Prinzipien.[1][2][4]
    - `~/.claude/includes/*.md` – lazy‑Load Dateien (z.B. `memory-general.md`, `memory-tools.md`).[2]

- **Project Scope**  
  - Root: `~/Kouzou/projects/<project>/`.  
  - Dateien/Dirs:  
    - `PROJECT.md` (oder `project.md`) – Projektbeschreibung, Ziele, konzeptionelle Domain‑Infos.[2]
       - sehr klein, lazy loading von anderen Informationen aus dem gleichen Verzeichnis
    - `CLAUDE.project.md` – Projekt‑Routing‑Regeln, z.B. wohin Projekt‑Konventionen und Workflows gehen.[2]
      - werden wir nicht nutzen siehe 2.3
    - `*` – projektweite Memory‑Docs, lazy geladen per Referenz.[1][2]
      - Struktur wie Repo Scope

- **Repo Scope**  
  - Root: Git‑Repo.  
  - Dateien/Dirs:  
    - `.CLAUDE.md` – Repo‑Anweisungen, Memory‑Routing für dieses Repo.[4][2]
      - Enthält einen @ include einer PROJECT.md Datei falls das Repo Bestandteil eines Projektes ist.
      - Basieren darauf enablen dann alle entsprechenden Skills einen Projekt Modus.
    - `docs/ai/memory/`:  
      - `general.md`, `tools.md`, `domain.md`, `context.md`, `troubleshooting.md`, `decisions.md`.[8][2] bzw. entsprechende Verzeichnisse mit dann entsprechenden Dateien pro Tool, Domain etc.
    - Optionale Verzeichnis‑CLAUDEs: `src/CLAUDE.md`, `docs/CLAUDE.md`, `tst/obsidian-testvault/CLAUDE.md` – gelten nur, wenn in diesem Verzeichnis gearbeitet wird (Claude Codes rekursive Discovery).[9][4]

### 2.2 Discovery-Verhalten (Claude Code)

- Claude Code liest `CLAUDE.md` und `CLAUDE.local.md` rekursiv von current working directory nach oben (bis `/`).[9][4]
- `CLAUDE.md` in Unterverzeichnissen werden nur geladen, wenn man dort arbeitet – genau dein gewünschtes „lazy loading durch Pfad“.[4]
- `~/.claude/CLAUDE.md` wird immer geladen.[4]

### 2.3 Memory Rules

Die generellen Regeln für die Memory Rules, also was geht wohin sollte in den Skills eingebaut sein.
Es sollte Override Funktionalität auf Project und Repo Scope geben.
Diese Overrides sollten auch über die Skills erstellt werden.

***

## 3. Memory-Achsen: Scope × Lifetime

Wir kombinieren TCS‑Scopes mit deinen Lifetime‑Kategorien.[2]

### 3.1 Lifetime-Definitionen

- **Static longlived**  
  - praktisch unveränderlich (Identität, Grundprinzipien, „How I work“).  
- **Longlived**  
  - seltene Änderungen (Tech‑Stack, Architektur‑Leitplanken, TDD/SDD‑Prinzipien).[10][1]
- **Medium lived**  
  - repo-/projektbezogene Regeln, die sich bei Releases/Refactors ändern (Domainmodell, konkrete Patterns, Entscheidungen).[8][2]
- **Short lived**  
  - TODOs, Plans, aktuelle Troubleshooting‑Notizen.[8][2]
- **Really short lived**  
  - Session‑Handover, temporäre Arbeitskontexte (was war im letzten Prompt, aktive Tasks etc.).[3][6]

### 3.2 Zuordnung (Beispiele)

| Scope  | Lifetime             | Beispiele                                  | Speicherort                                           |
|--------|----------------------|--------------------------------------------|-------------------------------------------------------|
| Global | static longlived     | persönliche Werte, Kommunikationsstil      | `~/.claude/CLAUDE.md`, `includes/memory-general.md`[1][2][4] |
| Global | longlived            | bevorzugte Tools, globale TDD/SDD‑Prinzipien | `includes/memory-tools.md`, global patterns‑Docs[1][10] |
| Project | longlived/medium    | Projekt‑Ziele, Domain‑Boundaries, Governance | `PROJECT.md`, includes im Project Verzeichnis |
| Repo   | medium lived         | Repo‑Patterns, Naming, Arch‑Entscheidungen | `docs/ai/{general,domain,decisions, etc}`[8][2] |
| Repo   | short lived          | TODOs, Plans, aktuelle Bugs                | `Todo.md`, `troubleshooting.md`[8][2] |
| Session| really short lived   | Session Guide, Task State                  | context-mode/Kairn DB (MCP), nicht in Filesystem[3][6][5] |

***

## 4. Reflect- & Memory-Prozess

### 4.1 Claude Code: Auto Memory und Manual Memory

- Claude kann Memory sowohl über Files (CLAUDE.md / Auto‑Memory‑Files) als auch über ein Memory‑Tool (/memories‑Dir) verwalten.[7][3]
- TCS nutzt die **File‑Variante** plus reflect‑Plugin:  
  - `claude-reflect` Plugin: erfasst Korrekturen/Feedback, schreibt in entsprechende Memory‑Files (global/project/local).[1]
    - dieses geht in das tcs plugin auf

### 4.2 TCS-Erweiterung: Mehrere spezialisierte Skills

Statt einem Mega‑Skill definieren wir eine Pipeline:  

1. **tcs-helper.memory-route**  
   - Input: reflect‑Output (Learnings) + Pfad/Scope Info.  
   - Aufgabe:  
     - Mappt Learnings auf `docs/ai/memory/{general,tools,domain,context,troubleshooting,decisions}.md` im Repo, plus ggf. Projekt‑Memory.[8][2]
     - Orientiert sich an miyo-reflect Workflow, ersetzt MiYo‑Spezifika durch generische Routing‑Regeln.[11][1]
    - Project Routing wird über include einer PROJECT.md in CLAUDE.md erreicht

2. **tcs-helper.memory-sync**  
   - Aufgabe:  
     - Stellt sicher, dass Projekt‑/Repo‑CLAUDE die relevanten Memory‑Files über kurze „Index/Import“-Hinweise referenzieren (keine Vollimporte).[1][2]
     - Hält `MEMORY.md`‑Index pro Repo/Projekt bei ~200 Zeilen (Conneely‑Regel: Index statt Volltext).[1][2]

3. **tcs-helper.memory-cleanup**  
   - Aufgabe:  
     - Wendet Token‑Budget‑Regeln aus centminmod an: resolved Troubleshooting/Epics archivieren, Duplikate entfernen, alte TODOs markieren.[8][1]
     - Erkennt ob Dinge in Claude.md eigentlich ein Skill sein könnten und ruft dann memory-promote auf.

4. **tcs-helper.memory-promote**  
   - Aufgabe:  
     - Nutzt intern `reflect-skills` (oder ähnliches) und scannt `.claude/memory/domain.md` auf wiederkehrende Patterns.[1][2]
     - Schlägt Skills in `tcs-patterns/*` vor und ersetzt längere Memory‑Einträge durch Pointer („see tcs-patterns/hexagonal“).[2][1]
     - Hier müssen wir noch einmal schauen. https://github.com/BayramAnnakov/claude-reflect/blob/main/commands/reflect-skills.md könnte da wirklich hilfreich, die Lösung sein.

**Flow in Worten:**  
- Nach einer Session, vor Context‑Compaction oder durch Hook Trigger:  
  - `reflect` → `tcs-helper.memory-route` → optional `memory-cleanup` → periodisch `memory-promote`.[11][1][2]
  
### 4.3 YOLO Mode

Wenn Claude im YOLO Mode läuft müßte vielleicht alles in eine strukturierte Datei geschrieben werden damit der User nachher entsprechende Entscheidungen treffen kann.
Auf jeden Fall sollte eine Dokumentation erstellt werden was im YOLO Mode alles in Dateien geschrieben wurde.

***

## 5. Context- und MCP-Layer

### 5.1 Ziele des Context-Layers

- Kontextfenster klein halten, ohne Information zu verlieren.[6][12]
- Session‑Kontinuität, auch wenn Claude‑Context kompaktet oder neue Sessions starten.[3][6]
- Flexibel:  
  - läuft nur mit Standard‑Context‑Server,  
  - nutzt Kairn als Upgrade, falls installiert.[13][5]

### 5.2 Context-Mode (Standard Context MCP)

- context-mode trackt pro Projekt: File‑Edits, Git‑Ops, Tasks, Errors, Entscheidungen in einer SQLite DB und generiert vor Context‑Compaction eine ≤2KB „Session Guide“.[12][6]
- Reduziert Kontext um ~98%, indem es nur relevante, deduplizierte Auszüge zurückgibt.[6][12]

In TCS‑Design:  
- context-mode ist **Option**, aber erste Wahl für „normalen“ Context‑Server.  
- TCS‑Skills, die auf Kontext bauen (z.B. `tcs-workflow.analyze`, `debug`) sollten:  
  - zuerst versuchen, eine Session‑Zusammenfassung via context-mode zu holen,  
  - dann bei Nicht‑Verfügbarkeit auf Files (Memory‑Docs + Code) zurückfallen.[6][2]

### 5.3 Kairn (Semantic Memory Upgrade)

- Kairn bietet graph‑basiertes, semantisches Memory über Projekte hinweg („How did I solve auth?“), als Upgrade auf context/evolving‑Lite Layer.[14][5][13]
- TCS soll **nicht** von Kairn abhängen, aber Kairn nutzen können, wenn vorhanden.  

Design:  
- Context‑Abstraktion in TCS als „Context Server Interface“:  
  - **Default**: context-mode (Standard‑Context).  
  - **Wenn `kairn` installiert**:
    - wird in Context-Mode MCP Server Registriert und handelt dann den context Part.
    - TCS‑Context‑Skills (z.B. `tcs-helper.context-search`) fragen Kairn mit semantischen Queries (z.B. „auth bug fix in this repo“),  
    - context-mode kann sich dann auf raw Tool‑Outputs konzentrieren, Kairn auf „semantische Sessions“.[5][13]

### 5.4 Kontextfluss im Zusammenspiel

1. Während der Arbeit:  
   - context-mode zeichnet Tool‑Output, Fehler, Kommandos auf.[6]
2. Wenn Kontext groß wird oder Session endet:  
   - Claude schreibt Zusammenfassung in Memory‑Files (per Memory‑Tool oder reflect + tcs-helper.memory‑Flow),[3][1]
   - context-mode erzeugt Session Guide + Index in DB.[6]
3. In einer neuen Session:  
   - Claude lädt CLAUDE.md/Memory‑Files (langfrist-/mittel‑lebige Fakten).[4][2]
   - Context‑Skills holen Session‑Kontext via context-mode (und Kairn, falls vorhanden).[13][5][6]
    
### 5.5 MCP Registry und Security
Siehe eigenes Dokument context-mode-mcp-server.md

***

## 6. Richtlinien für Inhalte (Was geht wohin?)

Aus sources/TCS‑Vision abgeleitet.[1][2]

- **CLAUDE.md / CLAUDE.project / Verzeichnis‑CLAUDE**  
  - Regeln, Prinzipien, Workflows.  
  - Routing‑Regeln, wann welche Memory/Context‑Skills laufen.  
  - Keine langen Listen, keine detaillierte Historie → dafür Memory‑Docs/DB.[2][1]

- **Memory-Docs (general/tools/domain/...)**  
  - Fakten, die du oder das Team später gezielt nachlesen wollt (Patterns, Entscheidungen, Troubleshooting‑Rezepte).[8][2]
  - Medium/short lived, menschenlesbar und git‑versioniert.  

- **Context-DB (context-mode / Kairn)**  
  - alles, was sehr kurzlebig ist oder sehr umfangreich (Raw‑Tool‑Output, Logs, Zwischenzustände), aber später semantisch gesucht werden soll.[5][6]
  - Primär für AI, nicht als Haupt‑Human‑Interface gedacht (optional Web‑UI wie bei manchen Memory‑Plugins).[15][5]

***

## 7. Offene Punkte / spätere Entscheidungen

- Exakte Verzeichnisnamen: `docs/ai/memory` vs `.claude/memory` vs `memory/` – in einer ADR fixieren.[2]
- Context‑Server‑Discovery: wie TCS erkennt, ob context-mode und/oder Kairn installiert sind (z.B. via Tool‑Availability).[5][6]
- Konkretes Interface von `tcs-helper.context-*` Skills (State, Modes) – nach erstem Prototypen von memory‑Flow definieren.[2]

***

Wenn du magst, kann ich dir als nächsten Schritt ein konkretes Markdown‑Dokument im Stil deiner vorhandenen TCS‑Docs schreiben („TITLE …“, Tabellen etc.), das du direkt als `tcs-memory-and-context-layout.md` ins Repo legen kannst.

Sources
[1] sources.md [URL redacted — contained expired AWS STS session token]
[2] tcs-vision.md [URL redacted — contained expired AWS STS session token]
[3] Memory tool - Claude API Docs https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
[4] Claude Code's Memory: Working with AI in Large Codebases https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with
[5] PrimeLine: Open Source Claude Code Plugins & Tools https://primeline.cc
[6] mksglu/context-mode v1.0.0 on GitHub - NewReleases.io https://newreleases.io/project/github/mksglu/context-mode/release/v1.0.0
[7] Claude Code's Memory System: The Full Guide (Most Developers Miss 90% of This) https://www.youtube.com/watch?v=FRwZg6VOjvQ
[8] overlap-analysis.md [URL redacted — contained expired AWS STS session token]
[9] [DOC] CLAUDE.md discovery - documentation is inconsistent #722 https://github.com/anthropics/claude-code/issues/722
[10] tdd-sdd-integration.md [URL redacted — contained expired AWS STS session token]
[11] SKILL.md [URL redacted — contained expired AWS STS session token]
[12] mksglu/claude-context-mode https://x.com/mksglu/status/2027803127898911186
[13] primeline-ai/evolving-lite: A self-evolving Claude Code ... https://github.com/primeline-ai/evolving-lite
[14] PrimeLine AI https://github.com/primeline-ai
[15] GitHub - thedotmack/claude-mem: A Claude Code plugin that automatically captures everything Claude does during your coding sessions, compresses it with AI (using Claude's agent-sdk), and injects relevant context back into future sessions. https://github.com/thedotmack/claude-mem
[16] Persistent Memory Between Claude Code Sessions · Issue #14227 https://github.com/anthropics/claude-code/issues/14227
[17] christian-byrne/claude-code-vector-memory: Semantic ... https://github.com/christian-byrne/claude-code-vector-memory
[18] [BUG] - Fails to read memories (claude.md) unless explicitly added to every prompt · Issue #2670 · anthropics/claude-code https://github.com/anthropics/claude-code/issues/2670
[19] Documentation about CLAUDE.md locations, seems not ... https://github.com/anthropics/claude-code/issues/2274
[20] unify output format and add test for gpu-types · PrimeIntellect-ai/prime-cli@637c79b https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13597457310
[21] GitHub - matthewrobertbell/mkcontext: Easily generate context for ChatGPT from files https://github.com/matthewrobertbell/mkcontext
[22] resolve conflicts · PrimeIntellect-ai/prime-cli@0d30140 https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13446167257/workflow
[23] Workflow runs · modelcontextprotocol/modelcontextprotocol http://github.com/modelcontextprotocol/modelcontextprotocol/actions
[24] [Resource]: claude-mem - Instant Persistent Memory ... https://github.com/hesreallyhim/awesome-claude-code/issues/167
[25] Workflow runs · PrimeIntellect-ai/prime-cli https://github.com/PrimeIntellect-ai/prime-cli/actions
[26] mksglu - Overview https://github.com/mksglu
[27] GitHub - NikiforovAll/claude-code-rules https://github.com/NikiforovAll/claude-code-rules
[28] add better default value selection when creating pods (#25) · PrimeIntellect-ai/prime-cli@11849cc https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13505020631/workflow
[29] Troubleshooting https://docs.basicmemory.com/integrations/claude-code
[30] You (probably) don't understand Claude Code memory. https://joseparreogarcia.substack.com/p/claude-code-memory-explained
[31] primeline-ai/universal-planning-framework https://github.com/primeline-ai/universal-planning-framework
[32] Claude Code Memory: The File That Changes Everything https://www.youtube.com/watch?v=e1F7zUWRm3w
[33] メモリドキュメント | Skills Marketplace https://lobehub.com/ja/skills/hlibkoval-claudemd-memory-doc
