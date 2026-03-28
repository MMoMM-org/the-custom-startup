Summary  
Der MCP‑Teil von deinem Design besteht aus einem erweiterten context-mode‑Server, der drei Rollen übernimmt: Gateway/Registry für andere MCP‑Server, Security‑Scanner für deren Konfiguration und optionaler Adapter, um Kairn als externes Projekt‑Gedächtnis anstelle der internen context-mode‑DB für bestimmte Daten zu nutzen.[1][2][3][4][5][6][7]

***

## Findings

### 1. Ausgangspunkt: context-mode heute

- context-mode ist ein MCP‑Server, der alle Tool‑Calls abfängt, deren Output in eine per‑Projekt SQLite‑FTS5‑DB indexiert und nur verdichtete, relevante Ausschnitte an Claude zurückgibt.[2][3][8][9][10]
- Er sitzt zwischen Agent und Tools, kapselt subprocess‑Ausführung, speichert Session‑Events, und ermöglicht spätere gezielte Queries anstatt rohe Outputs ins Kontextfenster zu kippen.[3][11][12]

Das ist deine Basis für: „normaler“ Context‑Server, Session‑Kontinuität und Kontext‑Reduktion.

***

### 2. Erweiterung 1: MCP Server Gateway / Registry

Ziel: context-mode soll mehrere nachgelagerte MCP‑Server bündeln und für Claude wie ein einziger Server erscheinen, ähnlich wie lasso‑mcp‑gateway.[4][7][1]

**Konzeptuell:**

- context-mode Gateway‑Layer:  
  - Frontend: ein MCP‑Endpoint, den Claude Code als „context-mode“ (wir müssen vielleicht den Namen ändern weil das nicht mehr nur context-mode ist.  
  - vielleicht: satori
      - „Satori“ als Erkenntnis/Moment des Verstehens – hübsches Bild für einen Kontext‑Server, der den Kern herausdestilliert.
  - Backend: Registry von MCP‑Servern (filesystem, github, basic-memory, kairn, etc.), die per STDIO/HTTP eingebunden sind.[11][13][2][3]

- Funktionen der Registry:  
  - Laden der Serverdefinitionen aus einer Konfig (z.B. `~/.context-mode/mcp.json` oder `~/.mcp/context-mode.json`).
    - Trennung zwischen Global / Project / Repo auch hier. liegt im ~/.claude verzeichnis in Global, im <project> Verzeichnis und in der root des repos
    - zu prüfen ist ob das .mcp.json file im repo bestehen bleiben kann und wir das autoregistrieren und dann über die config an/aus schalten.
  - Dynamische Capability‑Registrierung: Tools der down‑stream MCPs werden als `<server>_<tool>` oder via Namespacing exponiert, ähnlich der Dynamic Capability Registration im lasso‑Gateway.[1]
  - Routing: context-mode entscheidet anhand des Toolnamens / Namespaces, an welchen Server der Aufruf geht.[7][1]
  - hot/cold mode für MCP, so ähnlich wie Airis Server.. MCP Server nur dann laden wenn a) enabled und b) gebraucht

Damit hast du:  
- Einen einzigen MCP‑Entry in Claude Code, der intern viele Servers orchestriert.  
- Einen klaren Ort (context-mode) für spätere Security‑Filter und Policies.

***

### 3. Erweiterung 2: Security Scanner im Gateway

Ziel: context-mode soll vor dem Laden/Expose von MCP‑Servern deren Risiko prüfen und Konfiguration entsprechend markieren/blocken, angelehnt an lasso‑mcp‑gateway‑Scanner.[6][4][7][1]

**Bausteine:**

- **Scan‑Zeitpunkt:**  
  - Beim Start von context-mode (oder wenn Konfig sich ändert) wird jede MCP‑Server‑Definition gescannt.[1]

