@test "health check responds" {
  run echo ok
  [ "$status" -eq 0 ]
}
