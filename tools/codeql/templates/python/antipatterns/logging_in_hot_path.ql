/**
 * @name Eager string formatting in logging call (anti-pattern, Python)
 * @description logger.info("got %s" % x) or f-strings inside logger calls.
 *              The formatting cost is paid even when the level is disabled.
 *              Fix: use the lazy form `logger.info("got %s", x)`.
 * @kind problem
 * @problem.severity recommendation
 * @id ${RULE_ID}
 */

import python

string getServiceFromPath(File f) {
  exists(string p |
    p = f.getRelativePath() and
    p.matches("${PATH_LIKE}") and
    result = p.regexpCapture("${PATH_REGEX_CAPTURE}", 1)
  )
}

predicate inScope(Module m) {
  m.getFile().getRelativePath().matches("${PATH_LIKE}")
}

predicate isLoggingCall(Call c) {
  exists(string n | n = c.getFunc().(Attribute).getName() |
    n = "debug" or n = "info" or n = "warning" or n = "error" or
    n = "critical" or n = "exception" or n = "log"
  )
}

from Call call, Function enclosing, string serviceName, Expr arg, string argKind
where
  enclosing = call.getScope() and
  inScope(enclosing.getEnclosingModule()) and
  isLoggingCall(call) and
  arg = call.getArg(0) and
  (
    (arg instanceof BinaryExpr and argKind = "binary_format") or
    (arg.toString().matches("f%") and argKind = "fstring")
  ) and
  serviceName = getServiceFromPath(enclosing.getEnclosingModule().getFile())
select call, "kind=eager_log_format|service=" + serviceName +
  "|kind=" + argKind +
  "|in_function=" + enclosing.getQualifiedName()
