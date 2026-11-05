---
type: regex
target: last_message
pattern: '^(?=[\s\S]*OUTCOME:)(?=[\s\S]*SHIPPED)(?=[\s\S]*PARKED)(?=[\s\S]*NEED_INPUT)'
weight: 2
---
The draft brief requests the OUTCOME line with all three values step 6 branches on: SHIPPED, PARKED
and NEED_INPUT.
