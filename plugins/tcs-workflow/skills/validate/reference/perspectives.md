# Validation Perspectives

Perspective definitions, activation rules, and detailed focus areas for the validate skill.

---

## Perspectives

### ✅ Completeness

**Intent**: Ensure nothing is missing from specifications or implementations. *(Structural presence: do required sections, markers, and artifacts exist?)*

**Does NOT cover**: Whether content is deep enough (acceptance criteria specificity, edge case enumeration) — that's Coverage.

**What to validate**:
- All required sections exist and are non-empty
- No `[NEEDS CLARIFICATION]` markers remain
- Validation checklists are complete (all `[x]`)
- No TODO/FIXME/XXX/HACK markers in implementation
- Required artifacts present (PRD, SDD, PLAN as applicable)

**Techniques**: Section scanning, marker detection, checklist completion counting. See `3cs-framework.md` for full methodology.

### 🔗 Consistency

**Intent**: Check internal alignment within and across documents.

**What to validate**:
- Terminology used consistently across all documents
- No contradictory statements between sections
- Cross-references are valid (linked sections exist)
- PRD requirements trace to SDD components
- SDD components trace to PLAN tasks
- Implementation matches specification interfaces

**Techniques**: Term frequency analysis, cross-reference verification, traceability matrix building. See `3cs-framework.md`.

### 📍 Alignment

**Intent**: Verify that documented patterns actually exist in code. *(Snapshot match: is the current implementation consistent with documented contracts?)*

**Does NOT cover**: Whether implementation has diverged from specification requirements over time — that's Drift.

**What to validate**:
- Documented architectural patterns present in implementation
- Interface contracts match actual code signatures
- No hallucinated implementations (spec describes something code doesn't do)
- Configuration values match documented values
- Data models match schema descriptions

**Techniques**: Interface contract comparison, naming convention analysis, import analysis. See `drift-detection.md` for detection strategies.

### 📐 Coverage

**Intent**: Assess specification depth and completeness of coverage. *(Content depth: are criteria specific, edge cases enumerated, targets measurable?)*

**Does NOT cover**: Whether required sections and artifacts structurally exist — that's Completeness.

**What to validate**:
- All functional requirements have acceptance criteria
- All interfaces have complete type specifications
- Edge cases are addressed (null, empty, boundary values)
- Error handling documented for each operation
- Non-functional requirements have measurable targets
- Security considerations documented

**Techniques**: Requirement-to-spec mapping, acceptance criteria counting, edge case enumeration. See `3cs-framework.md`.

### 📊 Drift

**Intent**: Detect divergence between specifications and implementation. *(Delta analysis: has implementation diverged from spec requirements — scope creep, missing features, contradictions?)*

**Does NOT cover**: Whether current code matches documented interfaces and schemas — that's Alignment.

**What to validate**:
- Scope creep — implementation adds features not in spec
- Missing — spec requires features not yet implemented
- Contradicts — implementation conflicts with spec
- Extra — unplanned work that may or may not be valuable

**Techniques**: Acceptance criteria mapping, interface contract validation, architecture pattern verification, PLAN task completion checking. See `drift-detection.md` for full strategies, severity assessment, and drift logging.

### 📜 Constitution

**Intent**: Enforce project governance rules from CONSTITUTION.md.

**What to validate**:
- L1 (Must) — Critical rules, blocking, autofix required
- L2 (Should) — Important rules, blocking, human action required
- L3 (May) — Advisory, non-blocking, informational only

**Techniques**: Pattern rules (regex matching), check rules (semantic LLM analysis), scope-based file filtering. See `constitution-validation.md` for rule schema, parsing, and execution.

---

## Perspective Selection by Validation Mode

| Validation Mode | Perspectives Applied |
|----------------|---------------------|
| **Spec Validation** | ✅ Completeness, 🔗 Consistency, 📍 Alignment, 📐 Coverage + ambiguity detection |
| **File Validation** | ✅ Completeness, 🔗 Consistency, 📍 Alignment |
| **Drift Detection** | 📊 Drift, 📍 Alignment, 🔗 Consistency |
| **Constitution** | 📜 Constitution |
| **Comparison** | 📍 Alignment, 🔗 Consistency, 📐 Coverage |
| **Understanding** | 📍 Alignment, ✅ Completeness |

## Conditional Perspectives

| Condition | Additional Perspective |
|-----------|----------------------|
| CONSTITUTION.md exists | +📜 Constitution |
| Spec + implementation both available | +📊 Drift |
| Specification documents only | +Ambiguity scoring (see `ambiguity-detection.md`) |
