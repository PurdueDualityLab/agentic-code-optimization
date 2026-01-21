/**
 * @name Database call in loop
 * @description Performing database operations commonly inside a loop can lead to N+1 performance issues.
 * @kind problem
 * @problem.severity warning
 * @id cpp/performance/db-call-in-loop
 * @tags performance
 */

import cpp

from Loop l, FunctionCall fc
where
  l.getStmt().getAChild*() = fc.getEnclosingStmt() and
  (
    // MongoDB: Flag query initiation/writes, but NOT cursor iteration (likely just reading results)
    (
      fc.getTarget().getName().matches("mongoc_%") and
      not fc.getTarget().getName() = "mongoc_cursor_next" and
      not fc.getTarget().getName() = "mongoc_cursor_destroy" and
      not fc.getTarget().getName() = "mongoc_client_pool_push" and
      not fc.getTarget().getName() = "bson_destroy"
    )
    or
    // Redis: Flag commands execution
    (
      (fc.getTarget().getDeclaringType().getName().matches("Redis%") or fc.getTarget().getName().matches("redis_%")) and
      not fc.getTarget().getName() = "pipeline" // Creating pipeline in loop *might* be ok if exec is later, but usually bad. Let's keep it tight.
    )
    or
    // Generic ClientPool usage usually implies RPC/DB
    fc.getTarget().getDeclaringType().getName().matches("ClientPool%")
  )
select fc, "Database/RPC call inside loop (potential N+1 problem)."
