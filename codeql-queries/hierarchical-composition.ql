/**
 * @name TeaStore Hierarchical Composition (Service Level)
 * @description Captures service-to-package and package-to-class relationships only
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/hierarchical-composition
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\.descartes\\.teastore\\.([^.]+).*", 1)
  )
}

predicate isSignificantClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Dao") or
  c.getName().matches("%Entity")
}

from Element child, string serviceName, string parentFqn, string childFqn, string relType
where
  // Package contains significant classes only
  (
    exists(Package p, Class c |
      c.getPackage() = p and
      serviceName = getMicroserviceFromPackage(p) and
      isSignificantClass(c) and
      c.fromSource() and
      child = c and
      parentFqn = p.getName() and
      childFqn = c.getQualifiedName() and
      relType = "package_to_class"
    )
  )
  or
  // Class inheritance (only for significant classes)
  (
    exists(Class sub, Class sup |
      sub.fromSource() and
      isSignificantClass(sub) and
      sup = sub.getASupertype() and
      sup instanceof Class and
      serviceName = getMicroserviceFromPackage(sub.getPackage()) and
      child = sub and
      parentFqn = sup.getQualifiedName() and
      childFqn = sub.getQualifiedName() and
      relType = "inheritance"
    )
  )
select child, "kind=hierarchical_composition|service=" + serviceName +
  "|relation=" + relType +
  "|parent=" + parentFqn +
  "|child=" + childFqn
