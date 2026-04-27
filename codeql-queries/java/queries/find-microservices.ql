/**
 * @name Identify TeaStore Microservices (Simple)
 * @description Finds microservices by analyzing package structure
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/find-microservices-simple
 */

import java

/**
 * Extract microservice name from package
 */
string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

/**
 * Check if a class is a significant microservice component
 */
predicate isSignificantComponent(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Application") or
  c.getName().matches("%Registry") or
  c.getPackage().getName().matches("%.rest") or
  c.getPackage().getName().matches("%.servlet")
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  isSignificantComponent(c) and
  c.fromSource()
select c, "kind=microservice|service=" + serviceName + "|component_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()
