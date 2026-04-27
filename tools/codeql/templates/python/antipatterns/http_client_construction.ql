/**
 * @name HTTP client / Session constructed in function body (anti-pattern, Python)
 * @description requests.Session() / aiohttp.ClientSession() / httpx.Client()
 *              constructed inside a function rather than reused at module
 *              scope or via dependency injection — defeats connection
 *              pooling.
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

predicate isHttpClientCtor(Call c) {
  exists(string s | s = c.getFunc().toString() |
    s.matches("%requests.Session%") or
    s.matches("%aiohttp.ClientSession%") or
    s.matches("%httpx.Client%") or
    s.matches("%httpx.AsyncClient%") or
    s.matches("%urllib3.PoolManager%")
  )
}

from Call call, Function enclosing, string serviceName
where
  enclosing = call.getScope() and
  inScope(enclosing.getEnclosingModule()) and
  isHttpClientCtor(call) and
  serviceName = getServiceFromPath(enclosing.getEnclosingModule().getFile())
select call, "kind=http_client_ctor|service=" + serviceName +
  "|in_function=" + enclosing.getQualifiedName() +
  "|expr=" + call.getFunc().toString()
