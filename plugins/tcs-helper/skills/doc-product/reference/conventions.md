# Page Type → Section Structure

This file maps each minimum `docs/` page type to a recommended section structure,
the purpose of each section, and a "must include" checklist. `modes/write.md`
references this map when proposing section structure to the author.

Used by: `modes/write.md`

---

## installation

**Persona served**: first-time installer — has never used this software, knows their
operating system, wants to install and verify in one sitting.

**Recommended sections**:

- Prerequisites — lists software, OS, and account requirements the reader must have
  before the first install step.
- Install — gives the exact command or UI steps to put the software on the machine.
- Verify — tells the reader how to confirm the installation succeeded without needing
  to contact the author.
- Next steps — points to configuration or a quickstart so the reader knows what to do
  after a successful install.

**Must include**:

- How do I verify it works?
- What do I need before I start (prerequisites)?
- Where does the software end up after installation?

---

## configuration

**Persona served**: config-explorer — has the software installed, wants to understand
a setting's purpose and default before changing it.

**Recommended sections**:

- Where settings live — describes the file, UI panel, or environment variable that
  holds the configuration, so the reader can find it without guessing.
- Settings reference — documents each option: name, type, default, and what it
  controls; a table is the canonical form.
- Override mechanism — explains how to change a setting (edit a file, toggle a UI
  control, set an env var) and what takes precedence when multiple sources conflict.
- Defaults and safe values — calls out which defaults are safe to leave untouched and
  which ones the reader is expected to change for their use case.

**Must include**:

- What is the default value for each setting?
- What happens if I leave a setting at its default?
- How do I change a setting without breaking anything?

---

## usage

**Persona served**: task-runner — has the software configured and wants to accomplish
a specific goal without reading the full source code.

**Recommended sections**:

- Invocation — shows the minimal command or interaction needed to make the software
  do something useful.
- Common patterns — covers the two or three most frequent real-world invocations with
  the flags or options that matter.
- Expected output — describes what success looks like (exit codes, files written,
  messages printed) so the reader knows whether it worked.
- Flags and options — reference table or list of all user-facing options, their types,
  and their defaults.

**Must include**:

- How do I run the most common task?
- What does a successful run look like?
- What flags are available and what do they do?

---

## troubleshooting

**Persona served**: troubleshooter — hit an error, has the software roughly installed
and configured, wants to recover without contacting the author.

**Recommended sections**:

- Common errors — symptom → cause → fix entries for the errors users encounter most
  frequently; a table or definition-list structure keeps scanning fast.
- Where to look for logs — points the reader to log files, debug flags, or OS tools
  that produce the diagnostic output needed to diagnose unexpected failures.
- Diagnostic steps — a short ordered checklist the reader can run through before
  escalating, so they can rule out the most common root causes themselves.
- Escalation — explains how to report an unresolved issue (link to issue tracker,
  required information to include, expected response time).

**Must include**:

- What does this error mean and how do I fix it?
- Where are the logs or diagnostic output?
- What information do I need to gather before asking for help?
