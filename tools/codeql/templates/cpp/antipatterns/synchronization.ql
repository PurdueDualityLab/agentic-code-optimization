/**
 * @name Synchronisation constructs (anti-pattern probe, C++)
 * @description Local lock acquisitions (std::lock_guard, std::unique_lock,
 *              std::scoped_lock) inside in-scope functions. Together with
 *              the call graph these locate contention candidates.
 * @kind problem
 * @problem.severity recommendation
 * @id ${RULE_ID}
 */

import cpp

string getServiceFromPath(File f) {
  exists(string p |
    p = f.getRelativePath() and
    p.matches("${PATH_LIKE}") and
    result = p.regexpCapture("${PATH_REGEX_CAPTURE}", 1)
  )
}

predicate inScope(Function fn) {
  fn.getFile().getRelativePath().matches("${PATH_LIKE}")
}

predicate isLockType(Type t) {
  t.getName().matches("lock_guard%") or
  t.getName().matches("unique_lock%") or
  t.getName().matches("scoped_lock%") or
  t.getName().matches("shared_lock%")
}

from Variable v, Function fn, string serviceName
where
  fn.fromSource() and
  inScope(fn) and
  v.getFunction() = fn and
  isLockType(v.getType().getUnspecifiedType()) and
  serviceName = getServiceFromPath(fn.getFile())
select v, "kind=lock_acquisition|service=" + serviceName +
  "|lock_type=" + v.getType().getName() +
  "|in_function=" + fn.getQualifiedName()
