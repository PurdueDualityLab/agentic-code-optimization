/**
 * @name Service-like classes (structural)
 * @description Identifies classes whose names/packages indicate service or
 *              entry-point roles within the benchmark scope. The package
 *              filter is parameterised by the fingerprint so the same query
 *              works for any Java codebase.
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

predicate isServiceLike(Class c) {
  c.getName().matches("%Service") or
  c.getName().matches("%Servlet") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Application") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Registry")
}

from Class c, string serviceName
where
  c.fromSource() and
  c.getPackage().getName().matches("${PACKAGE_LIKE}") and
  isServiceLike(c) and
  serviceName = getServiceFromPackage(c.getPackage())
select c, "kind=service|service=" + serviceName + "|fqn=" + c.getQualifiedName()
