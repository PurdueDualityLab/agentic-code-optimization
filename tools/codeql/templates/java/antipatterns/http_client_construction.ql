/**
 * @name HTTP client constructed in method body (anti-pattern)
 * @description HTTP client objects (HttpClient, OkHttpClient, RestTemplate)
 *              constructed inside a method body — a strong heuristic for
 *              "client created per request" which forces TCP / TLS
 *              handshakes and pool re-init. Field-level constructions are
 *              expected (singleton-style) and excluded.
 * @kind problem
 * @problem.severity recommendation
 * @id ${RULE_ID}
 */

import java

string getServiceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("${PACKAGE_LIKE}") and
    result = pkgName.regexpCapture("${PACKAGE_REGEX_CAPTURE}", 1)
  )
}

predicate isHttpClientType(RefType t) {
  t.hasQualifiedName("okhttp3", "OkHttpClient") or
  t.hasQualifiedName("org.apache.http.client", "HttpClient") or
  t.hasQualifiedName("org.apache.http.impl.client", "CloseableHttpClient") or
  t.hasQualifiedName("java.net.http", "HttpClient") or
  t.hasQualifiedName("org.springframework.web.client", "RestTemplate") or
  t.hasQualifiedName("org.springframework.web.reactive.function.client", "WebClient")
}

from ClassInstanceExpr ctor, Method enclosing, string serviceName
where
  isHttpClientType(ctor.getConstructedType()) and
  enclosing = ctor.getEnclosingCallable() and
  enclosing.fromSource() and
  enclosing.getDeclaringType().getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(enclosing.getDeclaringType().getPackage())
select ctor, "kind=http_client_ctor|service=" + serviceName +
  "|client_type=" + ctor.getConstructedType().getQualifiedName() +
  "|in_method=" + enclosing.getDeclaringType().getQualifiedName() +
  "#" + enclosing.getName()
