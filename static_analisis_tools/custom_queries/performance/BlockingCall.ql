/**
 * @name Blocking thread sleep
 * @description Explicitly sleeping a thread blocks execution and reduces throughput in microservices.
 * @kind problem
 * @problem.severity warning
 * @id cpp/performance/blocking-sleep
 * @tags performance
 */

import cpp

from FunctionCall fc, Function enclosing
where
  fc.getEnclosingFunction() = enclosing and
  (
    fc.getTarget().getQualifiedName().matches("%sleep%") or
    fc.getTarget().getName() = "usleep" or
    fc.getTarget().getName() = "sleep"
  ) and
  // Ignore startup/init functions where blocking is acceptable
  not enclosing.getName() = "main" and
  not enclosing.getName().matches("Init%") and
  not enclosing.getName().matches("Setup%")
select fc, "Blocking sleep call detected in request path."
