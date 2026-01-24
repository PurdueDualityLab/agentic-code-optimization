/**
 * @name TeaStore Synchronization Constructs
 * @description Captures synchronized blocks and methods
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/synchronization-constructs
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

from Method m, string serviceName
where
  m.isSynchronized() and
  m.fromSource() and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage())
select m, "kind=synchronization_construct|service=" + serviceName +
  "|type=method|class=" + m.getDeclaringType().getQualifiedName() +
  "|method=" + m.getName()
