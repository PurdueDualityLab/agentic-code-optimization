/**
 * @name Static Evidence Linkage
 * @description Links behavior-level abstractions to matching static evidence.
 * @kind problem
 * @id cpp/static-evidence-linkage
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

from Element e, string description
where
  (
    e instanceof FunctionCall and
    description = "Function call: " + e.(FunctionCall).getTarget().getName()
  )
  or
  (
    e instanceof Loop and
    (
      (e instanceof WhileStmt and description = "While loop")
      or
      (e instanceof DoStmt and description = "Do-while loop")
      or
      (e instanceof ForStmt and description = "For loop")
      or
      (not e instanceof WhileStmt and not e instanceof DoStmt and not e instanceof ForStmt and description = "Loop construct")
    )
  )
  or
  (
    e instanceof IfStmt and
    description = "If statement"
  )
  or
  (
    e instanceof SwitchStmt and
    description = "Switch statement"
  )
  or
  (
    e instanceof ReturnStmt and
    description = "Return statement"
  )
select e, description + " at " + e.getLocation().toString()
