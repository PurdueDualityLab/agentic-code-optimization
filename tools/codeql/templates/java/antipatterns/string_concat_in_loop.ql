/**
 * @name String concatenation inside loop (anti-pattern)
 * @description String += or "a" + b assignments to the same variable inside
 *              for/while/foreach. Quadratic in JVMs that don't fully
 *              optimise this pattern. Replaces the per-benchmark hardcoded
 *              version.
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

predicate inLoop(Stmt s) {
  s.getEnclosingStmt+() instanceof LoopStmt
}

from AssignAddExpr a, Method enclosing, string serviceName
where
  a.getDest().getType() instanceof TypeString and
  inLoop(a.getEnclosingStmt()) and
  enclosing = a.getEnclosingCallable() and
  enclosing.fromSource() and
  enclosing.getDeclaringType().getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(enclosing.getDeclaringType().getPackage())
select a, "kind=string_concat_in_loop|service=" + serviceName +
  "|in_method=" + enclosing.getDeclaringType().getQualifiedName() +
  "#" + enclosing.getName()
