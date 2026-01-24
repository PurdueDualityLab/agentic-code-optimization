/**
 * @name TeaStore Interaction Sites (Aggregated)
 * @description Captures external calls and database access sites aggregated by class
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/interaction-sites
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

predicate isDbPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    (
      pkgName.matches("java.sql%") or
      pkgName.matches("javax.sql%") or
      pkgName.matches("javax.persistence%") or
      pkgName.matches("org.hibernate%") or
      pkgName.matches("org.springframework.jdbc%") or
      pkgName.matches("org.springframework.data%")
    )
  )
}

from Class c, string serviceName, string targetPackage, string interactionType
where
  c.fromSource() and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  exists(MethodCall call, Package targetPkg |
    call.getEnclosingCallable().getDeclaringType() = c and
    targetPkg = call.getMethod().getDeclaringType().getPackage() and
    targetPackage = targetPkg.getName() and
    not targetPackage.matches("tools.descartes.teastore.%") and
    (
      (isDbPackage(targetPkg) and interactionType = "db_access") or
      (not isDbPackage(targetPkg) and interactionType = "external_call")
    )
  )
select c, "kind=interaction_site|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|type=" + interactionType +
  "|target_package=" + targetPackage
