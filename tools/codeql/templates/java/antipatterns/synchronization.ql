/**
 * @name Synchronisation constructs (anti-pattern probe)
 * @description Synchronized methods, synchronized blocks, and explicit lock
 *              types. These are rough proxies for contention candidates —
 *              the analyzer agent must confirm via runtime / call-graph
 *              evidence before flagging a fix.
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

predicate inScope(RefType t) {
  t.getPackage().getName().matches("${PACKAGE_LIKE}") and t.fromSource()
}

from Element e, string kind, string serviceName, string fqn
where
  (
    exists(Method m |
      m = e and m.isSynchronized() and inScope(m.getDeclaringType()) and
      kind = "synchronized_method" and
      serviceName = getServiceFromPackage(m.getDeclaringType().getPackage()) and
      fqn = m.getDeclaringType().getQualifiedName() + "#" + m.getName()
    )
  )
  or
  (
    exists(SynchronizedStmt s |
      e = s and inScope(s.getEnclosingCallable().getDeclaringType()) and
      kind = "synchronized_block" and
      serviceName = getServiceFromPackage(
        s.getEnclosingCallable().getDeclaringType().getPackage()
      ) and
      fqn = s.getEnclosingCallable().getDeclaringType().getQualifiedName() +
            "#" + s.getEnclosingCallable().getName()
    )
  )
select e, "kind=" + kind + "|service=" + serviceName + "|fqn=" + fqn
