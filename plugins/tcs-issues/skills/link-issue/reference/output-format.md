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
