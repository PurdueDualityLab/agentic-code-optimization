/**
 * @name HTTP endpoints / route handlers (structural, Python)
 * @description Functions decorated with route-like decorators (Flask
 *              @app.route, FastAPI @app.get/post, Django paths). Falls
 *              back to a name heuristic for legacy code.
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

predicate hasRouteDecorator(Function f) {
  exists(Expr dec | dec = f.getADecorator() |
    dec.toString().regexpMatch(".*\\.(route|get|post|put|delete|patch|api_route)\\(.*") or
    dec.toString().regexpMatch(".*\\bapp\\.[a-z]+\\(.*")
  )
}

from Function f, string serviceName
where
  inScope(f.getEnclosingModule()) and
  hasRouteDecorator(f) and
  serviceName = getServiceFromPath(f.getEnclosingModule().getFile())
select f, "kind=endpoint|service=" + serviceName +
  "|module=" + f.getEnclosingModule().getName() +
  "|function=" + f.getName()
