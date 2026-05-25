/**
 * @name HTTP / RPC endpoints (structural)
 * @description Endpoints reachable from outside the JVM: servlets, JAX-RS
 *              resources, Spring controllers. Annotation- *and* name-based
 *              detection so the query keeps working when annotations are
 *              missing (e.g. legacy servlets).
 * @kind problem
 * @problem.severity recommendation
 * @id ${RULE_ID}
 */

import java

string getServiceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("${PACKAGE_LIKE}") and
    result = pkgName.regexpCapture("${PACKAGE_REGEX_CAPTURE}", 1)
  )
}

predicate hasEndpointAnnotation(Class c) {
  exists(Annotation a |
    a = c.getAnAnnotation() and
    (
      a.getType().getName() = "Path" or
      a.getType().getName() = "RestController" or
      a.getType().getName() = "Controller" or
      a.getType().getName() = "RequestMapping"
    )
  )
}

predicate hasEndpointName(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Resource") or
  c.getPackage().getName().matches("%.rest") or
  c.getPackage().getName().matches("%.servlet") or
  c.getPackage().getName().matches("%.api")
}

from Class c, string serviceName, string detector
where
  c.fromSource() and
  c.getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(c.getPackage()) and
  (
    (hasEndpointAnnotation(c) and detector = "annotation") or
    (hasEndpointName(c) and detector = "name")
  )
select c, "kind=endpoint|service=" + serviceName + "|fqn=" + c.getQualifiedName() +
  "|detected_by=" + detector
