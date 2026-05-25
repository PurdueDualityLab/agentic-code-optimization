/**
 * @name Function-level call edges (structural, C++)
 * @description Within-benchmark function call edges. Excludes self-calls
 *              and stdlib targets. Aggregating to declaring class on both
 *              sides keeps SARIF tractable.
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

predicate inScope(File f) {
  f.getRelativePath().matches("${PATH_LIKE}")
}

from FunctionCall call, Function caller, Function callee, string fromSvc, string toSvc
where
  caller = call.getEnclosingFunction() and
  callee = call.getTarget() and
  caller.fromSource() and callee.fromSource() and
  inScope(caller.getFile()) and inScope(callee.getFile()) and
  caller != callee and
  fromSvc = getServiceFromPath(caller.getFile()) and
  toSvc = getServiceFromPath(callee.getFile())
select call, "kind=call_edge|from_service=" + fromSvc +
  "|to_service=" + toSvc +
  "|caller=" + caller.getQualifiedName() +
  "|callee=" + callee.getQualifiedName()
