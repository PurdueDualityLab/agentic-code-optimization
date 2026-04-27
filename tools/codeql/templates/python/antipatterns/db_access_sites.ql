/**
 * @name Database access sites (anti-pattern probe, Python)
 * @description Calls into SQLAlchemy session / Django ORM / sqlite3 cursor.
 *              Surface for the analyzer to investigate N+1 queries and
 *              transaction scope.
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

predicate isDbCall(Call c) {
  exists(string n | n = c.getFunc().(Attribute).getName() |
    n = "execute" or n = "executemany" or n = "fetchall" or n = "fetchone" or
    n = "filter" or n = "all" or n = "one" or n = "first" or
    n = "query" or n = "get" or n = "save" or n = "create" or n = "update" or
    n = "objects"
  )
}

from Call call, Function enclosing, string serviceName
where
  enclosing = call.getScope() and
  inScope(enclosing.getEnclosingModule()) and
  isDbCall(call) and
  serviceName = getServiceFromPath(enclosing.getEnclosingModule().getFile())
select call, "kind=db_call|service=" + serviceName +
  "|in_function=" + enclosing.getQualifiedName() +
  "|method=" + call.getFunc().(Attribute).getName()
