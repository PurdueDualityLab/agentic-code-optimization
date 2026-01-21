/**
 * @name Exported Interfaces
 * @description Identifies exported entry points like Thrift handlers and main functions.
 * @kind problem
 * @id cpp/exported-interfaces
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Function f, string interfaceType
where
  (
    f.getName() = "main" and
    interfaceType = "Entry point: main function"
  )
  or
  (
    exists(MemberFunction mf |
      mf = f and
      mf.getDeclaringType().getName().matches("%Handler") and
      mf.isPublic() and
      interfaceType = "Public handler method: " + mf.getDeclaringType().getName() + "::" + mf.getName()
    )
  )
select f, interfaceType
