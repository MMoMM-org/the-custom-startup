Summary  
`docs/ai/` als sichtbare Root für die Memory‑Bank passt gut zu deinem Ziel („nicht verstecken“) und zu TCS‑Vision; die Repo‑Struktur lässt sich darum herum mit wenigen Standard‑Verzeichnissen und gezielten Verzeichnis‑CLAUDE.mds sauber aufziehen.[1][2][3]

***

## Empfohlene Repo-Struktur

**Root-Ebene (möglichst schlank)**  
- `CLAUDE.md`  
  - kurz, referenziert nur:  
    - `docs/ai/memory/memory.md` (Routing/Index),  
    - `docs/ai/CRITICAL_DOCS.md` (Referenzliste wie im Reddit‑Pattern),  
    - Projekt‑Memory via `@~/Kouzou/projects/<project>/memory.md` (falls nötig).[2][3]
- `docs/`  
  - `ai/` → Memory‑Bank + AI‑Spezifika (siehe unten).  
  - `architecture/`, `design/` etc. für fachliche Doku.  
- `src/` – Code.  
- `test/` – Tests.  
- Optional:  
  - `config/` – Build‑/Tooling‑Konfigs (siehe unten).  
  - `scripts/` – Hilfsskripte.  

Alles andere (esbuild, Vite, tsconfig, etc.) kannst du schrittweise in `config/` oder `config/build/` verschieben, solange die jeweiligen Tools das unterstützen. Die Root bleibt so im Wesentlichen: `CLAUDE.md`, `docs/`, `src/`, `test/`, `config/`, `package.json` (falls nötig).[3][1]

***

## Memory Bank unter docs/ai/

Strukturvorschlag direkt aus TCS‑Vision + Youngleaders‑Pattern abgeleitet:[2][3]

- `docs/ai/memory/`  
  - `memory.md`  
    - Index + Routing‑Info für das Repo, analog Conneelys `MEMORY.md` (≤ 200 Zeilen).[3][2]
    - Enthält auch den „Critical Documentation Pattern“-Block mit Pfaden zu wichtigen Docs (wie im Reddit‑Beispiel), z.B.:  
      - `/docs/architecture/DOCKER_ARCHITECTURE.md`  
      - `/docs/architecture/DATABASE_SCHEMA.md`  
      - `/docs/security/SECURITY_CHECKLIST.md`.[2]
  - `general.md`  
    - generelle Regeln und Konventionen für das Repo (Naming, Code‑Style, Repo‑Ziele), lazy‑loaded über Referenz aus `memory.md`.[3]
  - `tools.md`  
    - repo‑spezifisches Tool‑Wissen: Build‑Pipeline, CI‑Skripte, lokale Tools, Besonderheiten.[2][3]
  - `domain.md`  
    - Business‑Regeln, Datenmodelle, Architektur‑Entscheidungen für dieses Repo.[3]
  - `decisions.md`  
    - ADR‑Kurzformen oder Links auf echte ADR‑Files (z.B. `docs/architecture/adr/`).[1][3]
  - `context.md`  
    - aktuelle Ziele, Fokusbereiche, evtl. kurze „current sprint context“, wird von memory‑cleanup regelmäßig ausgedünnt.[1][3]
  - `troubleshooting.md`  
    - bekannte Probleme und Fixes, kann über cleanup in einen `archive/`‑Bereich verschoben werden.[1][2][3]

Damit ist `docs/ai/memory/memory.md` dein zentrales Routing‑Dokument (Index + „Critical Docs“-Liste), während einzelne Dateien fokussiert bleiben.[2][3]
Tools, Domain, Descisions etc sind dann wiederum eigene Unterverzeichnisse mit mehr Informationen.

***

## Verzeichnis-bezogene CLAUDE.md

Du kannst die CLAUDE‑Discovery so nutzen, dass sie dein Lazy‑Loading verstärkt:[4][2]

- Root: `CLAUDE.md`  
  - beschreibt nur die Grundregeln und verweist auf `docs/ai/memory/memory.md`.  

