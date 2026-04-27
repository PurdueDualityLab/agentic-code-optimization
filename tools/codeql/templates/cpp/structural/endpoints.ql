/**
 * @name Service handler / endpoint methods (structural, C++)
 * @description Functions that look like RPC handlers or HTTP request entry
 *              points. Heuristic: methods on a *Handler class with names
 *              like Handle*/Process*/On*. Apache Thrift / gRPC follow this
 *              convention.
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

predicate handlerNamePattern(Function fn) {
  fn.getName().matches("Handle%") or
  fn.getName().matches("handle_%") or
  fn.getName().matches("Process%") or
  fn.getName().matches("On%") or
  fn.getName().matches("Serve%") or
  fn.getName().matches("Reply%")
}

from MemberFunction fn, Class c, string serviceName
where
  fn.fromSource() and
  inScope(fn) and
  c = fn.getDeclaringType() and
  c.getName().matches("%Handler") and
  handlerNamePattern(fn) and
  serviceName = getServiceFromPath(fn.getFile())
select fn, "kind=endpoint|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|method=" + fn.getName()
