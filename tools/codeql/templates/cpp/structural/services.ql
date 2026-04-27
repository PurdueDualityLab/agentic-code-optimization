/**
 * @name Service-like classes (structural, C++)
 * @description Classes/structs whose names indicate service or handler roles
 *              within the benchmark scope. Path filter is parameterised by
 *              the fingerprint.
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

predicate inScope(Class c) {
  c.getFile().getRelativePath().matches("${PATH_LIKE}")
}

predicate isServiceLike(Class c) {
  c.getName().matches("%Service%") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Server") or
  c.getName().matches("%Client") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Repository")
}

from Class c, string serviceName
where
  c.fromSource() and
  inScope(c) and
  isServiceLike(c) and
  serviceName = getServiceFromPath(c.getFile())
select c, "kind=service|service=" + serviceName + "|fqn=" + c.getQualifiedName()
