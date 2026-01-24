/**
 * @name TeaStore Control Flow Structure (Aggregated)
 * @description Captures control-flow statement counts per class
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/control-flow-structure
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
  c.getName().matches("%Handler")
}

from Class c, string serviceName, int ifCount, int forCount, int whileCount, int switchCount
where
  c.fromSource() and
  isSignificantClass(c) and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  ifCount = count(IfStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  forCount = count(ForStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  whileCount = count(WhileStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  switchCount = count(SwitchStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  (ifCount > 0 or forCount > 0 or whileCount > 0 or switchCount > 0)
select c, "kind=control_flow_structure|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|if_count=" + ifCount +
  "|for_count=" + forCount +
  "|while_count=" + whileCount +
  "|switch_count=" + switchCount
