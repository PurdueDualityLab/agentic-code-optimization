/**
 * @name TeaStore Rooted Call Graph (Class Level)
 * @description Captures interprocedural call graph edges at class level within TeaStore packages
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/rooted-call-graph-depth5
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

from Class callerClass, Class calleeClass, string fromService, string toService
where
  exists(MethodCall call |
    call.getEnclosingCallable().getDeclaringType() = callerClass and
    call.getMethod().getDeclaringType() = calleeClass and
    callerClass.getPackage().getName().matches("tools.descartes.teastore.%") and
    calleeClass.getPackage().getName().matches("tools.descartes.teastore.%") and
    fromService = getMicroserviceFromPackage(callerClass.getPackage()) and
    toService = getMicroserviceFromPackage(calleeClass.getPackage()) and
    callerClass != calleeClass
  )
select callerClass, "kind=call_graph_edge|from_service=" + fromService +
  "|caller=" + callerClass.getQualifiedName() +
  "|to_service=" + toService +
  "|callee=" + calleeClass.getQualifiedName()
