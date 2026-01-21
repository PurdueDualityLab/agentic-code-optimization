/**
 * @name Component Responsibilities
 * @description Infers component responsibilities based on interactions with external systems.
 * @kind problem
 * @id cpp/component-responsibilities
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Function f, string responsibility
where
  (
    exists(FunctionCall call |
      call.getEnclosingFunction() = f and
      call.getTarget().getName().matches("%redis%") and
      responsibility = "Redis interaction in " + f.getName()
    )
  )
  or
  (
    exists(FunctionCall call |
      call.getEnclosingFunction() = f and
      call.getTarget().getName().matches("%mongo%") and
      responsibility = "MongoDB interaction in " + f.getName()
    )
  )
  or
  (
    exists(FunctionCall call |
      call.getEnclosingFunction() = f and
      (
        call.getTarget().getName().matches("%Client") or
        call.getTarget().getName().matches("%Service")
      ) and
      responsibility = "RPC/Service interaction in " + f.getName()
    )
  )
select f, responsibility