- `src/CLAUDE.md`  
  - Fokus auf Code‑Qualität, TDD/SDD‑Integration, Architektur‑Regeln für Implementierung.[5][3]

- `test/CLAUDE.md`  
  - Fokus auf Test‑Struktur, Naming‑Konventionen, Coverage‑Erwartungen, evtl. Hinweise zu Mutation‑Testing.[1][3]

- `docs/CLAUDE.md`  
  - Regeln für Dokumentation (wie Architektur‑Docs aufgebaut sein sollen, wo sie gelistet werden).[3]

- `docs/ai/CLAUDE.md` (optional)  
  - erklärt, wie Memory‑Bank genutzt und gepflegt wird (wann `memory.md` zu aktualisieren ist, wie `domain.md` vs. `decisions.md` zu trennen sind).[3]

Diese Dateien werden nur geladen, wenn du in dem jeweiligen Verzeichnis arbeitest – das ist effektiv „directory‑scoped lazy loading“ und ersetzt viele explizite Load‑Kommandos in der Root‑CLAUDE.[4][2]

***

## Build-/Tooling-Dateien verschlanken

Best Practices in Richtung „saubere Root“:

- `config/` oder `config/build/`  
  - `config/build/esbuild.config.ts`  
  - `config/build/vite.config.ts`  
  - `config/jest.config.ts` etc.  
- `package.json` bleibt in der Root (weil Tools und Menschen das erwarten), aber du kannst Scripts/Felder minimal halten und vom TCS‑Setup‑Skill generieren lassen.[1][3]

In `docs/ai/memory/tools.md` beschreibst du, wo diese Konfigs liegen, damit Claude sie schnell findet, ohne die Root mit Hunderten Dateien zu füllen.[2][3]

***

## Lazy Loading / Routing-Definition

Inhaltlich kannst du das Reddit‑Pattern direkt in `memory.md` (oder Root‑CLAUDE) adaptieren:[2]

- In `CLAUDE.md`:  
  - „Für alle wichtigen Docs siehe `docs/ai/memory/memory.md` → Section CRITICAL DOCUMENTATION.“  
- In `memory.md`:  
  - Liste der wichtigsten Docs mit absoluten oder relativen Pfaden, wie in deinem Zitat.  
  - Hinweis: „Wenn du neue Architektur‑/Setup‑/Security‑Docs anlegst, füge sie hier hinzu.“  

Zusätzlich:  
- `memory.md` erklärt, welche anderen Memory‑Files es gibt und wofür sie zuständig sind (general/tools/domain/...).[3]

***

## Empfehlung

- Ja, `docs/ai/` ist eine gute sichtbare Root für die Memory‑Bank; sie passt zum TCS‑Vision‑Layout (`.claude/memory` war dort nur „indicative“, nicht fest).[3]
- Ich würde als nächsten Schritt ein konkretes Skelett für `docs/ai/memory/memory.md` + `general.md` + einen minimalen `CLAUDE.md`‑Header entwerfen, damit du die Struktur im ersten Repo direkt ausprobieren kannst.

Möchtest du als nächstes ein konkretes Markdown‑Skelett für `CLAUDE.md` und `docs/ai/memory/memory.md` (inkl. Critical‑Docs‑Abschnitt) haben?

Sources
[1] overlap-analysis.md https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29350042/f598a795-38b9-4f28-a168-7111efb12970/overlap-analysis.md
[2] sources.md https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29350042/c85e4583-fc9b-4f83-afac-312b6f1fdff1/sources.md
[3] tcs-vision.md https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29350042/3e64ae8a-577f-4750-8931-15eadf71583a/tcs-vision.md
[4] Claude Code's Memory: Working with AI in Large Codebases https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with
[5] tdd-sdd-integration.md https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29350042/407cb99c-5c33-4d70-8fd4-efdcf5c8236b/tdd-sdd-integration.md
[6] SKILL.md https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29350042/a5caf4c3-03e3-4b05-a9fa-65aa7ab76cff/SKILL.md
