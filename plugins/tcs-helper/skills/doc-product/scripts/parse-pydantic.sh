#!/usr/bin/env bash
# parse-pydantic.sh — Pydantic / dataclass settings parser
# Bash 3.2 compatible.
#
# Usage:  parse-pydantic.sh <python_file_path> [class_name]
#
# Output: TSV on stdout with header: name<TAB>type<TAB>default<TAB>description
#         One row per declared field.
#
# Exit codes:
#   0  success
#   1  file not found
#   2  python3 not on PATH (ADR-5 missing-dependency error)
#   3  no suitable class found in file
#   4  pydantic module unavailable in python3 (when file imports pydantic)
#
# Error messages go to stderr; no Python tracebacks are allowed to leak.

set -euo pipefail

# ---------------------------------------------------------------------------
# ADR-5: dependency check — python3 must be on PATH before any parsing
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  printf 'error: python3 not found\n' >&2
  printf 'reason: Pydantic / dataclass settings extraction requires python3\n' >&2
  printf 'install: brew install python3  (macOS)  |  apt-get install python3  (Linux)\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
  printf 'usage: parse-pydantic.sh <python_file_path> [class_name]\n' >&2
  exit 1
fi

PYTHON_FILE="$1"
CLASS_NAME="${2:-}"

if [ ! -f "$PYTHON_FILE" ]; then
  printf 'error: file not found: %s\n' "$PYTHON_FILE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Check for pydantic import in file + pydantic availability in python3
# Only relevant when the file actually imports pydantic.
# ---------------------------------------------------------------------------
if grep -q 'from pydantic\|import pydantic' "$PYTHON_FILE"; then
  # File uses pydantic — verify python3 can import it
  if ! python3 -c 'import pydantic' 2>/dev/null; then
    printf 'error: Pydantic module unavailable in this environment\n' >&2
    printf 'reason: file imports pydantic but the parser'\''s python3 cannot import it\n' >&2
    printf 'install: pip install pydantic  (in the python3 environment used by this parser), or convert the source to JSON Schema first\n' >&2
    exit 4
  fi
fi

# ---------------------------------------------------------------------------
# Inline Python — introspect the module and emit TSV
# All Python error output is captured; no raw tracebacks reach the caller.
# ---------------------------------------------------------------------------
python3 -c '
import sys
import os
import importlib.util
import inspect
import re
import ast

NEEDS_DESC = "[NEEDS DESCRIPTION]"
NEEDS_DEFAULT = "[NEEDS DEFAULT]"

python_file = sys.argv[1]
class_name_arg = sys.argv[2] if len(sys.argv) > 2 else ""

# ---------------------------------------------------------------------------
# Load the module from file path without executing side-effects in __main__
# Use exec with a fresh namespace to avoid import machinery touching sys.path
# with potentially unavailable deps beyond pydantic.
# ---------------------------------------------------------------------------
module_source = open(python_file).read()

# Parse the AST to find class definitions — done before any import attempt
# so we can report "no class found" without import errors.
try:
    tree = ast.parse(module_source)
except SyntaxError as e:
    print("error: syntax error in {}: {}".format(python_file, e), file=sys.stderr)
    sys.exit(3)

# Collect class names from AST
ast_classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

if not ast_classes:
    print("error: no Pydantic BaseModel or @dataclass found in {}".format(python_file),
          file=sys.stderr)
    sys.exit(3)

# ---------------------------------------------------------------------------
# Load the module — errors from unavailable imports are caught and reported
# ---------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location("_dp_module", python_file)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except ImportError as e:
    print("error: cannot import module: {}".format(e), file=sys.stderr)
    sys.exit(3)
except Exception as e:
    print("error: failed to load {}: {}".format(python_file, e), file=sys.stderr)
    sys.exit(3)

# ---------------------------------------------------------------------------
# Detect available class(es) — filter to BaseModel subclasses or dataclasses
# ---------------------------------------------------------------------------
import dataclasses

def is_settings_class(obj):
    if not inspect.isclass(obj):
        return False
    if dataclasses.is_dataclass(obj):
        return True
    # duck-type for BaseModel (pydantic v1 + v2)
    if hasattr(obj, "__fields__") or hasattr(obj, "model_fields"):
        return True
    return False

candidates = [
    (name, obj)
    for name, obj in inspect.getmembers(mod, inspect.isclass)
    if obj.__module__ == "_dp_module" and is_settings_class(obj)
]

if not candidates:
    print("error: no Pydantic BaseModel or @dataclass found in {}".format(python_file),
          file=sys.stderr)
    sys.exit(3)

if class_name_arg:
    matched = [(n, c) for n, c in candidates if n == class_name_arg]
    if not matched:
        print("error: class {} not found in {}; available: {}".format(
            class_name_arg, python_file,
            ", ".join(n for n, _ in candidates)), file=sys.stderr)
        sys.exit(3)
    target_name, target_cls = matched[0]
