/**
 * @name TeaStore Resource-Based Dependencies
 * @description Captures resource references (URLs, file paths)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-resource-based
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

from StringLiteral s, Class c, string serviceName
where
  (s.getValue().matches("%http%") or s.getValue().matches("%/api/%")) and
  c = s.getEnclosingCallable().getDeclaringType() and
  c.fromSource() and
  serviceName = getMicroserviceFromPackage(c.getPackage())
select s, "kind=deps_resource_based|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|value=" + s.getValue()
