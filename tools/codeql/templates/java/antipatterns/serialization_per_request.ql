/**
 * @name JSON serialiser allocated per call (anti-pattern)
 * @description ObjectMapper / Gson construction inside a method body. Both
 *              libraries do significant work in their constructors (reflection
 *              cache init); reusing one instance across calls is the
 *              canonical fix. Field-level constructions are excluded.
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

predicate isSerializerType(RefType t) {
  t.hasQualifiedName("com.fasterxml.jackson.databind", "ObjectMapper") or
  t.hasQualifiedName("com.google.gson", "Gson") or
  t.hasQualifiedName("com.google.gson", "GsonBuilder")
}

from ClassInstanceExpr ctor, Method enclosing, string serviceName
where
  isSerializerType(ctor.getConstructedType()) and
  enclosing = ctor.getEnclosingCallable() and
  enclosing.fromSource() and
  enclosing.getDeclaringType().getPackage().getName().matches("${PACKAGE_LIKE}") and
  serviceName = getServiceFromPackage(enclosing.getDeclaringType().getPackage())
select ctor, "kind=serializer_ctor|service=" + serviceName +
  "|serializer=" + ctor.getConstructedType().getQualifiedName() +
  "|in_method=" + enclosing.getDeclaringType().getQualifiedName() +
  "#" + enclosing.getName()
