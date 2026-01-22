/**
 * @name TeaStore Exported Public API (Entry Points Only)
 * @description Captures only public entry point methods (endpoints, services)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/exported-public-api
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

predicate isEntryPointClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Service") or
  c.getPackage().getName().matches("%.rest") or
  c.getPackage().getName().matches("%.servlet")
}

from Method m, string serviceName
where
  m.isPublic() and
  isEntryPointClass(m.getDeclaringType()) and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
  m.fromSource()
select m, "kind=exported_public_api|service=" + serviceName +
  "|class=" + m.getDeclaringType().getQualifiedName() +
  "|method=" + m.getName() +
  "|signature=" + m.getStringSignature()
