/**
 * @name String concatenation in loop
 * @description Concatenating strings in a loop can be inefficient (O(n^2)).
 * @kind problem
 * @problem.severity warning
 * @id cpp/performance/string-concatenation-in-loop
 * @tags performance
 */

import cpp

from Loop l, FunctionCall fc
where
  l.getStmt().getAChild*() = fc.getEnclosingStmt() and
  (
    fc.getTarget().getName() = "operator+" or
    fc.getTarget().getName() = "operator+=" or
    fc.getTarget().getName() = "append" or 
    fc.getTarget().getName() = "to_string"
  ) and
  // Focus on std::string
  fc.getTarget().getDeclaringType().getName().matches("%string%")
select fc, "Potential string allocation/concatenation inside loop."
