/**
 * @name Redundant map lookup
 * @description Checking if a key exists and then retrieving it performs two lookups. Use find() instead.
 * @kind problem
 * @problem.severity warning
 * @id cpp/performance/redundant-map-lookup
 * @tags performance
 */

import cpp

from IfStmt i, FunctionCall check, FunctionCall retrieval
where
  // The structure is if (check) { retrieval }
  check = i.getCondition().getAChild*() and
  retrieval.getEnclosingStmt().getParentStmt*() = i.getThen() and
  
  // The check is likely map.count(k) or map.find(k) != end
  (check.getTarget().getName() = "count" or check.getTarget().getName() = "find") and
  
  // The retrieval is map.at(k) or map[k]
  (retrieval.getTarget().getName() = "at" or retrieval.getTarget().getName() = "operator[]") and
  
  // They operate on the same variable (simplification)
  check.getQualifier() = retrieval.getQualifier()

select i, "Potential double map lookup. Use iterator from find() to avoid second lookup."
