# Output Format — link-issue

One block per mode. Keep it scannable: one issue per line.

## link

```
🔗 Linked <owner>/<repo>#<child> — <child title>
   as a sub-issue of #<parent> — <parent title>
```

## unlink

```
✂️  Unlinked <owner>/<repo>#<child> — <child title>
   from parent #<parent> — <parent title>
```

## list

```
🗂  <owner>/<repo>#<number> — <title>
   Parent:   #<parent> — <parent title> (<state>) | none
   Children: (<count>)
     #<number>  <title>  (<state>)
     #<number>  <title>  (<state>)
```

## sync

Preview (before confirm) — group by epic, then list anomalies:

```
🔁 <owner>/<repo> — <N> link(s) to create
   Epic #<epic> — <epic title>
     #<child>  <child title>
     #<child>  <child title>
   ⚠ Anomalies (<M>) — review manually
     #<child> → #<epic>: <reason>
```

Result (after apply):

```
✅ Synced <owner>/<repo> — linked <N>/<N>
   #<child> → child of #<epic>
   <failures, if any>
```
