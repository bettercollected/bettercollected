- Admin service: the portal's database role can delete a service heartbeat only when it is older than
  7 days and its service has reported nothing newer, which is exactly what the retention loop removes
  (a database trigger, admin migration 0019). A stolen portal credential can no longer erase live
  heartbeats, which the keyset checks and the integrity monitor read.
