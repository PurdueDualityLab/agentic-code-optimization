/**
 * @name TeaStore Call-Based Dependencies (Aggregated)
 * @description Captures class-to-class dependencies via method calls
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-call-based
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

from Class fromClass, Class toClass, string fromService, string toService
where
  exists(MethodCall call |
    call.getEnclosingCallable().getDeclaringType() = fromClass and
    call.getMethod().getDeclaringType() = toClass and
    fromClass.fromSource() and
    fromService = getMicroserviceFromPackage(fromClass.getPackage()) and
    toService = getMicroserviceFromPackage(toClass.getPackage()) and
    fromClass != toClass  // Exclude self-calls
  )
select fromClass, "kind=call_dependency|from_service=" + fromService +
  "|from_class=" + fromClass.getQualifiedName() +
  "|to_service=" + toService +
  "|to_class=" + toClass.getQualifiedName()