else:
    if len(candidates) > 1:
        print("error: multiple settings classes found in {}; specify one: {}".format(
            python_file, ", ".join(n for n, _ in candidates)), file=sys.stderr)
        sys.exit(3)
    target_name, target_cls = candidates[0]

# ---------------------------------------------------------------------------
# Parse docstring for field descriptions (Google-style "Attributes:" section)
# ---------------------------------------------------------------------------
def parse_docstring_attrs(cls):
    """Return dict of field_name -> description from class docstring."""
    doc = inspect.getdoc(cls) or ""
    attrs = {}
    in_attrs = False
    # Match "Attributes:" or "Args:" section header (Google style)
    attr_section_re = re.compile(r"^(Attributes|Args)\s*:\s*$", re.IGNORECASE)
    # Match "    name: description" — 4-space indent or tab indent
    field_line_re = re.compile(r"^\s{2,}(\w+)\s*:\s*(.+)$")
    # rST :param name: description
    rst_param_re = re.compile(r"^:param\s+(\w+)\s*:\s*(.+)$")

    for line in doc.splitlines():
        # rST style — always collect
        m = rst_param_re.match(line.strip())
        if m:
            attrs[m.group(1)] = m.group(2).strip()
            continue
        if attr_section_re.match(line.strip()):
            in_attrs = True
            continue
        if in_attrs:
            # Stop at next section header (non-indented non-empty line)
            if line and not line[0].isspace():
                in_attrs = False
                continue
            m = field_line_re.match(line)
            if m:
                attrs[m.group(1)] = m.group(2).strip()
    return attrs

# ---------------------------------------------------------------------------
# Stringify type annotation
# ---------------------------------------------------------------------------
def type_str(annotation):
    if annotation is inspect.Parameter.empty or annotation is None:
        return ""
    # For typing generics, use repr and clean up
    s = getattr(annotation, "__name__", None)
    if s:
        return s
    # typing types (Optional, List, etc.)
    s = str(annotation)
    # Clean up "typing." prefix
    s = re.sub(r"typing\.", "", s)
    return s

# ---------------------------------------------------------------------------
# Stringify default value
# ---------------------------------------------------------------------------
def default_str(val, missing_sentinel):
    if val is missing_sentinel or val is inspect.Parameter.empty:
        return NEEDS_DEFAULT
    if val is dataclasses.MISSING:
        return NEEDS_DEFAULT
    return repr(val)

# ---------------------------------------------------------------------------
# Emit TSV
# ---------------------------------------------------------------------------
print("name\ttype\tdefault\tdescription")

# --- Pydantic v2 ---
if hasattr(target_cls, "model_fields"):
    try:
        from pydantic.fields import PydanticUndefinedType
        _pydantic_undef_types = (PydanticUndefinedType,)
    except ImportError:
        _pydantic_undef_types = ()

    def is_pydantic_undefined(v):
        if _pydantic_undef_types and isinstance(v, _pydantic_undef_types):
            return True
        # Fallback: string representation check
        return repr(v) == "PydanticUndefined"

    for field_name, field_info in target_cls.model_fields.items():
        ann = field_info.annotation
        t = type_str(ann) if ann is not None else ""
        default_val = field_info.default
        if is_pydantic_undefined(default_val):
            dflt = NEEDS_DEFAULT
        else:
            dflt = repr(default_val)
        desc = (field_info.description or "").strip() or NEEDS_DESC
        print("{}\t{}\t{}\t{}".format(field_name, t, dflt, desc))

# --- Pydantic v1 ---
elif hasattr(target_cls, "__fields__"):
    for field_name, field_obj in target_cls.__fields__.items():
        t = type_str(field_obj.outer_type_)
        default_val = field_obj.default
        # sentinel: None may be a real default in v1; check field_obj.required
        if getattr(field_obj, "required", False):
            dflt = NEEDS_DEFAULT
        elif default_val is None:
            dflt = "None"
        else:
            dflt = repr(default_val)
        # v1 Field description stored in field_obj.field_info.description
        desc_val = getattr(getattr(field_obj, "field_info", None), "description", None)
        desc = (desc_val or "").strip() or NEEDS_DESC
        print("{}\t{}\t{}\t{}".format(field_name, t, dflt, desc))

# --- dataclass ---
elif dataclasses.is_dataclass(target_cls):
    doc_attrs = parse_docstring_attrs(target_cls)
    for f in dataclasses.fields(target_cls):
        t = type_str(f.type) if not isinstance(f.type, str) else f.type
        if f.default is not dataclasses.MISSING:
            dflt = repr(f.default)
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            dflt = "factory"
        else:
            dflt = NEEDS_DEFAULT
        desc = doc_attrs.get(f.name, "").strip() or NEEDS_DESC
        print("{}\t{}\t{}\t{}".format(f.name, t, dflt, desc))

else:
    print("error: unsupported class type for {}".format(target_name), file=sys.stderr)
    sys.exit(3)
' "$PYTHON_FILE" "$CLASS_NAME"

PYTHON_EXIT=$?
exit $PYTHON_EXIT
