/**
 * @name Service-like classes (structural, Python)
 * @description Classes whose names indicate a service or handler role
 *              within the benchmark scope. Path filter is parameterised
 *              by the fingerprint.
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

predicate isServiceLike(Class c) {
  c.getName().matches("%Service") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Controller") or
  c.getName().matches("%View")
}

from Class c, string serviceName
where
  inScope(c.getEnclosingModule()) and
  isServiceLike(c) and
  serviceName = getServiceFromPath(c.getEnclosingModule().getFile())
select c, "kind=service|service=" + serviceName +
  "|module=" + c.getEnclosingModule().getName() +
  "|name=" + c.getName()
