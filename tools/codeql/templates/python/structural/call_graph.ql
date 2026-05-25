/**
 * @name Function-level call edges (structural, Python)
 * @description Within-benchmark call edges resolved by CodeQL points-to.
 *              Excludes self-calls.
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

from Call call, Function caller, Function callee, string fromSvc, string toSvc
where
  caller = call.getScope() and
  inScope(caller.getEnclosingModule()) and
  callee = call.getFunc().pointsTo().getOrigin().(FunctionExpr).getInnerScope() and
  inScope(callee.getEnclosingModule()) and
  caller != callee and
  fromSvc = getServiceFromPath(caller.getEnclosingModule().getFile()) and
  toSvc = getServiceFromPath(callee.getEnclosingModule().getFile())
select call, "kind=call_edge|from_service=" + fromSvc +
  "|to_service=" + toSvc +
  "|caller=" + caller.getQualifiedName() +
  "|callee=" + callee.getQualifiedName()
