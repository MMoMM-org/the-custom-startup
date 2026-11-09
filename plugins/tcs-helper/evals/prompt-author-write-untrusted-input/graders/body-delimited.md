---
type: regex
target: {source: file, path: prompts/triage.md}
pattern: '<([A-Za-z][\w-]*)[^>\n]*>(?:(?!</\1>)[\s\S]){0,400}\{\{\s*issue_body\s*\}\}(?:(?!</\1>)[\s\S]){0,400}</\1>|```[^\n]*\n(?:(?!```)[\s\S]){0,400}\{\{\s*issue_body\s*\}\}(?:(?!```)[\s\S]){0,400}```|\b(BEGIN|START)\b[^\n]*\n[\s\S]{0,400}?\{\{\s*issue_body\s*\}\}[\s\S]{0,400}?\bEND\b'
weight: 1
---
The `{{issue_body}}` placeholder sits inside a delimiter pair: an XML-style tag pair, a code fence, or
BEGIN/START and END marker lines (PA-15). Any of the three passes; the tag name does not matter.
