/**
 * @name Static Dependency Relations
 * @description Extracts dependency relationships among components (calls, type usage).
 * @kind problem
 * @id cpp/static-dependency-relations
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Element source, Element target, string dependencyType
where
  // Function Call Dependency
  (
    exists(FunctionCall call |
      source = call.getEnclosingFunction() and
      target = call.getTarget() and
      dependencyType = "Function call: " + source.(Function).getName() + " → " + target.(Function).getName()
    )
  )
  or
  // Type Instantiation/Usage Dependency (in local variables)
  (
    exists(LocalVariable v |
      source = v.getFunction() and
      target = v.getType().getUnspecifiedType().(Class) and
      dependencyType = "Type usage: " + source.(Function).getName() + " uses " + target.(Class).getName()
    )
  )
  or
  // Inheritance Dependency
  (
     exists(Class derived, Class base |
        source = derived and
        derived.getABaseClass() = base and
        target = base and
        dependencyType = "Inheritance: " + derived.getName() + " extends " + base.getName()
     )
  )
select source, dependencyType
