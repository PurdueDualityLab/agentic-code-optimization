/**
 * @name Database access sites (anti-pattern probe)
 * @description Methods that issue calls into JDBC / JPA / Hibernate APIs.
 *              Surface for the analyzer agent to investigate N+1 queries,
 *              missing prepared statements, batching, and transaction scope.
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

predicate isDbPackage(Package p) {
  p.getName().matches("java.sql%") or
  p.getName().matches("javax.sql%") or
  p.getName().matches("javax.persistence%") or
  p.getName().matches("jakarta.persistence%") or
  p.getName().matches("org.hibernate%") or
  p.getName().matches("org.springframework.jdbc%") or
  p.getName().matches("org.springframework.data%")
}

from MethodCall call, Method enclosing, string serviceName, string targetPkg
where
  enclosing = call.getEnclosingCallable() and
  enclosing.fromSource() and
  enclosing.getDeclaringType().getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(enclosing.getDeclaringType().getPackage()) and
  isDbPackage(call.getMethod().getDeclaringType().getPackage()) and
  targetPkg = call.getMethod().getDeclaringType().getPackage().getName()
select call, "kind=db_access|service=" + serviceName +
  "|target_pkg=" + targetPkg +
  "|target_method=" + call.getMethod().getName() +
  "|in_method=" + enclosing.getDeclaringType().getQualifiedName() +
  "#" + enclosing.getName()
