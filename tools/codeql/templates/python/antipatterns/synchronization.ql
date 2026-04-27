/**
 * @name Lock acquisition sites (anti-pattern probe, Python)
 * @description threading.Lock / RLock / Semaphore .acquire() and
 *              `with lock:` context-manager entries inside in-scope code.
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

predicate isLockAcquire(Call c) {
  c.getFunc().(Attribute).getName() = "acquire" or
  c.getFunc().(Attribute).getName() = "__enter__"
}

from Call call, Function enclosing, string serviceName
where
  enclosing = call.getScope() and
  inScope(enclosing.getEnclosingModule()) and
  isLockAcquire(call) and
  serviceName = getServiceFromPath(enclosing.getEnclosingModule().getFile())
select call, "kind=lock_acquire|service=" + serviceName +
  "|in_function=" + enclosing.getQualifiedName()
