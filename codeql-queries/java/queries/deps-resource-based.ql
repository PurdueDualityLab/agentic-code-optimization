/**
 * @name TeaStore Resource-Based Dependencies
 * @description Captures resource references (URLs, file paths)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-resource-based
 */

import java

from StringLiteral s
where
  s.getValue().matches("%http%") or s.getValue().matches("%/api/%")
select s, "kind=deps_resource_based|value=" + s.getValue() +
  "|file=" + s.getLocation().getFile().getRelativePath() +
  "|start_line=" + s.getLocation().getStartLine() +
  "|end_line=" + s.getLocation().getEndLine()