- **Analyse‑Dimensionen:**  
  - Reputation: GitHub‑Infos, Stars, ggf. Marketplace‑Einträge, wenn verfügbar (ähnlich lasso‑Reputation Analysis).[4][1]
  - Tool‑Beschreibungen: Pattern‑Scan auf sensible Aktionen (delete, exfiltrate, network‑calls, secrets‑read etc.), hidden instructions, riskante File‑Pfade.[7][1]
  - Konfiguration: Ports, Pfade, Shell‑Kommandos – potentielle Injection‑Punkte.[3][7]

- **Ergebnis & Policy:**  
  - Score + Status pro Server: `passed`, `blocked`, `skipped`, `pending` – analog zur lasso‑Gateway‑Konfiguration.[1]
  - Gate im Gateway: Tools eines `blocked` Servers werden nicht registriert bzw. sind für Claude unsichtbar.[7][1]
  - Logging: Audit‑Log (z.B. `~/.context-mode/scanner.log`) mit Begründungen, wie beim lasso‑Scanner.[4][1]

Damit verhält sich context-mode nicht nur als Kontext‑Optimierer, sondern auch als Sicherheitslayer für alle Tools, die du über TCS/TCS‑Plugins nutzt.

Note:

Vor allem soll er die Daten die an MCP server geleitet werden "intelligent" scannen. Siehe https://github.com/peterkrueck/Claude-Code-Development-Kit/blob/main/hooks/mcp-security-scan.sh
Ich weiß nicht wirklich ob wir den vollen lasso Ansatz machen sollten: Hier sollten wir noch einmal ein genaueres Spec schreiben was der Mode genau machen soll.

***

### 4. Erweiterung 3: Kairn-Integration als externer Context Store

Ziel: Kairn soll als persistentes, graphbasiertes Projekt‑Gedächtnis fungieren und für bestimmte „Memory‑/Context‑Anfragen“ statt der internen context-mode‑SQLite‑DB genutzt werden.[5][14][15]

**Kairn-Fähigkeiten (aus Evolving‑Lite/Kairn):**

- Hält einen Knowledge‑Graph mit Projekten, Entscheidungen, „Experiences“, der beim Boot in Sekunden geladen wird.[14][5]
- Unterstützt semantische Queries à la „Wie habe ich Auth‑Bug XY gelöst?“ statt reinem Text‑FTS.[5][14]
- Baut sich durch kontinuierliches Lernen aus Code‑Fixes und Entscheidungen selbst weiter auf.[14][5]

**Design im context-mode‑Gateway:**

- context-mode bleibt Default‑Context‑Server:  
  - Interne SQLite‑DB trackt Tool‑Outputs, Logs, Session‑Events.[3]

- Wenn Kairn als MCP‑Server registriert ist (z.B. `kairn` mit Tools `kairn_query`, `kairn_learn`):[15][5][14]
  - Gateway markiert Kairn als „Semantic Memory Provider“ im Registry‑State.  
  - Bestimmte Kontext‑Skills oder Tools werden auf Kairn geroutet:  
    - „project‑level knowledge“ → Kairn.  
    - „raw tool output recall / logs“ → context-mode SQLite.[5][3]

- Praktische Regeln (Beispiele):  
  - `context_search_recent_output` → context-mode interne DB.  
  - `context_search_decision_graph` oder `context_search_past_solution` → Kairn‑Tool.[14][3][5]
  - Beim Session‑Start kann context-mode optional einen „Bootup Context“ von Kairn holen (Graph‑Snapshot) und als condensed Summary an Claude liefern – wie im Evolving‑Lite Demo.[5][14]

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

