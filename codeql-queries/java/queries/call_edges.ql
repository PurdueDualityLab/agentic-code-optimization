/**
 * @name Call edges
 * @description Intra-service call graph edges.
 * @kind diagnostic
 * @id local/call-edges
 */
import java

from MethodCall call, Callable caller, Method callee
where
  caller = call.getEnclosingCallable() and
  callee = call.getMethod()
select
  call,
  call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() +
    " " + caller.getQualifiedName() + " -> " + callee.getQualifiedName() +
    " call_edge"
