/**
 * @name Class-level call graph (structural)
 * @description Class-to-class call edges within the benchmark scope. Excludes
 *              self-calls (uninteresting at this granularity). Aggregating at
 *              class level keeps SARIF output tractable on large monorepos.
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

from Class caller, Class callee, string fromService, string toService
where
  exists(MethodCall call |
    call.getEnclosingCallable().getDeclaringType() = caller and
    call.getMethod().getDeclaringType() = callee
  ) and
  caller.fromSource() and
  caller.getPackage().getName().matches("${PACKAGE_LIKE}") and
  callee.getPackage().getName().matches("${PACKAGE_LIKE}") and
  caller != callee and
  fromService = getServiceFromPackage(caller.getPackage()) and
  toService = getServiceFromPackage(callee.getPackage())
select caller, "kind=call_edge|from_service=" + fromService +
  "|to_service=" + toService +
  "|caller=" + caller.getQualifiedName() +
  "|callee=" + callee.getQualifiedName()
