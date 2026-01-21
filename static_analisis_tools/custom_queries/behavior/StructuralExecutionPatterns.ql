/**
 * @name Structural Execution Patterns
 * @description Analyzes structural execution patterns such as loop nesting depth.
 * @kind problem
 * @id cpp/structural-execution-patterns
 * @problem.severity recommendation
 * @tags behavior-agent
 */

import cpp

from Loop s, int depth
where
  depth = count(Loop parent | parent = s.getParent+())
select s, "Loop nesting depth: " + depth.toString() + " (type: " + s.getAPrimaryQlClass() + ")"
