/**
 * @name Evidence Mapping
 * @description Associates components with precise source locations for traceability.
 * @kind problem
 * @id cpp/evidence-mapping
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Element e, string elementType
where
  (
    e instanceof Function and
    not e.(Function).isCompilerGenerated() and
    elementType = "Function: " + e.(Function).getName()
  )
  or
  (
    e instanceof Class and
    elementType = "Class: " + e.(Class).getName()
  )
  or
  (
    e instanceof GlobalVariable and
    elementType = "Global variable: " + e.(GlobalVariable).getName()
  )
select e, elementType
