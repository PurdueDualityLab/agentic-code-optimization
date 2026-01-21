/**
 * @name Component Inventory
 * @description Identifies all software components (functions, classes, namespaces, files).
 * @kind problem
 * @id cpp/component-inventory
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Element e, string componentType
where
  (
    e instanceof Function and
    componentType = "Function: " + e.(Function).getName()
  )
  or
  (
    e instanceof Class and
    componentType = "Class: " + e.(Class).getName()
  )
  or
  (
    e instanceof Namespace and
    componentType = "Namespace: " + e.(Namespace).getName()
  )
  or
  (
    e instanceof File and
    componentType = "File: " + e.(File).getBaseName()
  )
select e, componentType
