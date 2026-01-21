/**
 * @name Interprocedural Call Graphs
 * @description Builds call graph edges from entry points (main, handlers).
 * @kind problem
 * @id cpp/interprocedural-call-graphs
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

predicate isEntryPoint(Function f) {
  f.getName() = "main"
  or
  f.getDeclaringType().getName().matches("%Handler")
}

predicate reachableFrom(Function caller, Function callee) {
  exists(FunctionCall call |
    call.getEnclosingFunction() = caller and
    call.getTarget() = callee
  )
  or
  exists(Function mid |
    reachableFrom(caller, mid) and
    exists(FunctionCall call |
      call.getEnclosingFunction() = mid and
      call.getTarget() = callee
    )
  )
}

from FunctionCall call, Function caller, Function callee
where
  caller = call.getEnclosingFunction() and
  callee = call.getTarget() and
  (isEntryPoint(caller) or exists(Function ep | isEntryPoint(ep) and reachableFrom(ep, caller)))
select call, caller.getName() + " → " + callee.getName() + " (call graph edge)"
