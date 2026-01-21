/**
 * @name Shared pointer passed by value
 * @description Passing std::shared_ptr by value invokes atomic operations. Use const reference unless ownership sharing is intended.
 * @kind problem
 * @problem.severity recommendation
 * @id cpp/performance/shared-ptr-by-value
 * @tags performance
 */

import cpp

from Function f, Parameter p
where
  f.getAParameter() = p and
  p.getType().getName().matches("shared_ptr<%") and
  not p.getType() instanceof ReferenceType and
  not f.getName() = "main" and
  not f.isCompilerGenerated() and
  not f.getName().matches("operator%") and
  f.hasDefinition()
select p, "std::shared_ptr passed by value. This causes atomic ops overhead."
