/**
 * @name String concatenation in a loop (anti-pattern, Python)
 * @description `s += chunk` inside a for/while body. Use list+join or
 *              io.StringIO instead.
 * @kind problem
 * @problem.severity recommendation
 * @id ${RULE_ID}
 */

import python

string getServiceFromPath(File f) {
  exists(string p |
    p = f.getRelativePath() and
    p.matches("${PATH_LIKE}") and
    result = p.regexpCapture("${PATH_REGEX_CAPTURE}", 1)
  )
}

predicate inScope(Module m) {
  m.getFile().getRelativePath().matches("${PATH_LIKE}")
}

predicate inLoop(Stmt s) {
  s.getParent+() instanceof For or s.getParent+() instanceof While
}

from AugAssign aug, Function enclosing, string serviceName
where
  enclosing = aug.getScope() and
  inScope(enclosing.getEnclosingModule()) and
  aug.getOp() instanceof Add and
  inLoop(aug) and
  serviceName = getServiceFromPath(enclosing.getEnclosingModule().getFile())
select aug, "kind=aug_assign_in_loop|service=" + serviceName +
  "|in_function=" + enclosing.getQualifiedName()
