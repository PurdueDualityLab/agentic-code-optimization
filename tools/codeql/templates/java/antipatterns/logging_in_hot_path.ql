/**
 * @name Logging with eager string construction (anti-pattern)
 * @description log4j / SLF4J calls with string concatenation in the message
 *              argument. The string is built unconditionally even when the
 *              level is disabled. Fix is parameterised logging.
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

predicate isLoggerCall(MethodCall call) {
  exists(RefType t | t = call.getMethod().getDeclaringType() |
    t.getQualifiedName() = "org.slf4j.Logger" or
    t.getQualifiedName() = "org.apache.log4j.Logger" or
    t.getQualifiedName() = "org.apache.logging.log4j.Logger" or
    t.getQualifiedName() = "java.util.logging.Logger"
  ) and
  call.getMethod().getName().regexpMatch("trace|debug|info|warn|error|fine|finer|finest")
}

from MethodCall call, AddExpr concatExpr, string serviceName, Method enclosing
where
  isLoggerCall(call) and
  concatExpr = call.getAnArgument() and
  concatExpr.getType() instanceof TypeString and
  enclosing = call.getEnclosingCallable() and
  enclosing.fromSource() and
  enclosing.getDeclaringType().getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(enclosing.getDeclaringType().getPackage())
select call, "kind=eager_log_concat|service=" + serviceName +
  "|level=" + call.getMethod().getName() +
  "|in_method=" + enclosing.getDeclaringType().getQualifiedName() +
  "#" + enclosing.getName()
