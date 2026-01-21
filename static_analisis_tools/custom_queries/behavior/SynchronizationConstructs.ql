/**
 * @name Synchronization Constructs
 * @description Identifies synchronization primitives (mutex, locks, condition variables).
 * @kind problem
 * @id cpp/synchronization-constructs
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

from Variable v, string syncType
where
  (
    v.getType().getName().matches("%mutex%") and
    syncType = "Mutex: " + v.getName()
  )
  or
  (
    v.getType().getName().matches("%lock_guard%") and
    syncType = "Lock guard: " + v.getName()
  )
  or
  (
    v.getType().getName().matches("%unique_lock%") and
    syncType = "Unique lock: " + v.getName()
  )
  or
  (
    v.getType().getName().matches("%condition_variable%") and
    syncType = "Condition variable: " + v.getName()
  )
select v, syncType + " (type: " + v.getType().getName() + ")"
