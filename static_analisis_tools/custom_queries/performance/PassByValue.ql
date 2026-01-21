/**
 * @name Expensive type passed by value
 * @description Passing large types (like containers) by value can cause unnecessary copying. Use const reference instead.
 * @kind problem
 * @problem.severity recommendation
 * @id cpp/performance/pass-by-value
 * @tags performance
 */

import cpp

// Define what we consider "expensive"
predicate isExpensiveType(Type t) {
  t.getName().matches("vector<%") or
  t.getName().matches("map<%") or
  t.getName().matches("unordered_map<%") or
  t.getName().matches("set<%") or
  t.getName().matches("deque<%") or
  t.getName().matches("list<%") or
  // String is debatable depending on SSO, but generally ref is safer for perf
  t.getName() = "string"
}

from Function f, Parameter p
where
  f.getAParameter() = p and
  not p.getType() instanceof ReferenceType and
  not p.getType() instanceof PointerType and
  isExpensiveType(p.getType().getUnderlyingType()) and
  // Exclude main, operators, and move constructors/assignments (which take value or rval)
  not f.getName() = "main" and
  not f.isCompilerGenerated() and
  not f.getName().matches("operator%") and
  f.hasDefinition()
select p, "Variable of type " + p.getType().getName() + " is passed by value. Consider using const reference."
