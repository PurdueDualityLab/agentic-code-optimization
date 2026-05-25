/**
 * @name Outgoing HTTP calls
 * @description Heuristic HTTP client call sites.
 * @kind diagnostic
 * @id local/http-clients
 */
import java

predicate isHttpClientType(string qname) {
  qname = "org.springframework.web.client.RestTemplate" or
  qname = "org.springframework.web.reactive.function.client.WebClient" or
  qname = "org.apache.http.client.HttpClient" or
  qname = "org.apache.http.client.methods.HttpUriRequest" or
  qname = "org.apache.hc.client5.http.classic.HttpClient" or
  qname = "okhttp3.OkHttpClient" or
  qname = "okhttp3.Call" or
  qname = "okhttp3.Request" or
  qname = "java.net.URL" or
  qname = "java.net.URLConnection"
}

predicate isHttpCall(MethodCall call) {
  isHttpClientType(call.getMethod().getDeclaringType().getQualifiedName()) or
  call.getMethod().getName() = "retrieve" or
  call.getMethod().getName() = "exchange" or
  call.getMethod().getName() = "execute" or
  call.getMethod().getName() = "send" or
  call.getMethod().getName() = "newCall"
}

from MethodCall call, Callable caller
where
  caller = call.getEnclosingCallable() and
  isHttpCall(call)
select
  call,
  call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() +
    " " + caller.getQualifiedName() + " -> " + call.getMethod().getQualifiedName() +
    " http_outgoing_call"
