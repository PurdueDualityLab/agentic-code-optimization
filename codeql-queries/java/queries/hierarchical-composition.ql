/**
 * @name TeaStore Call-Based Dependencies
 * @description Captures method-to-method dependencies via method calls
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

predicate callBasedDependency(MethodCall call, string fromService, string fromMethod,
  string toService, string toMethod) {
  exists(Method caller, Method callee |
    call.getEnclosingCallable() = caller and
    call.getMethod() = callee and  // Changed from getTarget()
    caller.fromSource() and
    fromService = getMicroserviceFromPackage(caller.getDeclaringType().getPackage()) and
    toService = getMicroserviceFromPackage(callee.getDeclaringType().getPackage()) and
    fromMethod = caller.getQualifiedName() and
    toMethod = callee.getQualifiedName()
  )
}

from MethodCall call, string fromService, string fromMethod, string toService, string toMethod
where
  callBasedDependency(call, fromService, fromMethod, toService, toMethod)
select call, "kind=call_dependency|from_service=" + fromService + "|from_method=" + fromMethod +
  "|to_service=" + toService + "|to_method=" + toMethod +
  "|file=" + call.getLocation().getFile().getRelativePath() +
  "|start_line=" + call.getLocation().getStartLine() +
  "|end_line=" + call.getLocation().getEndLine()