/**
 * @name Database access
 * @description JDBC/JPA/repository access sites.
 * @kind diagnostic
 * @id local/db-access
 */
import java

predicate isJdbcType(string qname) {
  qname = "java.sql.Connection" or
  qname = "java.sql.Statement" or
  qname = "java.sql.PreparedStatement" or
  qname = "java.sql.ResultSet" or
  qname = "javax.sql.DataSource"
}

predicate isJpaType(string qname) {
  qname = "javax.persistence.EntityManager" or
  qname = "jakarta.persistence.EntityManager"
}

predicate isDbCall(MethodCall call) {
  isJdbcType(call.getMethod().getDeclaringType().getQualifiedName()) or
  isJpaType(call.getMethod().getDeclaringType().getQualifiedName()) or
  call.getMethod().getDeclaringType().getName().matches("%Repository") or
  call.getMethod().getDeclaringType().getQualifiedName().matches("%Repository")
}

from MethodCall call, Callable caller
where
  caller = call.getEnclosingCallable() and
  isDbCall(call)
select
  call,
  call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() +
    " " + caller.getQualifiedName() + " -> " + call.getMethod().getQualifiedName() +
    " db_access"
