/**
 * @name TeaStore Component Inventory (Filtered)
 * @description Lists only significant packages, endpoint classes, and service classes
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/component-inventory
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
  c.getName().matches("%Application") or
  c.getName().matches("%Registry") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Dao") or
  c.getName().matches("%Entity")
}

from Element e, string kind, string fqn, string serviceName, string message
where
  // Only top-level service packages (not every subpackage)
  (
    exists(Package p |
      e = p and
      serviceName = getMicroserviceFromPackage(p) and
      // Only capture direct service packages, not nested ones
      p.getName().regexpMatch("tools\\.descartes\\.teastore\\.[^.]+") and
      kind = "package" and
      fqn = p.getName() and
      message = "kind=component|component_type=package|service=" + serviceName + "|fqn=" + fqn
    )
  )
  or
  // Only significant classes (endpoints, services, etc.)
  (
    exists(Class c |
      e = c and
      c.fromSource() and
      isSignificantClass(c) and
      serviceName = getMicroserviceFromPackage(c.getPackage()) and
      kind = "class" and
      fqn = c.getQualifiedName() and
      message = "kind=component|component_type=class|service=" + serviceName + "|fqn=" + fqn
    )
  )
select e, message
