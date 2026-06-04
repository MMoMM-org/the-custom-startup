# Output Format — issue

One block per mode. Keep it scannable: one item per line, omit fields that are unset.

## create

```
✅ Created <owner>/<repo>#<number> — <title>
   URL:    <url>
   Labels: <label, label> | none
   Board:  <project name> · status <Todo> | not on a board
   Epic:   run /link-issue link <number> under <epic> | none
```

## list

```
📋 <owner>/<repo> — <state> issues (<count>)
   #<number>  <title>   [<labels>]   @<assignee|—>
   #<number>  <title>   [<labels>]   @<assignee|—>
```

## close

```
🔒 Closed <owner>/<repo>#<number> — <title>
   Comment: <comment> | none
```

## comment

```
💬 Commented on <owner>/<repo>#<number>
   <comment URL>
```
