/**
 * @name Control Flow Structure
 * @description Reports control-flow structures like loops, conditionals, and switches.
 * @kind problem
 * @id cpp/control-flow-structure
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

from Stmt s, string structureType
where
  (
    s instanceof IfStmt and
    structureType = "Conditional: if statement"
  )
  or
  (
    s instanceof WhileStmt and
    structureType = "Loop: while"
  )
  or
  (
    s instanceof DoStmt and
    structureType = "Loop: do-while"
  )
  or
  (
    s instanceof ForStmt and
    structureType = "Loop: for"
  )
  or
  (
    s instanceof SwitchStmt and
    structureType = "Conditional: switch statement"
  )
select s, structureType
