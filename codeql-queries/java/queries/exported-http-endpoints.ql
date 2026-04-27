/**
 * @name TeaStore Exported HTTP Endpoints
 * @description Captures endpoint-like classes by naming conventions
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/exported-http-endpoints
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  (c.getName().matches("%Endpoint") or c.getName().matches("%Rest") or
   c.getPackage().getName().matches("%.rest")) and
  c.fromSource()
select c, "kind=exported_http_endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()
