/**
 * @name HTTP endpoints (Spring)
 * @description Spring MVC endpoint methods.
 * @kind diagnostic
 * @id local/endpoints
 */
import java

predicate isSpringMapping(Annotation a) {
  a.getType().getName() = "RequestMapping" or
  a.getType().getName() = "GetMapping" or
  a.getType().getName() = "PostMapping" or
  a.getType().getName() = "PutMapping" or
  a.getType().getName() = "DeleteMapping" or
  a.getType().getName() = "PatchMapping"
}

from Method m, Annotation a
where
  a = m.getAnAnnotation() and
  isSpringMapping(a)
select
  m,
  m.getFile().getRelativePath() + ":" + m.getLocation().getStartLine().toString() +
    " " + m.getDeclaringType().getQualifiedName() + "." + m.getName() +
    " [" + a.getType().getName() + "] endpoint"
