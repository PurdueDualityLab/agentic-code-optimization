/**
 * @name Java methods
 * @description Lists methods with their declaring type and name.
 * @kind diagnostic
 * @id local/java-methods
 */
import java

from Method m
select m,
  "Declaring type: " + m.getDeclaringType().getName() +
  ", name: " + m.getName()
