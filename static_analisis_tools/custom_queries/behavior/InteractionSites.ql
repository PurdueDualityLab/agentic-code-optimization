/**
 * @name Interaction Sites
 * @description Detects interaction sites with external systems (Redis, MongoDB, etc.).
 * @kind problem
 * @id cpp/interaction-sites
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

from FunctionCall call, string systemType
where
  (
    call.getTarget().getName().matches("%redis%") and
    systemType = "Redis operation: " + call.getTarget().getName()
  )
  or
  (
    call.getTarget().getName().matches("%mongo%") and
    systemType = "MongoDB operation: " + call.getTarget().getName()
  )
  or
  (
    call.getTarget().getName().matches("%memcache%") and
    systemType = "Memcached operation: " + call.getTarget().getName()
  )
  or
  (
    (
      call.getTarget().getName().matches("%Client") or
      call.getTarget().getName().matches("%Service")
    ) and
    systemType = "RPC call: " + call.getTarget().getName()
  )
select call, systemType