Sources
[1] Releases · lasso-security/mcp-gateway https://github.com/lasso-security/mcp-gateway/releases
[2] GitHub - mksglu/context-mode: Privacy-first. MCP is the protocol for ... https://github.com/mksglu/context-mode
[3] Context Mode: Reducing AI Context Bloat with an MCP Server https://betterstack.com/community/guides/ai/context-mode-mcp/
[4] Lasso Launches Open Source MCP Security Gateway https://www.lasso.security/resources/lasso-releases-first-open-source-security-gateway-for-mcp
[5] Claude Code Persistent Memory with Evolving Lite - PrimeLine https://primeline.cc/blog/persistent-memory-evolving-lite
[6] Why MCP Agents Are the Next Cybersecurity Battleground https://www.lasso.security/blog/why-mcp-agents-are-the-next-cyber-battleground
[7] Secure Your MCP Connections - Lasso Security https://www.lasso.security/use-cases/mcp
[8] Stop Burning Your Context Window — We Built Context Mode https://www.linkedin.com/pulse/stop-burning-your-context-window-we-built-mode-mert-koseoglu-c04nf
[9] mksglu/claude-context-mode - Mert Koseoglu - LinkedIn https://www.linkedin.com/posts/mksglu_github-mksgluclaude-context-mode-activity-7431589485726814208-Ft9w
[10] MCP server that reduces Claude Code context consumption by 98% https://news.ycombinator.com/item?id=47193064
[11] Claude Context Mode https://cultofclaude.com/skills/claude-context-mode/
[12] context-mode - mksglu/context-mode | Skills Leaderboard https://skills-rank.com/skill/mksglu/context-mode/context-mode
[13] GitHub - mcp-s-ai/secure-mcp-gateway https://github.com/mcp-s-ai/secure-mcp-gateway
[14] How to Give Claude Code Persistent Memory https://www.youtube.com/watch?v=mR6Ss6Tnzm4
[15] PrimeLine: Open Source Claude Code Plugins & Tools https://primeline.cc
[16] overlap-analysis.md [URL redacted — contained expired AWS STS session token]
[17] sources.md [URL redacted — contained expired AWS STS session token]
[18] tcs-vision.md [URL redacted — contained expired AWS STS session token]
[19] tdd-sdd-integration.md [URL redacted — contained expired AWS STS session token]
[20] SKILL.md [URL redacted — contained expired AWS STS session token]
[21] mksglu - Overview https://github.com/mksglu
[22] Canvas - Copy number variant (CNV) calling from DNA ... - GitHub https://github.com/Illumina/canvas
[23] iPhone Region/Country Codes https://gist.github.com/donn/0c501ab625625c381fdf3210bf0ff275
[24] GitHub - mik3y/usb-serial-for-android: Android USB host serial driver library for CDC, FTDI, Arduino and other devices. https://github.com/mik3y/usb-serial-for-android
[25] Activity · vllm-project/vllm-project.github.io https://github.com/vllm-project/vllm-project.github.io/activity
[26] GitHub - siderolabs/talos: Talos Linux is a modern Linux distribution built for Kubernetes. https://github.com/siderolabs/talos
[27] Display Problem on Ventura · Issue #647 · sickcodes/Docker-OSX https://github.com/sickcodes/Docker-OSX/issues/647
[28] GitHub - ggcr/Super-Temporal-LIIF: End-to-End Framework for Continuous Space-Time Super-Resolution on Remote Sensing data. https://github.com/ggcr/Super-Temporal-LIIF
[29] Mate needs gtk-engine-murrine for its theme. · Issue #103 · AnarchyLinux/installer https://github.com/AnarchyLinux/installer/issues/103
[30] Activity · lasso-security/mcp-gateway https://github.com/lasso-security/mcp-gateway/activity
[31] Make fuse_main() more powerful · Issue #382 · libfuse/libfuse https://github.com/libfuse/libfuse/issues/382
[32] react-native/Libraries/vendor/emitter/EventEmitter.js at 055c941c4045468af4ff2b8162d3a35dd993b1b9 · facebook/react-native https://github.com/facebook/react-native/blob/055c941c4045468af4ff2b8162d3a35dd993b1b9/Libraries/vendor/emitter/EventEmitter.js
[33] Build software better, together https://github.com/lasso-security/mcp-gateway/security
[34] Overview | mksglu/context-mode | Zread https://zread.ai/mksglu/context-mode
[35] How are people managing context + memory with Cline? ... https://www.reddit.com/r/CLine/comments/1qx4m16/how_are_people_managing_context_memory_with_cline/
