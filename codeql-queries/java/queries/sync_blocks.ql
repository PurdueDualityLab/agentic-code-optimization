/**
 * @name Synchronized blocks
 * @description Synchronized statements inside methods.
 * @kind diagnostic
 * @id local/sync-blocks
 */
import java

from SynchronizedStmt s, Callable c
where c = s.getEnclosingCallable()
select
  s,
  s.getFile().getRelativePath() + ":" + s.getLocation().getStartLine().toString() +
    " " + c.getQualifiedName() + " synchronized_block"
