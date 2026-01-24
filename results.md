================================================================================
🔬 JMeter Log Analyzer & Comparator
================================================================================

📊 Analyzing /Users/parth/agentic-code-optimization/mylogfile.log.master.5...
/Users/parth/agentic-code-optimization/analyze_jmeter_logs.py:22: DtypeWarning: Columns (0: responseCode, 1: responseMessage) have mixed types. Specify dtype option on import or set low_memory=False.
  df = pd.read_csv(file_path)
   Total requests: 799,976

📊 Analyzing /Users/parth/agentic-code-optimization/mylogfile.log.gpt.3...
   Total requests: 800,000

================================================================================
📈 MASTER BRANCH METRICS
================================================================================

⏱️  Duration & Volume:
   Test Duration:        11.13 minutes (667.88 seconds)
   Total Requests:       799,976
   Successful Requests:  799,938 (100.00%)
   Failed Requests:      38 (0.00%)

🚀 Throughput:
   Overall Throughput:   1197.79 req/sec
   Success Throughput:   1197.73 req/sec
   Calculation:          799,976 requests ÷ 667.88 sec

⚡ Response Time (milliseconds):
   Average:              12.84 ms
   Median (P50):         13.00 ms
   Std Deviation:        12.64 ms
   Minimum:              0.00 ms
   Maximum:              2592.00 ms

📊 Percentiles:
   P50 (50th):           13.00 ms
   P90 (90th):           23.00 ms
   P95 (95th):           24.00 ms
   P99 (99th):           26.00 ms

⏳ Latency:
   Average Latency:      9.56 ms
   Min Latency:          0.00 ms
   Max Latency:          2592.00 ms

📦 Data Transfer:
   Total Received:       24373.55 MB
   Total Sent:           749.23 MB
   Avg Bytes Received:   31947.86 bytes
   Avg Bytes Sent:       982.06 bytes

================================================================================
📈 GPT BRANCH METRICS
================================================================================

⏱️  Duration & Volume:
   Test Duration:        8.15 minutes (489.03 seconds)
   Total Requests:       800,000
   Successful Requests:  800,000 (100.00%)
   Failed Requests:      0 (0.00%)

🚀 Throughput:
   Overall Throughput:   1635.89 req/sec
   Success Throughput:   1635.89 req/sec
   Calculation:          800,000 requests ÷ 489.03 sec

⚡ Response Time (milliseconds):
   Average:              9.27 ms
   Median (P50):         9.00 ms
   Std Deviation:        11.53 ms
   Minimum:              0.00 ms
   Maximum:              2475.00 ms

📊 Percentiles:
   P50 (50th):           9.00 ms
   P90 (90th):           18.00 ms
   P95 (95th):           20.00 ms
   P99 (99th):           23.00 ms

⏳ Latency:
   Average Latency:      6.90 ms
   Min Latency:          0.00 ms
   Max Latency:          2470.00 ms

📦 Data Transfer:
   Total Received:       24599.13 MB
   Total Sent:           749.35 MB
   Avg Bytes Received:   32242.57 bytes
   Avg Bytes Sent:       982.18 bytes

================================================================================
🔍 COMPARATIVE ANALYSIS: MASTER vs GPT
================================================================================

🚀 Throughput Comparison:
   Branch        Total Req     Duration      Throughput
   -------------------------------------------------------
   Master          799,976    667.88 sec      1197.79 r/s
   GPT             800,000    489.03 sec      1635.89 r/s
   -------------------------------------------------------
   Change:     ↑ +36.58% 🟢

⚡ Average Response Time Comparison:
   Master:        12.84 ms
   GPT:            9.27 ms
   Change:     ↑ +27.81% 🔴

🔥 Maximum Response Time Comparison:
   Master:      2592.00 ms
   GPT:         2475.00 ms
   Change:     ↑  +4.51% 🔴

📊 P99 Latency Comparison:
   Master:        26.00 ms
   GPT:           23.00 ms
   Change:     ↑ +11.54% 🔴

❌ Error Rate Comparison:
   Master:       0.0048%
   GPT:          0.0000%
   Change:     ↑ +100.00% 🔴

⏱️  Test Duration Comparison:
   Master:       667.88 seconds (11.13 min)
   GPT:          489.03 seconds (8.15 min)
   Difference:  -178.84 seconds (-2.98 min)

📦 Total Requests Comparison:
   Master:      799,976 requests
   GPT:         800,000 requests
   Difference:      +24 requests

💡 Throughput Explanation:
   ┌────────────────────────────────────────────────────────────────────┐
   │ Throughput = Total Requests ÷ Time Duration                       │
   ├────────────────────────────────────────────────────────────────────┤
   │ Master:  799,976 req ÷  667.88 sec = 1197.79 req/sec │
   │ GPT:     800,000 req ÷  489.03 sec = 1635.89 req/sec │
   └────────────────────────────────────────────────────────────────────┘

📊 Percentile Comparison:
   Percentile            Master          GPT          Change
   -------------------------------------------------------
   P50 (median)         13.00 ms       9.00 ms       -30.77%
   P90                  23.00 ms      18.00 ms       -21.74%
   P95                  24.00 ms      20.00 ms       -16.67%
   P99                  26.00 ms      23.00 ms       -11.54%

================================================================================
📋 SUMMARY
================================================================================

🏆 Performance Winners:
   Throughput:           GPT
   Avg Response Time:    GPT
   Max Response Time:    GPT
   P99 Latency:          GPT
   Error Rate:           GPT

💾 Comparison saved to: jmeter_comparison.csv
💾 Detailed metrics saved to: jmeter_comparison_detailed.csv
💾 Throughput over time saved to: jmeter_comparison_throughput_over_time.csv

================================================================================
✅ Analysis complete!
================================================================================
