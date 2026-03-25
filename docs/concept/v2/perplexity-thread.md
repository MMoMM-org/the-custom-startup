<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# ich möchte the-custom-startup umbauen und zum zentralen plugin repo machen für meine development arbeit. Anbei sind bereits ein paar Informationen.

Da eigentlich alles von der modularen claude.md und dem entsprechenden memory management abhängt wollte ich damit anfangen.
anbei noch einmal ein paar zusätzliche quellen die ich betrachen möchte

> [!connect] Your way around
> up:: [[60-06 MiYo Research (MOC)]]
> related::

# [[60-06 Referenzes Claude Code and Memory]]

``` dataviewjs
let page = dv.current();
if (page.summary && page.summary.length > 0) {
    dv.paragraph("\n**Summary:** _" + page.summary + "_");
}
```


## General

- @ loads files directly, only use this if 100% necessary
- Giving a reason to load a "named" file loads the file only when needed
- Claude will load every Claude.md file in the directory it is working in.. so you can have specific claude.md files in for example the test directory to cover the very specific testing for this repo.
- context handling is still problematic, might need custom approach (TBD)


## Claude.md

A good approach to Claude.md Management
**[GitHub - citypaul / .dotfiles](https://github.com/citypaul/.dotfiles)** - *My dotfiles* <br>(574 ⭐'s) | No Idea

a similar approach, using documentation to manage memory, instructions etc.
[Reddit - managing large claude files with documentation](https://www.reddit.com/r/ClaudeAI/comments/1lr6occ/tip_managing_large_claudemd_files_with_document/)

another one using documentation and file structur to limit context and modularize claude.md
**[GitHub - peterkrueck / Claude-Code-Development-Kit](https://github.com/peterkrueck/Claude-Code-Development-Kit)** - *Handle context at scale - my custom Claude Code workflow including hooks, mcp and sub agents* <br>(1.3k ⭐'s) | No Idea

very cool idea of having a session init file which does make sure the coding in THAT repo starts, by starting needed docker containers etc.. also has a lot of good scripts to setup the intial start of claude
“Stop Wasting Tokens: How to Optimize Claude Code Context by 60%” Smart session hooks and tiered documentation can save you hundreds of dollars monthly A practical guide for any Claude Code …
[“Stop Wasting Tokens: How to Optimize Claude Code Context by 60%”](https://medium.com/@jpranav97/stop-wasting-tokens-how-to-optimize-claude-code-context-by-60-bfad6fd477e5)

The basis of it all.. "Progressive Disclosure"
`CLAUDE.md` is a high-leverage configuration point for Claude Code. Learning how to write a good `CLAUDE.md` (or `AGENTS.md`) is a key skill for agent-enabled software engineering.
[Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)

can be used to help with creating own skills to help updating the claude.md
**[claude-plugins-official / plugins](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/claude-md-management)** - *claude-md-management* <br>(14.6k ⭐'s) | No Idea

## Memory

Uses a way to split up the code into different areas, which maps closely to what I started with in [[60-02 Kokoro Architecture|Kokoro Architecture]]
**[GitHub - centminmod / my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)** - *Shared starter template configuration and CLAUDE.md memory bank system for Claude Code* <br>(2.1k ⭐'s) | No Idea

Similar direction, adds specific memory for specific categories.. tools , domains etc.
How a single Substack post unlocked Claude Code's hidden memory system - and the full setup prompts to replicate it yourself.
[How I Finally Sorted My Claude Code Memory | \#98](https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory)

And one of the best ways to get stuff into memory, already included in the MiYo approach atm.
**[GitHub - BayramAnnakov / claude-reflect](https://github.com/bayramannakov/claude-reflect)** - *A self-learning system for Claude Code that captures corrections, positive feedback, and preferences — then syncs them to CLAUDE.md and AGENTS.md.* <br>(843 ⭐'s) | No Idea
also has skill discovery for transferring memory into skills

## Context

while a little bit of track still worthwhile as all of this is about the context window.

this is a good start for cutting down on context usage:
**[GitHub - mksglu / context-mode](https://github.com/mksglu/context-mode)** - *Privacy-first. MCP is the protocol for tool access. We're the virtualization layer for context.* <br>(5.9k ⭐'s) | No Idea

mcp server gateway, as a basic idea Peter Kruek above has also a hook to strip sensitive data
**[GitHub - lasso-security / mcp-gateway](https://github.com/lasso-security/mcp-gateway)** - *A plugin-based gateway that orchestrates other MCPs and allows developers to build upon it enterprise-grade agents.* <br>(360 ⭐'s) | No Idea

this together with this gateway approach to reduce the amount of tools the ai sees might be worth using to create an own MCP Server component
**[GitHub - agiletec-inc / airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway/tree/main)** - ** <br>(141 ⭐'s) | No Idea

a reference for the mksglu / context-mode repo
[MCP server that reduces Claude Code context consumption by 98% | Hacker News](https://news.ycombinator.com/item?id=47193064)

Summary
Du hast in TCS v2 bereits ein ziemlich klares Design für modulare CLAUDE.md-Dateien, ein dreistufiges Memory-System und progressive disclosure – genau das, was du brauchst, um „the-custom-startup“ zu deinem zentralen Plugin‑/Skill‑Repo zu machen. Der sinnvollste Startpunkt ist tatsächlich die Memory‑Schicht (claude-reflect + tcs-helpermemory + MiYo‑Router‑Muster), weil davon abhängt, wie du Skills, CLAUDE.md und Kontextverbrauch strukturierst.[^1_1][^1_2][^1_3][^1_4]

## Findings

1. Ausgangslage: TCS v2 als zentrales Framework

- TCS v2 ist bereits als „spec‑driven, test‑verified development framework“ für Claude Code gedacht, mit klarer Trennung in tcs-workflow, tcs-team, tcs-helper und tcs-patterns.[^1_3]
- Die Overlap‑Analyse zeigt, dass du wesentliche Ideen aus obrasuperpowers, citypaul.dotfiles und centminmod bereits in einen konsistenten Plugin‑Schnitt einmappt hast (ABSORB/MERGE/DEPRECATE/SKIP).[^1_1]
- sources.md hält die externen Quellen inkl. claude-reflect, citypaul, centminmod, Conneely etc. schon sauber für Attribution nach.[^1_2]

2. Zielbild: TCS als zentrales Plugin‑Repo

- TCS v2 ist bereits in vier Plugins geschnitten, die sich gut als „zentraler Plugin‑Hub“ eignen:
    - tcs-workflow: Kernpipeline (brainstorm, specify, implement, verify, review, debug, parallel-agents, guide).[^1_3]
    - tcs-team: Spezialisten (the-architect, the-developer, the-tester etc., inkl. ADR‑Agent).[^1_3]
    - tcs-helper: Setup, Memory, Git‑Worktrees, Finish‑Branch, Docs, Evaluate, Import‑Skill.[^1_1][^1_3]
    - tcs-patterns: Domain‑Skills (DDD, hexagonal, functional, typescript-strict, mutation-testing, frontend/react, twelve-factor).[^1_1][^1_3]
- Für dein Ziel „zentraler Plugin‑Hub“ musst du im Grunde „nur noch“:
    - tcs-helpermemory und die CLAUDE.md‑Generatoren stabilisieren,
    - Import‑/Evaluate‑Pfade (tcs-helperimport-skill, tcs-helperevaluate) wirklich implementieren,
    - und deine MiYo‑spezifischen Dinge (miyo-reflect Pattern) sauber in diese Architektur einbetten.[^1_4][^1_3][^1_1]

3. Memory‑System und modulare CLAUDE.md (Kern deiner Frage)

- Du hast im Vision‑Dokument ein klares 3‑Layer‑Memory‑Modell: global (.claude), project (.claude/projects/memory), repo (.claude/memory/*).[^1_3]
- Kategorien pro Layer: general, tools, domain, context, auto-memory, troubleshooting, decisions – mit expliziter Trennung nach Scope (global/project/repo).[^1_3]
- tcs-helpermemory baut bewusst NICHT ein eigenes Capture‑System, sondern erweitert claude-reflect mit:
    - gpr‑Routing‑Awareness (global/project/repo),
    - Kategorie‑Routing (tools.md, domain.md etc.),
    - Promotion‑Pfad via reflect-skills -> tcs-patterns (Skill‑Promotion statt immer größerer CLAUDE/MEMORY Files).[^1_2][^1_1][^1_3]
- Routing‑Regeln gehören in CLAUDE.md, nicht in MEMORY.md; MEMORY.md ist nur Index mit ~200 Zeilen Budget.[^1_2][^1_3]
- MiYo‑Pattern miyo-reflect:
    - SKILL.md definiert bereits, wie ein Memory‑Router nach reflect läuft, ohne Bestätigung, mit klaren Destinations (miyo-profile, miyo-decisions, outbox‑Handoffs, ADR‑Trigger).[^1_4]
    - Das ist praktisch die Blaupause für die Repo‑spezifische Erweiterung von claude-reflect, die du in tcs-helpermemory generalisieren willst.[^1_4][^1_3]

4. Wie du das konkret in „zentraler Plugin‑Repo“-Form gießt

### a) Zielstruktur für CLAUDE.md

- Global CLAUDE.md (User‑Level):
    - ~100 Zeilen, „Philosophy First“ im Stil citypaul v3.0.0: Kernprinzipien, generelle Arbeitsweise, Verweis auf TCS‑Plugins, aber keine Details.[^1_2][^1_3]
    - Importiert global nur:
        - TCS guide‑Skill (analog using-superpowers, jetzt tcs-workflowguide).[^1_1][^1_3]
        - Routing‑Regeln für globale Memory‑Dateien (global general/tools/domain etc.).[^1_2][^1_3]
- Projekt‑CLAUDE (.claude/CLAUDE.project.md):
    - Wird von tcs-helpersetup generiert:
        - liest Stack (z.B. TypeScript/Next.js, Go, etc.),
        - fügt passende tcs-patterns‑Skills ein,
        - konfiguriert hooks (format on save, lint).[^1_1][^1_3]
    - Enthält nur Projekt‑Routing‑Regeln (z.B. wo Projekt‑Konventionen, Workflow‑Entscheidungen landen).[^1_3]
- Repo‑CLAUDE (.claude/CLAUDE.md):
    - Enthält:
        - Routing für .claude/memory/* (general.md, tools.md, domain.md, context.md, troubleshooting.md, decisions.md).[^1_1][^1_3]
        - Hinweise, wie tcs-helpermemory nach reflect aufzurufen ist (Mode: route, sync, cleanup, promote).[^1_3]
        - Optional: repo‑spezifische MiYo‑Router‑Erweiterungen (z.B. miyo‑Profile‑Pfad).[^1_4][^1_3]


### b) tcs-helpermemory als „Memory‑Plugin“ für alles

- Eine Skill‑Schnittstelle (memory) mit Modes:
    - memory route: nach reflect aufrufen, routet Learnings in passende .claude/memory/* Dateien.[^1_3]
    - memory sync: sorgt dafür, dass diese Dateien in die Projekt‑CLAUDE importiert werden.[^1_3]
    - memory cleanup: Token‑Budget sauber halten (Stale Einträge, Troubleshooting‑Archiv).[^1_1][^1_3]
    - memory promote: nutzt reflect-skills, um wiederkehrende Domain‑Patterns in tcs-patterns Skills zu promoten.[^1_2][^1_3]
- Technisch: du kannst miyo-reflect als Referenz nehmen, wie Interface + Constraints aussehen sollten (State‑Objekt, RoutedItem etc.).[^1_4]


### c) Import‑ und Evaluate‑Pfad für externe Plugins

- sources.md und overlap-analysis.md definieren schon, wie du externe Repos einordnest (ABSORB/MERGE/DEPRECATE/SKIP).[^1_2][^1_1]
- tcs-helperevaluate und tcs-helperimport-skill sollten:
    - SKILL.md eines Fremd‑Repos gegen deine Evaluation‑Checkliste prüfen (Vision‑Dok: 12‑Punkte‑Score zu Uniqueness, Fit, Integration, Quality).[^1_3]
    - Bei ABSORB: neue tcs-* Skill‑Datei erzeugen und SKILL.md auf TCS‑Style normalisieren (Interface, Constraints, State).[^1_1][^1_3]
    - Bei MERGE: Patch für bestehenden Skill erzeugen (z.B. tcs-workflowbrainstorm um spec-review Subagent‑Loop erweitern).[^1_1]
    - Bei DEPRECATE/SKIP: nur im sources.md vermerken, keine Aktivierung.[^1_2][^1_1]


### d) Verbindung zu TDD/SDD‑Pipeline

- Dein TDD/SDD‑Konzept ist bereits sauber:
    - SDD definiert Contracts; jede Interface‑Definition erzeugt TDD‑Targets.[^1_5]
    - specify-plan erzeugt Plan‑Tasks mit expliziten RED/GREEN/REFACTOR‑Schritten.[^1_5][^1_1]
    - implement ruft tcs-workflowtdd vor jeder Implementierungsaufgabe auf, erzwingt „NO PRODUCTION CODE WITHOUT FAILING TEST“ und verwendet verify/test als Gate.[^1_5][^1_1][^1_3]
- Für dein zentrale‑Repo‑Ziel heißt das:
    - tcs-workflowtdd, tcs-workflowspecify-plan und tcs-workflowimplement müssen so abstrahiert werden, dass sie in beliebigen Repos funktionieren, solange die Memory/CLAUDE‑Struktur nach TCS‑Standard ist.[^1_5][^1_1][^1_3]
    - MiYo‑u. andere Projekte bekommen denselben Workflow out of the box, plus eigene patterns in tcs-patterns.

5. Risiken / Gegenargumente

- Komplexität und Einstiegshürde:
    - Drei Memory‑Layer, vier Plugin‑Namespaces und ein Skill‑Bewertungsframework sind mächtig, aber heavy für kleine Experimente.[^1_1][^1_3]
    - Gegenmaßnahme: „minimal TCS profile“ definieren (nur tcs-workflowguide + tcs-workflowspecify + tcs-workflowimplement + minimalist memory route), den Rest opt‑in über tcs-helpersetup.[^1_3]
- Abhängigkeit von claude-reflect Stack:
    - Dein Design setzt stark auf claude-reflect, reflect-skills und den aktuellen Claude Code‑Marketplace‑Status.[^1_2][^1_3]
    - Falls sich APIs ändern, hängt tcs-helpermemory daran. Gegenmaßnahme: deine eigenen SKILL.md‑Interfaces so kapseln, dass die interne Implementierung austauschbar ist.
- Kontextbudget immer noch kritisch:
    - Auch mit Memory‑Bank‑Architektur und Promotion‑Pfad bleibt das Risiko, dass zu viele Memory‑Files in einer Session geladen werden.[^1_2][^1_3]
    - Deshalb ist die strikte „Progressive Disclosure“-Regel wichtig: CLAUDE.md bleibt schlank, Memory nur als Index/Router, Inhalte via Skills on demand.[^1_2][^1_3]


## Sources

- overlap-analysis.md – TCS v2 Absorption Plan (Mapping externer Skills zu tcs-*, inkl. Memory‑Bank‑Architektur).[^1_1]
- sources.md – Externe Quellen, insbesondere claude-reflect, citypaul.dotfiles, centminmod, Conneely, Reddit‑Thread zu modularer CLAUDE.md.[^1_2]
- tcs-vision.md – TCS v2 Vision, Plugin‑Architektur, Memory‑System, Evaluation‑Kriterien für neue Skills, Modular‑CLAUDE-Ansatz.[^1_3]
- tdd-sdd-integration.md – TDD/SDD‑Verzahnung, Rolle von specify-plan, implement und tdd/test.[^1_5]
- SKILL.md – miyo-reflect Skill, Persona/Interface/Constraints für Memory‑Routing nach reflect.[^1_4]


## Recommendations

1. Startsequenz für deinen Umbau

- Schritt 1: TCS‑Memory‑Session finalisieren
    - Aus tcs-vision.md die vorgesehene .claude/memory‑Verzeichnisstruktur konkretisieren (Dateinamen, Pfade, Beispiel‑Inhalte).[^1_3]
    - tcs-helpermemory SKILL.md definieren (Modes, State, Constraints) analog zu miyo-reflect.[^1_4][^1_3]
- Schritt 2: Generierung der CLAUDE.md‑Layer umsetzen
    - tcs-helpersetup so erweitern, dass es für ein neues Repo sowohl .claude/CLAUDE.md (repo) als auch CLAUDE.project.md erzeugt und die Memory‑Routing‑Regeln einbettet.[^1_1][^1_3]
    - Eine minimale Global‑CLAUDE.md‑Vorlage (philosophy‑First, TCS‑Guide) definieren.[^1_2][^1_3]
- Schritt 3: MiYo‑Integration als Referenz‑Implementierung
    - miyo-reflect in das neue tcs-helpermemory‑Muster überführen: MiYo‑spezifische Destinations (miyo-profile, miyo-decisions etc.) als spezielle Routing‑Regeln im Repo‑CLAUDE.md.[^1_4][^1_3]
    - Damit MiYo als „Dogfood“-Repo für dein zentrales TCS‑Plugin‑Setup nutzen.
- Schritt 4: Evaluate/Import‑Pfad minimal nutzbar machen
    - tcs-helperevaluate: Evaluation‑Checkliste aus tcs-vision.md implementieren (Score 0–12, Handlungsempfehlung ABSORB/MERGE/DEPRECATE/SKIP).[^1_1][^1_3]
    - tcs-helperimport-skill: Für ABSORB‑Fälle generiert es eine TCS‑konforme SKILL.md‑Schablone in einem Ziel‑Plugin (z.B. tcs-patternshexagonal).[^1_3][^1_1]
- Schritt 5: TDD‑Gate produktiv schalten
    - tcs-workflowspecify-plan so schärfen, dass alle Plan‑Tasks RED/GREEN/REFACTOR plus SDD‑Referenz haben.[^1_5][^1_1]
    - tcs-workflowimplement zwingend über tcs-workflowtdd und verify laufen lassen, bevor ein Task als „done“ gelten darf.[^1_5][^1_1][^1_3]

2. Konkreter nächster Schritt (kleine, testbare Einheit)

- Als ersten praktischen Schritt würde ich vorschlagen:
    - Eine SKILL.md für tcs-helpermemory zu entwerfen, in der du:
        - Persona, State (learnedItems, repoScope, projectScope, globalScope), Modes (route/sync/cleanup/promote) definierst,
        - deine Routing‑Tabelle explizit reinschreibst (analog der Tabelle in tcs-vision.md),
        - und MiYo‑spezifische Destinationen als optionale Erweiterung referenzierst.[^1_4][^1_3]
- Wenn du möchtest, kann ich im nächsten Schritt einen konkreten Entwurf für diese tcs-helpermemory SKILL.md formulieren, der zu deinem bestehenden MiYo‑Pattern und den TCS‑Vision‑Dokumenten passt.

Womit willst du konkret anfangen: mit der SKILL.md für tcs-helpermemory, oder zuerst mit einer Template‑CLAUDE.md‑Struktur (global/project/repo) für dein neues zentrale‑Repo‑Setup?
<span style="display:none">[^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: overlap-analysis.md

[^1_2]: sources.md

[^1_3]: tcs-vision.md

[^1_4]: SKILL.md

[^1_5]: tdd-sdd-integration.md

[^1_6]: research-prompt.md

[^1_7]: prd-prompt.md

[^1_8]: brainstorm-prompt.md

[^1_9]: constitution-prompt.md


---

# zuerst will ich einmal das design complett aufbauen, und da sind ein paar Dinge zu beachten:

1) Pfade:
Global:

- für lazy loaded claude dateien (memory, personal information etc) in ~/.claude/includes
Project:
- befindet sich in einem zu bennenden Verzeichnis im Home, e.g. ~/Kouzou/projects/<project>/
Repo:
- Claude.md
    - Falls ein Project @ auf ~/Kouzou/projects/<project>/project.md (oder wie auch immer wir die nennen)
- ein Verzeichnis in der die anderen Dateien für Memory etc reinkommt.. diese werden dann meistens lazy loaded
    - wir könnten /docs/ai/memory /docs/ai/tools etc nutzen
- für bestimmte Verzeichnisse eine eigene Claude.md mit spezifischen informationen für dieses Verzeichnis
    - zu lazy loading nur dann wenn sich claude.md dort befindet.. z.b. tst/obsidian-testvault/CLAUDE.md mit genauer beschreibung was hier zu tun ist..
    - hiermit könnte man sich lazy loading befehle in der Repo Claude.md sparen. andere beispiele wären bestimmt /docs, /src etc.

2) Reflect:
das ganze reflect handling soll nicht mehr aus mehreren plugins / skills / hooks bestehen sondern in einen prozess gegossen werden.
der ansatz mit einem SKILL ist meine ich nicht wirklich gut, es sei denn wir können aus dem skill wiederrum heraus Agenten oder andere skills aufrufen..
sonst würde ich eigentlich spezifische genaue definierte skills bevorzugen
3) Architektur:
Claude.md, memory bank (bzw dokumentation des Memrory) mit Reflection und context minimierung gehören zusammen.
Hier müssen wir also auch einen entsprechenden plan haben wie wir das schritt für schritt erst einmal architektieren und dann weiter aufbauen.
4) Context Handling:
Ist sicherlich auch interessant und notwendig, zumal ja der memory server aus context-mode wiederum einen teil der infos der normalerweise in der memory bank landen müßte reduziert.
Ich würde diesen mcp server dann so ausbauen das er zusätzlich noch die ansätze von lasso und airis integriert und so als registrar für andere mcp server dienen kann
5) Memory Layer(?)
wenn wir 1 - 4 uns ansehen haben wir eigentlich auch mehrere Memory Layer(?)

- static longlived
    - dinge wie persönliche informationen, und andere prinzipien die universell sind
- longlived
    - dinge die sich nur sehr selten ändern
    - tech stack, design prinzipien
- medium lived
    - dinge die für ein repo / project relevant sind
- short lived
- todos, plans etc..
- really short lived
    - session handover
https://github.com/primeline-ai/kairn hat da einen netten Ansatz.. würde ich aber am Anfang wirklich nur EINBINDEN und nicht mit in tcs einbauen, allerdings würde KAIRN ja den Session Continuity Ansatz von context-mode ersetzen, das sollten wir entsprechend beachten

6) Use cases

- der memory-bank und findings, befehle etc in eigene dokumente aufzuteilen hilft nicht nur claude sondern auch einem menschen
- Dinge in einer Datenbank oder MCP Server zu handeln hilft der AI
deswegen möchte ich das ganze so aufbauen das beide etwas davon haben.
---
wie sollten wir jetzt die struktur und das design für claude.md, memory-bank und context aufbauen? sources.md hat da schon einen guten Ansatz zu definieren was wohin geht

Summary
Wir können dein Design sauber dreiteilen: Dateipfade/Struktur, ein einheitlicher „Reflect‑Pipeline“-Prozess mit mehreren feinen Skills statt einem Monster‑Skill, und ein Memory/Context‑Modell, das deine Layer (static → really short lived) auf die bestehenden TCS‑3‑Layer plus context‑mode/Kairn abbildet.[^2_1][^2_2][^2_3][^2_4]

## Findings

### 1. Pfad- und Strukturvorschlag

Ich mape deine Wünsche auf ein klares Layout, das zu TCS‑Vision und sources passt.[^2_2][^2_3]

**Global (User‑Scope)**

- Konfiguration:
    - `~/.claude/CLAUDE.md` – globaler Kern (Philosophie, Routing‑Regeln, Verweis auf TCS).[^2_3][^2_2]
    - `~/.claude/includes/` – lazy‑Load Dateien:
        - `memory-general.md` (statische/longlived persönliche Infos).
        - `memory-tools.md` (immer benutzte Tools/Integrationen).[^2_2][^2_3]
- Richtlinie: Global nur **static longlived** + **longlived** (Prinzipien, feste Präferenzen, globale Tools).[^2_3][^2_2]

**Project (zwischen Home und Repo)**

- Root: `~/Kouzou/projects/<project>/` (Name noch zu entscheiden).[^2_3]
- Dateien/Dirs:
    - `project.md` oder `PROJECT.md` – Projekt‑Kontext (Ziele, Domain, Workflows), fungiert als Projekt‑Memory‑Index.[^2_3]
    - `.claude/CLAUDE.project.md` – projektweite Routing‑Regeln (z.B. wohin Projekt‑Konventionen/Workflows).[^2_3]
    - `memory/` oder `docs/ai/project-memory/` – projektweite Memory‑Docs (z.B. `general.md`, `domain.md`), lazy geladen über Verweise aus CLAUDE.project.[^2_3]

**Repo (Code‑Scope)**

- Wurzel: Git‑Repo.
- Dateien/Dirs:
    - `.claude/CLAUDE.md` – Repo‑CLAUDE, enthält:
        - Routing für repo‑Memory,
        - Verweis auf Projekt‑ und Global‑Layer,
        - Infos zum Reflect‑Prozess (welche Skills in welcher Reihenfolge).[^2_3]
    - `.claude/memory/` oder `docs/ai/memory/`:
        - `general.md`, `tools.md`, `domain.md`, `context.md`, `troubleshooting.md`, `decisions.md` (wie in Vision beschrieben).[^2_1][^2_3]
    - Optional je Verzeichnis eine eigene `CLAUDE.md` (z.B. `src/CLAUDE.md`, `docs/CLAUDE.md`, `tst/obsidian-testvault/CLAUDE.md`), mit sehr fokussierten Anweisungen:
        - Diese werden nur geladen, wenn Claude in diesem Verzeichnis arbeitet (lazy load durch Pfad).[^2_2][^2_3]
- Richtlinie:
    - Repo‑Memory enthält primär **medium lived** (repo/project relevant) und **short lived** (TODOs, Plans, Troubleshooting), ggf. mit Archiv‑Sektion.[^2_2][^2_3]


### 2. Reflect-Prozess: Ein „Flow“, mehrere Skills

TCS‑Vision will ein einheitliches Memory‑System, aber baut bewusst auf claude-reflect + miyo-reflect + reflect-skills auf. Dein Wunsch „kein Monster‑Skill“ passt gut dazu.[^2_4][^2_2][^2_3]

**Vorgeschlagene Architektur**

- Basis bleibt:
    - `claude-reflect` Plugin – sammelt Korrekturen/Feedback und schreibt grob nach global/project/local.[^2_2][^2_3]
- TCS‑Layer als **Pipeline** statt eines Skills:

1. `tcs-helper.memory-route`
        - liest das, was reflect geschrieben hat (plus Session‑Log),
        - routet pro Repo nach `.claude/memory/{general,tools,domain,context,troubleshooting,decisions}.md`, analog zu miyo‑reflect, aber generisch.[^2_4][^2_2][^2_3]
2. `tcs-helper.memory-sync`
        - sorgt dafür, dass die relevanten Memory‑Files in Repo‑ und Projekt‑CLAUDE referenziert werden (Index/Imports), ohne sie komplett in den Kontext zu kippen.[^2_1][^2_3]
3. `tcs-helper.memory-cleanup`
        - wendet Regeln aus centminmod/context‑.cleanup‑Mustern an: alte Troubleshooting‑Einträge archivieren, resolved TODOs verschieben, Token‑Last reduzieren.[^2_1][^2_2]
4. `tcs-helper.memory-promote`
        - nutzt intern `reflect-skills`, um Wiederholungsmuster in `domain.md` zu erkennen und als `tcs-patterns/*` Skills vorzuschlagen („Promotion‑Pfad“).[^2_2][^2_3]

Damit erfüllst du:

- Kein einzelner Mega‑Skill, sondern mehrere klar definierte Skills (route/sync/cleanup/promote).[^2_1][^2_3]
- Trotzdem ein „Prozess“, der in CLAUDE.md beschrieben ist:
    - „Nach reflect: call memory-route → optional memory-cleanup → periodisch memory-promote.“[^2_4][^2_3]


### 3. Memory-Layer Modell + Kontext

Du hast bereits 3 Scope‑Layer (global/project/repo) in TCS‑Vision, plus deine neuen zeitlichen Layer‑Ideen. Das lässt sich sauber kombinieren.[^2_3]

**Achse 1 – Scope (aus TCS)**

- Global (.claude): persönliche Präferenzen, cross‑project Konventionen, globale Tools.[^2_3]
- Project (HOME/Projects/<project>): Projekt‑Konventionen, gemeinsame Domain‑Modelle.[^2_3]
- Repo (.claude/memory): Codebase‑spezifische Patterns, Naming, Troubleshooting, Entscheidungen.[^2_1][^2_3]

**Achse 2 – Lifetime (dein Modell)**

- static longlived:
    - global: persönliche Daten, Arbeitsphilosophie, TDD/SDD‑Prinzipien.[^2_5][^2_2]
- longlived:
    - global + project: Tech‑Stack‑Wahl, Architektur‑Leitlinien (z.B. MiYo Architektur).[^2_2][^2_3]
- medium lived:
    - project + repo: aktuelle Architektur‑Entscheidungen, aktive Domain‑Regeln.[^2_1][^2_3]
- short lived:
    - repo: TODOs, Plans, „current focus“ im Memory; wird durch memory-cleanup und tcs-workflowspecify/implement gesteuert.[^2_5][^2_1][^2_3]
- really short lived:
    - Session‑Handover; primär Kandidat für context-mode/Kairn, nicht für Datei‑Memory.[^2_2][^2_3]

**Context-Mode / MCP-Registrar**

- context-mode‑Server reduziert Kontextverbrauch (Memory + Code) massiv, indem er nur relevante Ausschnitte liefert.[^2_2][^2_3]
- Deine Idee: einen MCP‑Registrar bauen, der:
    - context-mode als „Memory‑Server“ benutzt,
    - Ideen aus `lasso` und `airis-mcp-gateway` übernimmt (Gateway/Registrar, der Tools/Server kapselt und filtert).[^2_2]
- Designentscheid:
    - **Datei‑Memory** für Menschen + baseline AI (global/project/repo + Lifetime‑Schichten).
    - **MCP‑Memory** (context-mode/Kairn) für session‑Kontinuität + hochfrequente, wirklich kurzlebige Infos.
    - TCS selbst bleibt davon relativ entkoppelt: in CLAUDE.md definierst du nur, wie/ob der MCP‑Registrar als Tool genutzt wird.


### 4. Use-Cases und Prinzipien (Mensch + AI)

- Mensch:
    - Memory‑Bank als Docs (docs/ai/memory, project.md etc.) ist navigierbar, kann als Referenz gelesen werden.[^2_2][^2_3]
    - Aufteilung nach Scope + Lifetime verhindert Monster‑Files; MEMORY.md/Indices bleiben bei ~200 Zeilen.[^2_3][^2_2]
- AI:
    - reflect + memory-route + context-mode sorgen dafür, dass nur relevante Stücke in den Kontext gelangen, nicht alles.[^2_2][^2_3]
    - Promotion zu tcs-patterns reduziert auf Dauer die Memory‑Größe (Konzept aus Conneely).[^2_3][^2_2]


## Sources

- tcs-vision.md – Memory‑System (Layer/Kategorien, Directory‑Struktur), Modular‑CLAUDE‑Ansatz, Rolle von tcs-helpermemory.[^2_3]
- sources.md – Ableitung aus claude-reflect, centminmod, citypaul, Conneely, inkl. MEMORY.md‑Budget und Routing‑Regeln.[^2_2]
- overlap-analysis.md – TCS v2 Absorption Plan, insbesondere Memory‑Bank‑Konzept und geplante tcs-helpermemory‑Funktionen.[^2_1]
- SKILL.md – miyo-reflect als bestehender Memory‑Router, der nach reflect läuft.[^2_4]


## Recommendations

1. Struktur jetzt formalisieren (Design-Ebene, keine Implementierung)

- Schreibe eine kurze Spezifikation „TCS v2 Memory \& Context Layout“, in der du:
    - Pfade genau festlegst (global ~/.claude/includes, project ~/Kouzou/projects/<project>, repo .claude/memory vs docs/ai/memory).[^2_2][^2_3]
    - Pro Scope + Lifetime definierst, was hinein darf und was nicht (2–3 Bulletpoints je Kategorie).[^2_3][^2_2]
- Ergänze in dieser Spec auch den Reflect‑Flow:
    - `reflect` → `tcs-helper.memory-route` → (optional) `tcs-helper.memory-cleanup` → (periodisch) `tcs-helper.memory-promote`.[^2_4][^2_2][^2_3]

2. Skill-Schnittstellen für den Reflect-Prozess skizzieren

- Definiere getrennte SKILL.md‑Skeletons (ohne Implementation):
    - `tcs-helper.memory-route` (Persona = generic memory router, State = learnings + scope info).[^2_2][^2_3]
    - `tcs-helper.memory-sync` (Persona = Sync‑Manager, State = list of memory files/index).[^2_1][^2_3]
    - `tcs-helper.memory-cleanup` (Persona = Token‑Budget‑Guardian).[^2_1][^2_2]
    - `tcs-helper.memory-promote` (Persona = Pattern‑Promoter, nutzt reflect-skills).[^2_3][^2_2]

3. Context/MCP Layer nur referenzieren, noch nicht integrieren

- In CLAUDE.md und der Design‑Spec:
    - Kontext‑Minimierung per context-mode/Kairn als „optional MCP‑Layer“ erwähnen,
    - aber Implementation/Integration in einen MCP‑Registrar (lasso/airis‑Stil) explizit als „späterer Schritt“ markieren, damit TCS‑Kern unabhängig bleibt.[^2_2][^2_3]

4. Nächster konkreter Schritt

- Ich würde als nächstes eine kurze, konkrete „TCS v2 Memory \& Context Layout“-Seite mit Tabellen entwerfen (Scope × Lifetime × Pfad × Datei‑Typ), damit du sie direkt in dein Repo legen kannst und daraus CLAUDE.md/Skills generierst.[^2_3]

Willst du, dass ich dir im nächsten Schritt genau diese Tabelle + Text für die „Memory \& Context Layout“-Spec formuliere (auf Basis deiner Pfade + der TCS-Vision)?

<div align="center">⁂</div>

[^2_1]: overlap-analysis.md

[^2_2]: sources.md

[^2_3]: tcs-vision.md

[^2_4]: SKILL.md

[^2_5]: tdd-sdd-integration.md


---

# hier ist noch einmal wie claude memory funktioniert.. https://code.claude.com/docs/en/memory

schreibe mir doch bitte einen rohentwurf für die spezifikation, integrieren context/mcp layer
die context skills müssen halt einmal mit dem "normalen" context server und wenn installiert mit dem kairn server arbeiten

Summary
Ich schreibe dir einen Rohentwurf für eine „TCS v2 Memory \& Context Layout“-Spec, die Claude‑Memory (CLAUDE.md + Auto‑Memory), dein 3‑Layer‑Modell (global/project/repo), die Lifetime‑Layer und einen optionalen Context/MCP‑Layer (context-mode + Kairn) integriert.[^3_1][^3_2][^3_3][^3_4][^3_5][^3_6]

***

## 1. Zweck und Ziele

- Ziel: Einheitliches Design für **CLAUDE.md**, Memory‑Bank und Context‑Layer, das
    - mit Claude Codes bestehendem Memory‑System kompatibel ist (CLAUDE.md, Auto‑Memory, rekursive Discovery),[^3_7][^3_4]
    - TCS‑Vision (3 Layer, progressive disclosure) respektiert,[^3_2]
    - und optional einen Context/MCP‑Layer (context-mode, Kairn) nutzen kann, ohne TCS hart daran zu koppeln.[^3_5][^3_6]

***

## 2. Scopes, Pfade und Discovery

### 2.1 Scopes

Wir unterscheiden drei inhaltliche Scopes (TCS) und mappen sie auf Claude Codes Filesystem‑Verhalten.[^3_4][^3_2]

- **Global Scope (User)**
    - Speicherort: `~/.claude/`.[^3_4]
    - Dateien:
        - `~/.claude/CLAUDE.md` – globale Präferenzen, Arbeitsphilosophie, universelle Prinzipien.[^3_1][^3_2][^3_4]
        - `~/.claude/includes/*.md` – lazy‑Load Dateien (z.B. `memory-general.md`, `memory-tools.md`).[^3_2]
- **Project Scope**
    - Root: `~/Kouzou/projects/<project>/`.
    - Dateien/Dirs:
        - `PROJECT.md` (oder `project.md`) – Projektbeschreibung, Ziele, konzeptionelle Domain‑Infos.[^3_2]
        - `.claude/CLAUDE.project.md` – Projekt‑Routing‑Regeln, z.B. wohin Projekt‑Konventionen und Workflows gehen.[^3_2]
        - `docs/ai/project-memory/` (oder `memory/`) – projektweite Memory‑Docs, lazy geladen per Referenz.[^3_1][^3_2]
- **Repo Scope**
    - Root: Git‑Repo.
    - Dateien/Dirs:
        - `.claude/CLAUDE.md` – Repo‑Anweisungen, Memory‑Routing für dieses Repo.[^3_4][^3_2]
        - `.claude/memory/` oder `docs/ai/memory/`:
            - `general.md`, `tools.md`, `domain.md`, `context.md`, `troubleshooting.md`, `decisions.md`.[^3_8][^3_2]
        - Optionale Verzeichnis‑CLAUDEs: `src/CLAUDE.md`, `docs/CLAUDE.md`, `tst/obsidian-testvault/CLAUDE.md` – gelten nur, wenn in diesem Verzeichnis gearbeitet wird (Claude Codes rekursive Discovery).[^3_9][^3_4]


### 2.2 Discovery-Verhalten (Claude Code)

- Claude Code liest `CLAUDE.md` und `CLAUDE.local.md` rekursiv von current working directory nach oben (bis `/`).[^3_9][^3_4]
- `CLAUDE.md` in Unterverzeichnissen werden nur geladen, wenn man dort arbeitet – genau dein gewünschtes „lazy loading durch Pfad“.[^3_4]
- `~/.claude/CLAUDE.md` wird global eingemischt, wenn man unter dem Home‑Pfad arbeitet.[^3_4]

***

## 3. Memory-Achsen: Scope × Lifetime

Wir kombinieren TCS‑Scopes mit deinen Lifetime‑Kategorien.[^3_2]

### 3.1 Lifetime-Definitionen

- **Static longlived**
    - praktisch unveränderlich (Identität, Grundprinzipien, „How I work“).
- **Longlived**
    - seltene Änderungen (Tech‑Stack, Architektur‑Leitplanken, TDD/SDD‑Prinzipien).[^3_10][^3_1]
- **Medium lived**
    - repo-/projektbezogene Regeln, die sich bei Releases/Refactors ändern (Domainmodell, konkrete Patterns, Entscheidungen).[^3_8][^3_2]
- **Short lived**
    - TODOs, Plans, aktuelle Troubleshooting‑Notizen.[^3_8][^3_2]
- **Really short lived**
    - Session‑Handover, temporäre Arbeitskontexte (was war im letzten Prompt, aktive Tasks etc.).[^3_3][^3_6]


### 3.2 Zuordnung (Beispiele)

| Scope | Lifetime | Beispiele | Speicherort |
| :-- | :-- | :-- | :-- |
| Global | static longlived | persönliche Werte, Kommunikationsstil | `~/.claude/CLAUDE.md`, `includes/memory-general.md`[^3_1][^3_2][^3_4] |
| Global | longlived | bevorzugte Tools, globale TDD/SDD‑Prinzipien | `includes/memory-tools.md`, global patterns‑Docs[^3_1][^3_10] |
| Project | longlived/medium | Projekt‑Ziele, Domain‑Boundaries, Governance | `PROJECT.md`, `.claude/CLAUDE.project.md`, `docs/ai/project-memory/*.md`[^3_2] |
| Repo | medium lived | Repo‑Patterns, Naming, Arch‑Entscheidungen | `.claude/memory/{general,domain,decisions}.md`[^3_8][^3_2] |
| Repo | short lived | TODOs, Plans, aktuelle Bugs | `.claude/memory/context.md`, `troubleshooting.md`[^3_8][^3_2] |
| Session | really short lived | Session Guide, Task State | context-mode/Kairn DB (MCP), nicht in Filesystem[^3_3][^3_6][^3_5] |


***

## 4. Reflect- \& Memory-Prozess

### 4.1 Claude Code: Auto Memory und Manual Memory

- Claude kann Memory sowohl über Files (CLAUDE.md / Auto‑Memory‑Files) als auch über ein Memory‑Tool (/memories‑Dir) verwalten.[^3_3][^3_7]
- TCS nutzt die **File‑Variante** plus reflect‑Plugin:
    - `claude-reflect` Plugin: erfasst Korrekturen/Feedback, schreibt in entsprechende Memory‑Files (global/project/local).[^3_1]


### 4.2 TCS-Erweiterung: Mehrere spezialisierte Skills

Statt einem Mega‑Skill definieren wir eine Pipeline:

1. **tcs-helper.memory-route**
    - Input: reflect‑Output (Learnings) + Pfad/Scope Info.
    - Aufgabe:
        - Mappt Learnings auf `.claude/memory/{general,tools,domain,context,troubleshooting,decisions}.md` im Repo, plus ggf. Projekt‑Memory.[^3_8][^3_2]
        - Orientiert sich an miyo-reflect Workflow, ersetzt MiYo‑Spezifika durch generische Routing‑Regeln.[^3_11][^3_1]
2. **tcs-helper.memory-sync**
    - Aufgabe:
        - Stellt sicher, dass Projekt‑/Repo‑CLAUDE die relevanten Memory‑Files über kurze „Index/Import“-Hinweise referenzieren (keine Vollimporte).[^3_1][^3_2]
        - Hält `MEMORY.md`‑Index pro Repo/Projekt bei ~200 Zeilen (Conneely‑Regel: Index statt Volltext).[^3_1][^3_2]
3. **tcs-helper.memory-cleanup**
    - Aufgabe:
        - Wendet Token‑Budget‑Regeln aus centminmod an: resolved Troubleshooting/Epics archivieren, Duplikate entfernen, alte TODOs markieren.[^3_8][^3_1]
4. **tcs-helper.memory-promote**
    - Aufgabe:
        - Nutzt intern `reflect-skills` (oder ähnliches) und scannt `.claude/memory/domain.md` auf wiederkehrende Patterns.[^3_2][^3_1]
        - Schlägt Skills in `tcs-patterns/*` vor und ersetzt längere Memory‑Einträge durch Pointer („see tcs-patterns/hexagonal“).[^3_1][^3_2]

**Flow in Worten:**

- Nach einer Session oder vor Context‑Compaction:
    - `reflect` → `tcs-helper.memory-route` → optional `memory-cleanup` → periodisch `memory-promote`.[^3_11][^3_2][^3_1]

***

## 5. Context- und MCP-Layer

### 5.1 Ziele des Context-Layers

- Kontextfenster klein halten, ohne Information zu verlieren.[^3_6][^3_12]
- Session‑Kontinuität, auch wenn Claude‑Context kompaktet oder neue Sessions starten.[^3_6][^3_3]
- Flexibel:
    - läuft nur mit Standard‑Context‑Server,
    - nutzt Kairn als Upgrade, falls installiert.[^3_13][^3_5]


### 5.2 Context-Mode (Standard Context MCP)

- context-mode trackt pro Projekt: File‑Edits, Git‑Ops, Tasks, Errors, Entscheidungen in einer SQLite DB und generiert vor Context‑Compaction eine ≤2KB „Session Guide“.[^3_12][^3_6]
- Reduziert Kontext um ~98%, indem es nur relevante, deduplizierte Auszüge zurückgibt.[^3_12][^3_6]

In TCS‑Design:

- context-mode ist **Option**, aber erste Wahl für „normalen“ Context‑Server.
- TCS‑Skills, die auf Kontext bauen (z.B. `tcs-workflow.analyze`, `debug`) sollten:
    - zuerst versuchen, eine Session‑Zusammenfassung via context-mode zu holen,
    - dann bei Nicht‑Verfügbarkeit auf Files (Memory‑Docs + Code) zurückfallen.[^3_6][^3_2]


### 5.3 Kairn (Semantic Memory Upgrade)

- Kairn bietet graph‑basiertes, semantisches Memory über Projekte hinweg („How did I solve auth?“), als Upgrade auf context/evolving‑Lite Layer.[^3_14][^3_5][^3_13]
- TCS soll **nicht** von Kairn abhängen, aber Kairn nutzen können, wenn vorhanden.

Design:

- Context‑Abstraktion in TCS als „Context Server Interface“:
    - **Default**: context-mode (Standard‑Context).
    - **Wenn `kairn` installiert**:
        - TCS‑Context‑Skills (z.B. `tcs-helper.context-search`) fragen Kairn mit semantischen Queries (z.B. „auth bug fix in this repo“),
        - context-mode kann sich dann auf raw Tool‑Outputs konzentrieren, Kairn auf „semantische Sessions“.[^3_5][^3_13]


### 5.4 Kontextfluss im Zusammenspiel

1. Während der Arbeit:
    - context-mode zeichnet Tool‑Output, Fehler, Kommandos auf.[^3_6]
2. Wenn Kontext groß wird oder Session endet:
    - Claude schreibt Zusammenfassung in Memory‑Files (per Memory‑Tool oder reflect + tcs-helper.memory‑Flow),[^3_3][^3_1]
    - context-mode erzeugt Session Guide + Index in DB.[^3_6]
3. In einer neuen Session:
    - Claude lädt CLAUDE.md/Memory‑Files (langfrist-/mittel‑lebige Fakten).[^3_4][^3_2]
    - Context‑Skills holen Session‑Kontext via context-mode (und Kairn, falls vorhanden).[^3_13][^3_5][^3_6]

***

## 6. Richtlinien für Inhalte (Was geht wohin?)

Aus sources/TCS‑Vision abgeleitet.[^3_2][^3_1]

- **CLAUDE.md / CLAUDE.project / Verzeichnis‑CLAUDE**
    - Regeln, Prinzipien, Workflows.
    - Routing‑Regeln, wann welche Memory/Context‑Skills laufen.
    - Keine langen Listen, keine detaillierte Historie → dafür Memory‑Docs/DB.[^3_1][^3_2]
- **Memory-Docs (general/tools/domain/...)**
    - Fakten, die du oder das Team später gezielt nachlesen wollt (Patterns, Entscheidungen, Troubleshooting‑Rezepte).[^3_8][^3_2]
    - Medium/short lived, menschenlesbar und git‑versioniert.
- **Context-DB (context-mode / Kairn)**
    - alles, was sehr kurzlebig ist oder sehr umfangreich (Raw‑Tool‑Output, Logs, Zwischenzustände), aber später semantisch gesucht werden soll.[^3_5][^3_6]
    - Primär für AI, nicht als Haupt‑Human‑Interface gedacht (optional Web‑UI wie bei manchen Memory‑Plugins).[^3_15][^3_5]

***

## 7. Offene Punkte / spätere Entscheidungen

- Exakte Verzeichnisnamen: `docs/ai/memory` vs `.claude/memory` vs `memory/` – in einer ADR fixieren.[^3_2]
- Context‑Server‑Discovery: wie TCS erkennt, ob context-mode und/oder Kairn installiert sind (z.B. via Tool‑Availability).[^3_5][^3_6]
- Konkretes Interface von `tcs-helper.context-*` Skills (State, Modes) – nach erstem Prototypen von memory‑Flow definieren.[^3_2]

***

Wenn du magst, kann ich dir als nächsten Schritt ein konkretes Markdown‑Dokument im Stil deiner vorhandenen TCS‑Docs schreiben („TITLE …“, Tabellen etc.), das du direkt als `tcs-memory-and-context-layout.md` ins Repo legen kannst.
<span style="display:none">[^3_16][^3_17][^3_18][^3_19][^3_20][^3_21][^3_22][^3_23][^3_24][^3_25][^3_26][^3_27][^3_28][^3_29][^3_30][^3_31][^3_32][^3_33]</span>

<div align="center">⁂</div>

[^3_1]: sources.md

[^3_2]: tcs-vision.md

[^3_3]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

[^3_4]: https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with

[^3_5]: https://primeline.cc

[^3_6]: https://newreleases.io/project/github/mksglu/context-mode/release/v1.0.0

[^3_7]: https://www.youtube.com/watch?v=FRwZg6VOjvQ

[^3_8]: overlap-analysis.md

[^3_9]: https://github.com/anthropics/claude-code/issues/722

[^3_10]: tdd-sdd-integration.md

[^3_11]: SKILL.md

[^3_12]: https://x.com/mksglu/status/2027803127898911186

[^3_13]: https://github.com/primeline-ai/evolving-lite

[^3_14]: https://github.com/primeline-ai

[^3_15]: https://github.com/thedotmack/claude-mem

[^3_16]: https://github.com/anthropics/claude-code/issues/14227

[^3_17]: https://github.com/christian-byrne/claude-code-vector-memory

[^3_18]: https://github.com/anthropics/claude-code/issues/2670

[^3_19]: https://github.com/anthropics/claude-code/issues/2274

[^3_20]: https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13597457310

[^3_21]: https://github.com/matthewrobertbell/mkcontext

[^3_22]: https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13446167257/workflow

[^3_23]: http://github.com/modelcontextprotocol/modelcontextprotocol/actions

[^3_24]: https://github.com/hesreallyhim/awesome-claude-code/issues/167

[^3_25]: https://github.com/PrimeIntellect-ai/prime-cli/actions

[^3_26]: https://github.com/mksglu

[^3_27]: https://github.com/NikiforovAll/claude-code-rules

[^3_28]: https://github.com/PrimeIntellect-ai/prime-cli/actions/runs/13505020631/workflow

[^3_29]: https://docs.basicmemory.com/integrations/claude-code

[^3_30]: https://joseparreogarcia.substack.com/p/claude-code-memory-explained

[^3_31]: https://github.com/primeline-ai/universal-planning-framework

[^3_32]: https://www.youtube.com/watch?v=e1F7zUWRm3w

[^3_33]: https://lobehub.com/ja/skills/hlibkoval-claudemd-memory-doc


---

# erstelle mir doch bitte eine neue sources.md nach dem originalen vorbild

Summary
Ich entwerfe dir eine neue `sources.md`, die sich in Struktur und Stil eng an dein bestehendes TCS‑v2‑Vorbild anlehnt (TITLE‑Blöcke, „What we use“-Listen, klare Attribution), aber den neuen Fokus auf Memory \& Context (context-mode, Kairn, lasso, airis, Claude‑Memory‑Docs) integriert.[^4_1][^4_2][^4_3][^4_4][^4_5][^4_6]

***

## Findings

### Rohentwurf `sources.md`

```markdown
This document lists all external sources analyzed and drawn from in the TCS v2 Memory & Context design. 
Maintained for reference and attribution when publishing changes.

---

TITLE TCS v2 Memory & Context Sources Attribution - claude-reflect marketplace plugin

Plugin claude-reflect installed via Claude Code marketplace
Repository https://github.com/claude-reflect-marketplace/claude-reflect
Version used 3.0.1

What we use
- reflect two-stage self-learning hooks capture corrections, queue routed to CLAUDE.md destinations.
  Foundation for tcs-helper.memory-route capture layer.
- Learning destinations model global CLAUDE.md, project CLAUDE.md, CLAUDE.local.md, rules.md, auto-memory.
  Direct input for the TCS gpr (global/project/repo) routing table.
- reflect-skills AI-powered session analysis that identifies repeating patterns and generates skill files.
  Promotion mechanism for Conneely-style staging → promotion → pointer lifecycle.
  Used as organic growth engine for tcs-patterns via tcs-helper.memory-promote.
- miyo-reflect extension pattern proof that reflect can be extended with repo-specific routing.
  Architectural template for repo-layer routing in tcs-helper.memory-route.

---

TITLE TCS v2 Memory & Context Sources Attribution - Claude Code Memory Docs

Docs https://code.claude.com/docs/en/memory
Supplementary resources
- https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with
- https://joseparreogarcia.substack.com/p/claude-code-memory-explained

What we use
- CLAUDE.md discovery rules directory-level files loaded recursively towards repo root.
  Confirms design choice for per-directory CLAUDE.md (e.g. src/CLAUDE.md, docs/CLAUDE.md) as natural lazy-loading boundary.
- Global CLAUDE.md in ~/.claude as always-on user scope.
  Basis für static longlived and longlived memory at global scope.
- Auto Memory and memory-tool concepts inform separation between human-readable file memory
  and tool-driven context databases (context-mode, Kairn).
- Guidance on keeping CLAUDE.md lean and delegating detail to referenced documents.
  Aligns with TCS progressive disclosure philosophy.

---

TITLE TCS v2 Memory & Context Sources Attribution - John Conneely Memory System

Article https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory
Author John Conneely

What we use
- Memory category taxonomy general conventions, tools integrations, domain topic knowledge.
  Applied across TCS scopes (global, project, repo) instead of one global bucket.
- MEMORY.md as index-only document with ~200-line budget.
  Adopted as design constraint for project/repo MEMORY indices in TCS.
- Routing rules belong in CLAUDE.md, not in MEMORY.md.
  Directly informs decision to keep routing logic in CLAUDE.md / CLAUDE.project.md.
- PreToolUse hook pattern for injecting memory before tool calls.
  Inspiration for tcs-helper.context-* skills, which consult context servers before expensive operations.
- Practical result: reducing CLAUDE.md from ~189 to ~63 lines by moving content into typed memory files.
  Serves as benchmark for TCS modular CLAUDE.md approach.

Key divergence
- Conneely keeps all categories at global scope.
  TCS distributes categories across global (general/tools), project (project-domain), and repo (codebase-domain, troubleshooting).

---

TITLE TCS v2 Memory & Context Sources Attribution - centminmod/my-claude-code-setup

Repository https://github.com/centminmod/my-claude-code-setup
Author centminmod
License Check repo for current license

What we use
- Memory bank architecture per-concern CLAUDE-*.md files
  (activeContext, patterns, decisions, troubleshooting).
  Basis for repo-level typed memory directory (.claude/memory or docs/ai/memory).
- Cleanup-context workflow token reduction, archive resolved issues.
  Forms the core of tcs-helper.memory-cleanup modes.
- Memory bank synchronizer agent and preservation rules
  (never delete todos/roadmaps, only update technical accuracy).
  Informs design for tcs-helper.memory-sync.
- CLAUDE.md tech-stack templates (Cloudflare Workers, Convex) in docs/templates.
  Pattern reused in tcs-helper.setup for stack-aware CLAUDE.md generation.

---

TITLE TCS v2 Memory & Context Sources Attribution - citypaul/dotfiles

Repository https://github.com/citypaul/dotfiles
Author Paul Dobbins (citypaul)
License Check repo for current license

What we use
- Philosophy-first CLAUDE.md approach v3.0.0 (~100 lines core, skills on demand).
  Core justification for keeping all CLAUDE.md files lean and delegating detail to skills and memory docs.
- Domain skill libraries (DDD, hexagonal-architecture, functional, typescript-strict, mutation-testing,
  frontend-testing, react-testing, twelve-factor).
  Underpin TCS tcs-patterns plugin as domain knowledge library.
- setup command concept to detect stack and generate CLAUDE.md + hooks + agents.
  Direct inspiration for tcs-helper.setup.
- Expectations about TDD discipline, PR evidence, and plan formats.
  Integrated into tcs-workflow.tdd, tcs-workflow.specify-plan, and tcs-workflow.implement.

---

TITLE TCS v2 Memory & Context Sources Attribution - obrasuperpowers

Repository https://github.com/obrasuperpowers
Author Jesse Vincent (obra)
License Check repo for current license

What we use
- TDD skill RED-GREEN-REFACTOR iron law and rejected-rationalizations table.
  Embedded into tcs-workflow.tdd and TDD/SDD integration documents.
- Verification-before-completion discipline (evidence-before-claims).
  Implemented as tcs-workflow.verify gate.
- Receiving-code-review rigor pattern.
  Forms the basis of tcs-workflow.receive-review.
- Dispatching-parallel-agents patterns.
  Absorbed into tcs-workflow.parallel-agents for explicit parallel dispatch.
- Systematic-debugging anti-shortcut rules.
  Strengthen tcs-workflow.debug and inform what belongs in troubleshooting memory.

---

TITLE TCS v2 Memory & Context Sources Attribution - context-mode

Repository https://github.com/mksglu/context-mode
Author mksglu
Release reference v1.0.0

What we use
- MCP server that captures raw tool outputs, errors, and edits in a structured context database,
  then serves compact, task-relevant summaries back to Claude.
  Basis for the TCS Context Server abstraction.
- Reported 90–98% reduction in Claude Code context usage by moving history out of the context window
  and into a dedicated context store.
  Motivates offloading really short lived session data to context servers instead of file memory.
- Design of a single context-mode server fronting many tools.
  Informs TCS plan for a context/MCP registrar that can proxy multiple MCP servers.

How TCS uses it
- Default implementation for "normal" context server behind tcs-helper.context-* skills.
- Session continuity for task-level history and recent operations, complementary to file-based memory.

---

TITLE TCS v2 Memory & Context Sources Attribution - lasso-security/mcp-gateway

Repository https://github.com/lasso-security/mcp-gateway
Author Lasso Security
License Check repo for current license

What we use
- Gateway MCP that composes multiple downstream MCP servers and applies policy/filter rules.
  Provides reference architecture for a TCS context registrar/gateway.
- Plugin-based extension model.
  Serves as conceptual model for registering multiple context sources (context-mode, Kairn, others).

---

TITLE TCS v2 Memory & Context Sources Attribution - agiletec-inc/airis-mcp-gateway

Repository https://github.com/agiletec-inc/airis-mcp-gateway
Author Agiletec Inc
License Check repo for current license

What we use
- Alternate gateway design that routes and filters MCP traffic through a central orchestrator.
  Cross-checks and validates ideas from lasso-security/mcp-gateway for TCS gateway design.
- Pattern of exposing a single entrypoint to many tools/services.
  Aligns with TCS goal to present a small, curated tool surface to Claude.

---

TITLE TCS v2 Memory & Context Sources Attribution - PrimeLine / Kairn & related projects

Organization https://github.com/primeline-ai
Product page https://primeline.cc
Representative repo https://github.com/primeline-ai/evolving-lite

What we use
- Kairn-style semantic project memory and session continuity as an optional upgrade over raw context logs.
  Guides TCS decision to keep an abstract Context Server interface that can work with context-mode only,
  or context-mode plus Kairn.
- Graph- and embedding-based retrieval for "How did I fix this before?" queries.
  Inspiration for future tcs-helper.context-search skills that can call semantic context servers when available.
- Separation between human-facing docs and AI-first context stores.
  Mirrors TCS split between file-based memory banks and MCP-based context databases.

Note
- Kairn is treated as an optional integration, not a hard dependency for TCS.
  All core workflows must still function with file memory + context-mode only.

---

TITLE TCS v2 Memory & Context Sources Attribution - Claude Code Memory Community Guides

Resources
- https://www.youtube.com/watch?v=e1F7zUWRm3w ("Claude Code Memory: The File That Changes Everything")
- https://www.youtube.com/watch?v=FRwZg6VOjvQ ("Claude Code's Memory System: The Full Guide")
- https://github.com/NikiforovAll/claude-code-rules
- Various community issues documenting CLAUDE.md discovery and memory behaviour in Claude Code

What we use
- Practical patterns for structuring CLAUDE.md (short core, references to focused documents).
  Reinforce the progressive disclosure approach in TCS.
- Edge cases around CLAUDE.md discovery (per-directory files, global files, inconsistent documentation).
  Inform defensive design for where TCS places CLAUDE.md and how it documents discovery rules.
- Example rulesets for making memory behaviour explicit.
  Provide ideas for how TCS can document its own CLAUDE.md and memory-bank rules.

---

TITLE TCS v2 Memory & Context Sources Attribution - TCS Upstream Baseline

Repository https://github.com/MMoMM-org/the-custom-startup
Origin upstream the-startup framework

What we use
- Full spec pipeline PRD → SDD → PLAN via specify.
- Agent team library tcs-team, 15+ agents.
- Phase orchestration with drift detection in implement.
- Constitution enforcement via validate and CONSTITUTION.md.
- Existing tcs-helper.skill-author and statusline scripts.
  All extended but not replaced by the new Memory & Context design.
```


***

## Sources

- Deine bestehende `sources.md` für Struktur, Sprachstil und Attribution („TITLE …“, „What we use“, Upstream‑Block).[^4_1]
- `tcs-vision.md` für Memory‑System, Plugins, progressive disclosure und die Position von tcs-helper.memory/tcs-patterns.[^4_2]
- Kontext‑Mode Release/Docs und Diskussionen zu Context‑Reduktion als MCP‑Server.[^4_3][^4_7]
- PrimeLine/Kairn Repos und Seite für semantisches Projekt‑Memory und Session‑Kontinuität.[^4_4][^4_8][^4_9]
- Community‑Guides zu Claude Code Memory und CLAUDE.md‑Discovery.[^4_5][^4_6][^4_10][^4_11]

***

Recommendations

- Nimm den Rohentwurf, passe bei Bedarf Namen der TCS‑Skills an (z.B. ob du `tcs-helper.memory-route` genau so nennen willst).
- Ergänze später weitere Quellen (z.B. spezifische Kairn‑Repo‑Links), sobald du sie konkret einsetzt.

Willst du als nächstes eine passende „TCS v2 Memory \& Context Layout“-Seite im gleichen Stil (TITLE‑Blöcke + Tabellen), die direkt auf diese neue `sources.md` referenziert?
<span style="display:none">[^4_12][^4_13][^4_14]</span>

<div align="center">⁂</div>

[^4_1]: sources.md

[^4_2]: tcs-vision.md

[^4_3]: https://newreleases.io/project/github/mksglu/context-mode/release/v1.0.0

[^4_4]: https://primeline.cc

[^4_5]: https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with

[^4_6]: https://joseparreogarcia.substack.com/p/claude-code-memory-explained

[^4_7]: https://x.com/mksglu/status/2027803127898911186

[^4_8]: https://github.com/primeline-ai

[^4_9]: https://github.com/primeline-ai/evolving-lite

[^4_10]: https://www.youtube.com/watch?v=e1F7zUWRm3w

[^4_11]: https://github.com/anthropics/claude-code/issues/722

[^4_12]: overlap-analysis.md

[^4_13]: tdd-sdd-integration.md

[^4_14]: SKILL.md


---

# kannst du mir bitte auch noch den MCP Server zusammen fassen?

Also die Änderungen am context-mode MCP server damit er:

- als MCP Server Gateway / Registry funktioniert
- als MCP Server Security Scanner funktioniert
- und neu, damit KAIRN in dem MCP Server registriert werden kann und dann anstelle der internen Context Database für die entsprechenden informationen genutzt wird.

Summary
Der MCP‑Teil von deinem Design besteht aus einem erweiterten context-mode‑Server, der drei Rollen übernimmt: Gateway/Registry für andere MCP‑Server, Security‑Scanner für deren Konfiguration und optionaler Adapter, um Kairn als externes Projekt‑Gedächtnis anstelle der internen context-mode‑DB für bestimmte Daten zu nutzen.[^5_1][^5_2][^5_3][^5_4][^5_5][^5_6][^5_7]

***

## Findings

### 1. Ausgangspunkt: context-mode heute

- context-mode ist ein MCP‑Server, der alle Tool‑Calls abfängt, deren Output in eine per‑Projekt SQLite‑FTS5‑DB indexiert und nur verdichtete, relevante Ausschnitte an Claude zurückgibt.[^5_2][^5_3][^5_8][^5_9][^5_10]
- Er sitzt zwischen Agent und Tools, kapselt subprocess‑Ausführung, speichert Session‑Events, und ermöglicht spätere gezielte Queries anstatt rohe Outputs ins Kontextfenster zu kippen.[^5_3][^5_11][^5_12]

Das ist deine Basis für: „normaler“ Context‑Server, Session‑Kontinuität und Kontext‑Reduktion.

***

### 2. Erweiterung 1: MCP Server Gateway / Registry

Ziel: context-mode soll mehrere nachgelagerte MCP‑Server bündeln und für Claude wie ein einziger Server erscheinen, ähnlich wie lasso‑mcp‑gateway.[^5_4][^5_7][^5_1]

**Konzeptuell:**

- context-mode Gateway‑Layer:
    - Frontend: ein MCP‑Endpoint, den Claude Code als „context-mode“ anspricht.
    - Backend: Registry von MCP‑Servern (filesystem, github, basic-memory, kairn, etc.), die per STDIO/HTTP eingebunden sind.[^5_13][^5_11][^5_2][^5_3]
- Funktionen der Registry:
    - Laden der Serverdefinitionen aus einer Konfig (z.B. `~/.context-mode/mcp.json` oder `~/.mcp/context-mode.json`).

```
- Dynamische Capability‑Registrierung: Tools der down‑stream MCPs werden als `<server>_<tool>` oder via Namespacing exponiert, ähnlich der Dynamic Capability Registration im lasso‑Gateway.[^5_1]
```

    - Routing: context-mode entscheidet anhand des Toolnamens / Namespaces, an welchen Server der Aufruf geht.[^5_7][^5_1]

Damit hast du:

- Einen einzigen MCP‑Entry in Claude Code, der intern viele Servers orchestriert.
- Einen klaren Ort (context-mode) für spätere Security‑Filter und Policies.

***

### 3. Erweiterung 2: Security Scanner im Gateway

Ziel: context-mode soll vor dem Laden/Expose von MCP‑Servern deren Risiko prüfen und Konfiguration entsprechend markieren/blocken, angelehnt an lasso‑mcp‑gateway‑Scanner.[^5_6][^5_4][^5_7][^5_1]

**Bausteine:**

- **Scan‑Zeitpunkt:**
    - Beim Start von context-mode (oder wenn Konfig sich ändert) wird jede MCP‑Server‑Definition gescannt.[^5_1]
- **Analyse‑Dimensionen:**
    - Reputation: GitHub‑Infos, Stars, ggf. Marketplace‑Einträge, wenn verfügbar (ähnlich lasso‑Reputation Analysis).[^5_4][^5_1]
    - Tool‑Beschreibungen: Pattern‑Scan auf sensible Aktionen (delete, exfiltrate, network‑calls, secrets‑read etc.), hidden instructions, riskante File‑Pfade.[^5_7][^5_1]
    - Konfiguration: Ports, Pfade, Shell‑Kommandos – potentielle Injection‑Punkte.[^5_3][^5_7]
- **Ergebnis \& Policy:**
    - Score + Status pro Server: `passed`, `blocked`, `skipped`, `pending` – analog zur lasso‑Gateway‑Konfiguration.[^5_1]
    - Gate im Gateway: Tools eines `blocked` Servers werden nicht registriert bzw. sind für Claude unsichtbar.[^5_7][^5_1]
    - Logging: Audit‑Log (z.B. `~/.context-mode/scanner.log`) mit Begründungen, wie beim lasso‑Scanner.[^5_4][^5_1]

Damit verhält sich context-mode nicht nur als Kontext‑Optimierer, sondern auch als Sicherheitslayer für alle Tools, die du über TCS/TCS‑Plugins nutzt.

***

### 4. Erweiterung 3: Kairn-Integration als externer Context Store

Ziel: Kairn soll als persistentes, graphbasiertes Projekt‑Gedächtnis fungieren und für bestimmte „Memory‑/Context‑Anfragen“ statt der internen context-mode‑SQLite‑DB genutzt werden.[^5_5][^5_14][^5_15]

**Kairn-Fähigkeiten (aus Evolving‑Lite/Kairn):**

- Hält einen Knowledge‑Graph mit Projekten, Entscheidungen, „Experiences“, der beim Boot in Sekunden geladen wird.[^5_14][^5_5]
- Unterstützt semantische Queries à la „Wie habe ich Auth‑Bug XY gelöst?“ statt reinem Text‑FTS.[^5_5][^5_14]
- Baut sich durch kontinuierliches Lernen aus Code‑Fixes und Entscheidungen selbst weiter auf.[^5_14][^5_5]

**Design im context-mode‑Gateway:**

- context-mode bleibt Default‑Context‑Server:
    - Interne SQLite‑DB trackt Tool‑Outputs, Logs, Session‑Events.[^5_3]
- Wenn Kairn als MCP‑Server registriert ist (z.B. `kairn` mit Tools `kairn_query`, `kairn_learn`):[^5_15][^5_5][^5_14]
    - Gateway markiert Kairn als „Semantic Memory Provider“ im Registry‑State.
    - Bestimmte Kontext‑Skills oder Tools werden auf Kairn geroutet:
        - „project‑level knowledge“ → Kairn.
        - „raw tool output recall / logs“ → context-mode SQLite.[^5_5][^5_3]
- Praktische Regeln (Beispiele):
    - `context_search_recent_output` → context-mode interne DB.
    - `context_search_decision_graph` oder `context_search_past_solution` → Kairn‑Tool.[^5_14][^5_3][^5_5]
    - Beim Session‑Start kann context-mode optional einen „Bootup Context“ von Kairn holen (Graph‑Snapshot) und als condensed Summary an Claude liefern – wie im Evolving‑Lite Demo.[^5_5][^5_14]

Kurz: context-mode bleibt für „raw context reduction“ zuständig, Kairn übernimmt „semantisches Knowledge‑Graph‑Memory“, sobald verfügbar.

***

## Recommendations

Konkret für dein Design:

- Definiere in deiner TCS‑Spec drei Schichten im MCP‑Teil:

1. **Context-Server‑Abstraktion** (für TCS‑Skills): TCS sieht nur „Context‑Server“, nicht, ob intern SQLite oder Kairn genutzt wird.
2. **context-mode Gateway** als Default‑Implementation mit Registry + Security‑Scanner.
3. **Optionale Kairn‑Integration**: Wenn `kairn` registriert ist, werden bestimmte Kontext‑Queries umgeleitet.
- In CLAUDE.md (global/projekt/repo) beschreibst du nur:
    - „Nutze Context‑Server für Session‑Kontext; falls Kairn vorhanden, nutze es für Projekt‑Wissen.“
    - Alle Details (Registrierung, Security‑Scanning) leben im MCP‑Server und seiner Config.

Wenn du möchtest, kann ich daraus im nächsten Schritt eine „TCS MCP Context Server Design“-Seite im gleichen TITLE‑/TABLE‑Stil wie deine anderen Docs schreiben, inkl. Abschnitt für Registry, Security‑Scanner und Kairn‑Mode.
<span style="display:none">[^5_16][^5_17][^5_18][^5_19][^5_20][^5_21][^5_22][^5_23][^5_24][^5_25][^5_26][^5_27][^5_28][^5_29][^5_30][^5_31][^5_32][^5_33][^5_34][^5_35]</span>

<div align="center">⁂</div>

[^5_1]: https://github.com/lasso-security/mcp-gateway/releases

[^5_2]: https://github.com/mksglu/context-mode

[^5_3]: https://betterstack.com/community/guides/ai/context-mode-mcp/

[^5_4]: https://www.lasso.security/resources/lasso-releases-first-open-source-security-gateway-for-mcp

[^5_5]: https://primeline.cc/blog/persistent-memory-evolving-lite

[^5_6]: https://www.lasso.security/blog/why-mcp-agents-are-the-next-cyber-battleground

[^5_7]: https://www.lasso.security/use-cases/mcp

[^5_8]: https://www.linkedin.com/pulse/stop-burning-your-context-window-we-built-mode-mert-koseoglu-c04nf

[^5_9]: https://www.linkedin.com/posts/mksglu_github-mksgluclaude-context-mode-activity-7431589485726814208-Ft9w

[^5_10]: https://news.ycombinator.com/item?id=47193064

[^5_11]: https://cultofclaude.com/skills/claude-context-mode/

[^5_12]: https://skills-rank.com/skill/mksglu/context-mode/context-mode

[^5_13]: https://github.com/mcp-s-ai/secure-mcp-gateway

[^5_14]: https://www.youtube.com/watch?v=mR6Ss6Tnzm4

[^5_15]: https://primeline.cc

[^5_16]: overlap-analysis.md

[^5_17]: sources.md

[^5_18]: tcs-vision.md

[^5_19]: tdd-sdd-integration.md

[^5_20]: SKILL.md

[^5_21]: https://github.com/mksglu

[^5_22]: https://github.com/Illumina/canvas

[^5_23]: https://gist.github.com/donn/0c501ab625625c381fdf3210bf0ff275

[^5_24]: https://github.com/mik3y/usb-serial-for-android

[^5_25]: https://github.com/vllm-project/vllm-project.github.io/activity

[^5_26]: https://github.com/siderolabs/talos

[^5_27]: https://github.com/sickcodes/Docker-OSX/issues/647

[^5_28]: https://github.com/ggcr/Super-Temporal-LIIF

[^5_29]: https://github.com/AnarchyLinux/installer/issues/103

[^5_30]: https://github.com/lasso-security/mcp-gateway/activity

[^5_31]: https://github.com/libfuse/libfuse/issues/382

[^5_32]: https://github.com/facebook/react-native/blob/055c941c4045468af4ff2b8162d3a35dd993b1b9/Libraries/vendor/emitter/EventEmitter.js

[^5_33]: https://github.com/lasso-security/mcp-gateway/security

[^5_34]: https://zread.ai/mksglu/context-mode

[^5_35]: https://www.reddit.com/r/CLine/comments/1qx4m16/how_are_people_managing_context_memory_with_cline/


---

# lass uns einmal an der Strukur im Repo arbeiten, den Rest habe ich schon ganz gut definiert.

Ich denke wir sollten docs/ai/ nehmen, oder hast du einen besseren vorschlag wo die Root für die "Memory Bank" hin soll?
Ich will diese nicht verstecken, sie soll ja auch für den Nutzer direkt lesbar sein.

dann finde ich den Ansatz von youngleaders nicht schlecht.

- memory.md entspricht die routing info für das repo
- general.md die generellen informationen für die arbeit im repo (lazy loaded von memory.md)
- projects.md fällt je weg, die lebt ja in ~/Kouzou/projects/<project>/memory.md und wird über @ aus der repo CLAUDE.md geladen (falls notwendig)
der Rest mit Tools, Domain directories würde dann ja gut passen.

Die andere Frage ist welche anderen Verzeichnisse es Standardmäßig geben sollte und was normale Best Practices sind.

Könnte man z.b alle build related files wie esbuild, package.json auch in ein Unterverzeichnis packen? Ich möchte die root des repo möglichst klein halten.

Ich denke wir brauchen

- docs
- test
- src

was noch? Vor allen in Bezug auf dann Verzeichnis bezogene CLAUDE.mds

Das lazy loading müßte halt nur entsprechend definiert werden, so wie in dem reddit artikle.

---

https://www.reddit.com/r/ClaudeAI/comments/1lr6occ/tip_managing_large_claudemd_files_with_document/

I discovered a simple pattern that's been a game-changer, and wanted to share:

# Instead of one huge file, use document references:

``` markdown
### 🗺️ Key Documentation References
- **Docker Architecture**: `/docs/DOCKER_ARCHITECTURE.md` 🐳
- **Database Architecture**: `/docs/DATABASE_ARCHITECTURE.md`
- **PASSWORD TRUTH**: `/docs/PASSWORD_TRUTH.md` 🚨 READ THIS FIRST!
- **JWT Authentication**: `/docs/JWT_AUTHENTICATION_ARCHITECTURE.md` 🔐
- **Security Checklist**: `/docs/SECURITY_CHECKLIST.md` 🚨
- **Feature Requests**: `/docs/enhancements/README.md`
- **Health Monitoring V2**: `/docs/enhancements/HEALTH_MONITORING_V2.md` 🆕
```


# The key insight: Critical documentation pattern

I added this to my CLAUDE.md:

```markdown
## 📚 CRITICAL DOCUMENTATION PATTERN
**ALWAYS ADD IMPORTANT DOCS HERE!** When you create or discover:
- Architecture diagrams → Add reference path here
- Database schemas → Add reference path here  
- Problem solutions → Add reference path here
- Setup guides → Add reference path here

This prevents context loss! Update this file IMMEDIATELY when creating important docs.
```


# Why this works so well:

1. [**CLAUDE.md**](http://claude.md/) **stays manageable** - Mine is still ~470 lines but references 15+ detailed docs
2. **Deep dives live elsewhere** - Complex architecture docs can be as long as needed
3. **Instant context** - Claude Code knows exactly where to find specific info
4. **Problem/solution tracking** - That `/docs/PASSWORD_TRUTH.md` saved me hours!
5. **Version control friendly** - Changes to specific docs don't bloat the main file

---

Allerdings hatte er wohl das ganze nicht so im Griff und hatte nachher zu viel Informationen / Dateien.. aber das sollte ja mit unseren anderen Ansatz abgedeckt sein.

Mich interessiert jetzt erst einmal die Struktur des Repos für unseren Ansatz.

Summary
`docs/ai/` als sichtbare Root für die Memory‑Bank passt gut zu deinem Ziel („nicht verstecken“) und zu TCS‑Vision; die Repo‑Struktur lässt sich darum herum mit wenigen Standard‑Verzeichnissen und gezielten Verzeichnis‑CLAUDE.mds sauber aufziehen.[^6_1][^6_2][^6_3]

***

## Empfohlene Repo-Struktur

**Root-Ebene (möglichst schlank)**

- `CLAUDE.md`
    - kurz, referenziert nur:
        - `docs/ai/memory/memory.md` (Routing/Index),
        - `docs/ai/CRITICAL_DOCS.md` (Referenzliste wie im Reddit‑Pattern),
        - Projekt‑Memory via `@~/Kouzou/projects/<project>/memory.md` (falls nötig).[^6_2][^6_3]
- `docs/`
    - `ai/` → Memory‑Bank + AI‑Spezifika (siehe unten).
    - `architecture/`, `design/` etc. für fachliche Doku.
- `src/` – Code.
- `test/` – Tests.
- Optional:
    - `config/` – Build‑/Tooling‑Konfigs (siehe unten).
    - `scripts/` – Hilfsskripte.

Alles andere (esbuild, Vite, tsconfig, etc.) kannst du schrittweise in `config/` oder `config/build/` verschieben, solange die jeweiligen Tools das unterstützen. Die Root bleibt so im Wesentlichen: `CLAUDE.md`, `docs/`, `src/`, `test/`, `config/`, `package.json` (falls nötig).[^6_3][^6_1]

***

## Memory Bank unter docs/ai/

Strukturvorschlag direkt aus TCS‑Vision + Youngleaders‑Pattern abgeleitet:[^6_2][^6_3]

- `docs/ai/memory/`
    - `memory.md`
        - Index + Routing‑Info für das Repo, analog Conneelys `MEMORY.md` (≤ 200 Zeilen).[^6_3][^6_2]
        - Enthält auch den „Critical Documentation Pattern“-Block mit Pfaden zu wichtigen Docs (wie im Reddit‑Beispiel), z.B.:
            - `/docs/architecture/DOCKER_ARCHITECTURE.md`
            - `/docs/architecture/DATABASE_SCHEMA.md`
            - `/docs/security/SECURITY_CHECKLIST.md`.[^6_2]
    - `general.md`
        - generelle Regeln und Konventionen für das Repo (Naming, Code‑Style, Repo‑Ziele), lazy‑loaded über Referenz aus `memory.md`.[^6_3]
    - `tools.md`
        - repo‑spezifisches Tool‑Wissen: Build‑Pipeline, CI‑Skripte, lokale Tools, Besonderheiten.[^6_2][^6_3]
    - `domain.md`
        - Business‑Regeln, Datenmodelle, Architektur‑Entscheidungen für dieses Repo.[^6_3]
    - `decisions.md`
        - ADR‑Kurzformen oder Links auf echte ADR‑Files (z.B. `docs/architecture/adr/`).[^6_1][^6_3]
    - `context.md`
        - aktuelle Ziele, Fokusbereiche, evtl. kurze „current sprint context“, wird von memory‑cleanup regelmäßig ausgedünnt.[^6_1][^6_3]
    - `troubleshooting.md`
        - bekannte Probleme und Fixes, kann über cleanup in einen `archive/`‑Bereich verschoben werden.[^6_1][^6_2][^6_3]

Damit ist `docs/ai/memory/memory.md` dein zentrales Routing‑Dokument (Index + „Critical Docs“-Liste), während einzelne Dateien fokussiert bleiben.[^6_2][^6_3]

***

## Verzeichnis-bezogene CLAUDE.md

Du kannst die CLAUDE‑Discovery so nutzen, dass sie dein Lazy‑Loading verstärkt:[^6_4][^6_2]

- Root: `CLAUDE.md`
    - beschreibt nur die Grundregeln und verweist auf `docs/ai/memory/memory.md`.
- `src/CLAUDE.md`
    - Fokus auf Code‑Qualität, TDD/SDD‑Integration, Architektur‑Regeln für Implementierung.[^6_5][^6_3]
- `test/CLAUDE.md`
    - Fokus auf Test‑Struktur, Naming‑Konventionen, Coverage‑Erwartungen, evtl. Hinweise zu Mutation‑Testing.[^6_1][^6_3]
- `docs/CLAUDE.md`
    - Regeln für Dokumentation (wie Architektur‑Docs aufgebaut sein sollen, wo sie gelistet werden).[^6_3]
- `docs/ai/CLAUDE.md` (optional)
    - erklärt, wie Memory‑Bank genutzt und gepflegt wird (wann `memory.md` zu aktualisieren ist, wie `domain.md` vs. `decisions.md` zu trennen sind).[^6_3]

Diese Dateien werden nur geladen, wenn du in dem jeweiligen Verzeichnis arbeitest – das ist effektiv „directory‑scoped lazy loading“ und ersetzt viele explizite Load‑Kommandos in der Root‑CLAUDE.[^6_4][^6_2]

***

## Build-/Tooling-Dateien verschlanken

Best Practices in Richtung „saubere Root“:

- `config/` oder `config/build/`
    - `config/build/esbuild.config.ts`
    - `config/build/vite.config.ts`
    - `config/jest.config.ts` etc.
- `package.json` bleibt in der Root (weil Tools und Menschen das erwarten), aber du kannst Scripts/Felder minimal halten und vom TCS‑Setup‑Skill generieren lassen.[^6_1][^6_3]

In `docs/ai/memory/tools.md` beschreibst du, wo diese Konfigs liegen, damit Claude sie schnell findet, ohne die Root mit Hunderten Dateien zu füllen.[^6_2][^6_3]

***

## Lazy Loading / Routing-Definition

Inhaltlich kannst du das Reddit‑Pattern direkt in `memory.md` (oder Root‑CLAUDE) adaptieren:[^6_2]

- In `CLAUDE.md`:
    - „Für alle wichtigen Docs siehe `docs/ai/memory/memory.md` → Section CRITICAL DOCUMENTATION.“
- In `memory.md`:
    - Liste der wichtigsten Docs mit absoluten oder relativen Pfaden, wie in deinem Zitat.
    - Hinweis: „Wenn du neue Architektur‑/Setup‑/Security‑Docs anlegst, füge sie hier hinzu.“

Zusätzlich:

- `memory.md` erklärt, welche anderen Memory‑Files es gibt und wofür sie zuständig sind (general/tools/domain/...).[^6_3]

***

## Empfehlung

- Ja, `docs/ai/` ist eine gute sichtbare Root für die Memory‑Bank; sie passt zum TCS‑Vision‑Layout (`.claude/memory` war dort nur „indicative“, nicht fest).[^6_3]
- Ich würde als nächsten Schritt ein konkretes Skelett für `docs/ai/memory/memory.md` + `general.md` + einen minimalen `CLAUDE.md`‑Header entwerfen, damit du die Struktur im ersten Repo direkt ausprobieren kannst.

Möchtest du als nächstes ein konkretes Markdown‑Skelett für `CLAUDE.md` und `docs/ai/memory/memory.md` (inkl. Critical‑Docs‑Abschnitt) haben?
<span style="display:none">[^6_6]</span>

<div align="center">⁂</div>

[^6_1]: overlap-analysis.md

[^6_2]: sources.md

[^6_3]: tcs-vision.md

[^6_4]: https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with

[^6_5]: tdd-sdd-integration.md

[^6_6]: SKILL.md

