/**
 * @name TeaStore Component Inventory
 * @description Captures all packages, classes, and methods in TeaStore microservices
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

from Element e, string kind, string fqn, string serviceName, string message
where
  // Packages
  (
    exists(Package p |
      e = p and
      serviceName = getMicroserviceFromPackage(p) and
      kind = "package" and
      fqn = p.getName() and
      message = "kind=component|component_type=package|service=" + serviceName + 
                "|fqn=" + fqn +
                "|file=" + e.getLocation().getFile().getRelativePath() +
                "|start_line=" + e.getLocation().getStartLine() +
                "|end_line=" + e.getLocation().getEndLine()
    )
  )
  or
  // Classes
  (
    exists(Class c |
      e = c and
      c.fromSource() and
      serviceName = getMicroserviceFromPackage(c.getPackage()) and
      kind = "class" and
      fqn = c.getQualifiedName() and
      message = "kind=component|component_type=class|service=" + serviceName + 
                "|fqn=" + fqn +
                "|file=" + e.getLocation().getFile().getRelativePath() +
                "|start_line=" + e.getLocation().getStartLine() +
                "|end_line=" + e.getLocation().getEndLine()
    )
  )
  or
  // Methods
  (
    exists(Method m |
      e = m and
      m.fromSource() and
      serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
      kind = "method" and
      fqn = m.getQualifiedName() and
      message = "kind=component|component_type=method|service=" + serviceName + 
                "|fqn=" + fqn +
                "|file=" + e.getLocation().getFile().getRelativePath() +
                "|start_line=" + e.getLocation().getStartLine() +
                "|end_line=" + e.getLocation().getEndLine()
    )
  )
select e, message