/**
 * @name Synchronized methods
 * @description Methods declared with the synchronized modifier.
 * @kind diagnostic
 * @id local/sync-methods
 */
import java

from Method m
where m.isSynchronized()
select
  m,
  m.getFile().getRelativePath() + ":" + m.getLocation().getStartLine().toString() +
    " " + m.getQualifiedName() + " synchronized_method"
