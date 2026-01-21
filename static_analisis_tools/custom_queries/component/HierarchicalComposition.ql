/**
 * @name Hierarchical Composition
 * @description Derives parent-child relationships among components (File -> Namespace -> Class -> Function).
 * @kind problem
 * @id cpp/hierarchical-composition
 * @problem.severity recommendation
 * @tags component-agent
 */

import cpp

from Element parent, Element child, string relationType
where
  (
    child instanceof Function and
    parent = child.(Function).getDeclaringType() and
    relationType = "Class '" + parent.(Class).getName() + "' contains function '" + child.(Function).getName() + "'"
  )
  or
  (
    child instanceof Class and
    parent = child.(Class).getNamespace() and
    relationType = "Namespace '" + parent.(Namespace).getName() + "' contains class '" + child.(Class).getName() + "'"
  )
  or
  (
    // Top-level functions in a file (not in any class)
    child instanceof Function and
    parent = child.(Function).getFile() and
    not exists(child.(Function).getDeclaringType()) and
    relationType = "File '" + parent.(File).getBaseName() + "' contains function '" + child.(Function).getName() + "'"
  )
  or
  (
    // Top-level variables in a file
    child instanceof GlobalVariable and
    parent = child.(GlobalVariable).getFile() and
    relationType = "File '" + parent.(File).getBaseName() + "' contains variable '" + child.(GlobalVariable).getName() + "'"
  )
select parent, relationType
