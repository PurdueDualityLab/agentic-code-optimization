/**
 * @name TeaStore Exported Public API
 * @description Captures public methods exposed by services
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

from Method m, string serviceName
where
  m.isPublic() and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
  m.fromSource()
select m, "kind=exported_public_api|service=" + serviceName + "|method_fqn=" + m.getQualifiedName() +
  "|file=" + m.getLocation().getFile().getRelativePath() +
  "|start_line=" + m.getLocation().getStartLine() +
  "|end_line=" + m.getLocation().getEndLine()
