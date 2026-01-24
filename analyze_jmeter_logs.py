#!/usr/bin/env python3
"""
JMeter Log File Analyzer and Comparator
Analyzes JMeter log files and provides detailed performance metrics comparison
"""

import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def analyze_log_file(file_path):
    """
    Analyze a JMeter log file and extract key metrics
    """
    print(f"\n📊 Analyzing {file_path}...")

    # Read CSV file - JMeter logs are typically CSV format
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

    # Basic info
    total_requests = len(df)
    print(f"   Total requests: {total_requests:,}")

    # Time range
    start_time = df['timeStamp'].min()
    end_time = df['timeStamp'].max()
    duration_ms = end_time - start_time
    duration_sec = duration_ms / 1000.0
    duration_min = duration_sec / 60.0

    # Success/Failure analysis
    success_count = df['success'].sum()
    failure_count = total_requests - success_count
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
    failure_rate = 100 - success_rate

    # Response time statistics (elapsed time in ms)
    avg_response_time = df['elapsed'].mean()
    min_response_time = df['elapsed'].min()
    max_response_time = df['elapsed'].max()
    median_response_time = df['elapsed'].median()
    std_response_time = df['elapsed'].std()

    # Percentiles
    p50 = df['elapsed'].quantile(0.50)
    p90 = df['elapsed'].quantile(0.90)
    p95 = df['elapsed'].quantile(0.95)
    p99 = df['elapsed'].quantile(0.99)

    # Latency statistics
    avg_latency = df['Latency'].mean()
    min_latency = df['Latency'].min()
    max_latency = df['Latency'].max()

    # Throughput calculation
    throughput = total_requests / duration_sec if duration_sec > 0 else 0

    # Successful requests throughput
    successful_throughput = success_count / duration_sec if duration_sec > 0 else 0

    # Data transfer statistics
    total_bytes_received = df['bytes'].sum()
    total_bytes_sent = df['sentBytes'].sum()
    avg_bytes_received = df['bytes'].mean()
    avg_bytes_sent = df['sentBytes'].mean()

    # Throughput over time (requests per second in 30-second windows)
    df['timeStamp_sec'] = (df['timeStamp'] - start_time) / 1000.0
    df['time_window'] = (df['timeStamp_sec'] // 30).astype(int)  # 30-second windows
    throughput_over_time = df.groupby('time_window').size()

    # Response time over time
    response_time_over_time = df.groupby('time_window')['elapsed'].mean()

    # Request type breakdown
    request_breakdown = df.groupby('label').agg({
        'elapsed': ['count', 'mean', 'min', 'max'],
        'success': 'sum'
    }).round(2)

    metrics = {
        'file_path': file_path,
        'total_requests': total_requests,
        'duration_sec': duration_sec,
        'duration_min': duration_min,
        'success_count': success_count,
        'failure_count': failure_count,
        'success_rate': success_rate,
        'failure_rate': failure_rate,
        'avg_response_time_ms': avg_response_time,
        'min_response_time_ms': min_response_time,
        'max_response_time_ms': max_response_time,
        'median_response_time_ms': median_response_time,
        'std_response_time_ms': std_response_time,
        'p50_ms': p50,
        'p90_ms': p90,
        'p95_ms': p95,
        'p99_ms': p99,
        'avg_latency_ms': avg_latency,
        'min_latency_ms': min_latency,
        'max_latency_ms': max_latency,
        'throughput_req_sec': throughput,
        'successful_throughput_req_sec': successful_throughput,
        'total_bytes_received': total_bytes_received,
        'total_bytes_sent': total_bytes_sent,
        'avg_bytes_received': avg_bytes_received,
        'avg_bytes_sent': avg_bytes_sent,
        'throughput_over_time': throughput_over_time,
        'response_time_over_time': response_time_over_time,
        'request_breakdown': request_breakdown,
        'dataframe': df
    }

    return metrics

def print_metrics(metrics, branch_name):
    """
    Print metrics in a readable format
    """
    print(f"\n{'='*80}")
    print(f"📈 {branch_name.upper()} BRANCH METRICS")
    print(f"{'='*80}")

    print(f"\n⏱️  Duration & Volume:")
    print(f"   Test Duration:        {metrics['duration_min']:.2f} minutes ({metrics['duration_sec']:.2f} seconds)")
    print(f"   Total Requests:       {metrics['total_requests']:,}")
    print(f"   Successful Requests:  {metrics['success_count']:,} ({metrics['success_rate']:.2f}%)")
    print(f"   Failed Requests:      {metrics['failure_count']:,} ({metrics['failure_rate']:.2f}%)")

    print(f"\n🚀 Throughput:")
    print(f"   Overall Throughput:   {metrics['throughput_req_sec']:.2f} req/sec")
    print(f"   Success Throughput:   {metrics['successful_throughput_req_sec']:.2f} req/sec")
    print(f"   Calculation:          {metrics['total_requests']:,} requests ÷ {metrics['duration_sec']:.2f} sec")

    print(f"\n⚡ Response Time (milliseconds):")
    print(f"   Average:              {metrics['avg_response_time_ms']:.2f} ms")
    print(f"   Median (P50):         {metrics['median_response_time_ms']:.2f} ms")
    print(f"   Std Deviation:        {metrics['std_response_time_ms']:.2f} ms")
    print(f"   Minimum:              {metrics['min_response_time_ms']:.2f} ms")
    print(f"   Maximum:              {metrics['max_response_time_ms']:.2f} ms")

    print(f"\n📊 Percentiles:")
    print(f"   P50 (50th):           {metrics['p50_ms']:.2f} ms")
    print(f"   P90 (90th):           {metrics['p90_ms']:.2f} ms")
    print(f"   P95 (95th):           {metrics['p95_ms']:.2f} ms")
    print(f"   P99 (99th):           {metrics['p99_ms']:.2f} ms")

    print(f"\n⏳ Latency:")
    print(f"   Average Latency:      {metrics['avg_latency_ms']:.2f} ms")
    print(f"   Min Latency:          {metrics['min_latency_ms']:.2f} ms")
    print(f"   Max Latency:          {metrics['max_latency_ms']:.2f} ms")

    print(f"\n📦 Data Transfer:")
    print(f"   Total Received:       {metrics['total_bytes_received'] / 1024 / 1024:.2f} MB")
    print(f"   Total Sent:           {metrics['total_bytes_sent'] / 1024 / 1024:.2f} MB")
    print(f"   Avg Bytes Received:   {metrics['avg_bytes_received']:.2f} bytes")
    print(f"   Avg Bytes Sent:       {metrics['avg_bytes_sent']:.2f} bytes")

def compare_metrics(master_metrics, gpt_metrics):
    """
    Compare metrics between master and GPT branches
    """
    print(f"\n{'='*80}")
    print(f"🔍 COMPARATIVE ANALYSIS: MASTER vs GPT")
    print(f"{'='*80}")

    def percent_change(old, new):
        if old == 0:
            return 0
        return ((new - old) / old) * 100

    def format_change(old, new, unit="", inverse=False):
        """Format change with color indicators"""
        change = percent_change(old, new)
        if inverse:
            change = -change  # For metrics where lower is better

        if abs(change) < 0.01:
            symbol = "="
            indicator = "🟡"
        elif change > 0:
            symbol = "↑"
            indicator = "🟢" if not inverse else "🔴"
        else:
            symbol = "↓"
            indicator = "🔴" if not inverse else "🟢"

        return f"{symbol} {abs(change):+6.2f}% {indicator}"

    comparison = []

    # Throughput comparison
    print(f"\n🚀 Throughput Comparison:")
    master_tp = master_metrics['throughput_req_sec']
    gpt_tp = gpt_metrics['throughput_req_sec']
    change = format_change(master_tp, gpt_tp)
    print(f"   {'Branch':<10} {'Total Req':>12} {'Duration':>12} {'Throughput':>15}")
    print(f"   {'-'*55}")
    print(f"   {'Master':<10} {master_metrics['total_requests']:>12,} {master_metrics['duration_sec']:>9.2f} sec {master_tp:>12.2f} r/s")
    print(f"   {'GPT':<10} {gpt_metrics['total_requests']:>12,} {gpt_metrics['duration_sec']:>9.2f} sec {gpt_tp:>12.2f} r/s")
    print(f"   {'-'*55}")
    print(f"   Change:     {change}")
    comparison.append(['Throughput (req/sec)', master_tp, gpt_tp, percent_change(master_tp, gpt_tp)])

    # Response time comparison
    print(f"\n⚡ Average Response Time Comparison:")
    master_rt = master_metrics['avg_response_time_ms']
    gpt_rt = gpt_metrics['avg_response_time_ms']
    change = format_change(master_rt, gpt_rt, inverse=True)  # Lower is better
    print(f"   Master:     {master_rt:8.2f} ms")
    print(f"   GPT:        {gpt_rt:8.2f} ms")
    print(f"   Change:     {change}")
    comparison.append(['Avg Response Time (ms)', master_rt, gpt_rt, percent_change(master_rt, gpt_rt)])

    # Max response time comparison
    print(f"\n🔥 Maximum Response Time Comparison:")
    master_max = master_metrics['max_response_time_ms']
    gpt_max = gpt_metrics['max_response_time_ms']
    change = format_change(master_max, gpt_max, inverse=True)
    print(f"   Master:     {master_max:8.2f} ms")
    print(f"   GPT:        {gpt_max:8.2f} ms")
    print(f"   Change:     {change}")
    comparison.append(['Max Response Time (ms)', master_max, gpt_max, percent_change(master_max, gpt_max)])

    # P99 comparison
    print(f"\n📊 P99 Latency Comparison:")
    master_p99 = master_metrics['p99_ms']
    gpt_p99 = gpt_metrics['p99_ms']
    change = format_change(master_p99, gpt_p99, inverse=True)
    print(f"   Master:     {master_p99:8.2f} ms")
    print(f"   GPT:        {gpt_p99:8.2f} ms")
    print(f"   Change:     {change}")
    comparison.append(['P99 (ms)', master_p99, gpt_p99, percent_change(master_p99, gpt_p99)])

    # Error rate comparison
    print(f"\n❌ Error Rate Comparison:")
    master_err = master_metrics['failure_rate']
    gpt_err = gpt_metrics['failure_rate']
    change = format_change(master_err, gpt_err, inverse=True)
    print(f"   Master:     {master_err:8.4f}%")
    print(f"   GPT:        {gpt_err:8.4f}%")
    print(f"   Change:     {change}")
    comparison.append(['Error Rate (%)', master_err, gpt_err, percent_change(master_err, gpt_err)])

    # Duration comparison
    print(f"\n⏱️  Test Duration Comparison:")
    master_dur = master_metrics['duration_sec']
    gpt_dur = gpt_metrics['duration_sec']
    print(f"   Master:     {master_dur:8.2f} seconds ({master_dur/60:.2f} min)")
    print(f"   GPT:        {gpt_dur:8.2f} seconds ({gpt_dur/60:.2f} min)")
    print(f"   Difference: {gpt_dur - master_dur:+8.2f} seconds ({(gpt_dur - master_dur)/60:+.2f} min)")
    comparison.append(['Duration (seconds)', master_dur, gpt_dur, percent_change(master_dur, gpt_dur)])

    # Total requests comparison
    print(f"\n📦 Total Requests Comparison:")
    master_req = master_metrics['total_requests']
    gpt_req = gpt_metrics['total_requests']
    print(f"   Master:     {master_req:8,} requests")
    print(f"   GPT:        {gpt_req:8,} requests")
    print(f"   Difference: {gpt_req - master_req:+8,} requests")
    comparison.append(['Total Requests', master_req, gpt_req, percent_change(master_req, gpt_req)])

    # Throughput explanation
    master_throughput = master_metrics['throughput_req_sec']
    gpt_throughput = gpt_metrics['throughput_req_sec']

    print(f"\n💡 Throughput Explanation:")
    print(f"   ┌────────────────────────────────────────────────────────────────────┐")
    print(f"   │ Throughput = Total Requests ÷ Time Duration                       │")
    print(f"   ├────────────────────────────────────────────────────────────────────┤")
    print(f"   │ Master: {master_req:>8,} req ÷ {master_dur:>7.2f} sec = {master_throughput:>7.2f} req/sec │")
    print(f"   │ GPT:    {gpt_req:>8,} req ÷ {gpt_dur:>7.2f} sec = {gpt_throughput:>7.2f} req/sec │")
    print(f"   └────────────────────────────────────────────────────────────────────┘")
    if gpt_req > master_req and gpt_throughput < master_throughput:
        print(f"   ⚠️  GPT processed MORE total requests ({gpt_req:,} vs {master_req:,})")
        print(f"       but took LONGER ({gpt_dur/60:.2f} min vs {master_dur/60:.2f} min)")
        print(f"       resulting in LOWER throughput ({gpt_throughput:.2f} vs {master_throughput:.2f} req/sec)")
    elif master_req > gpt_req and master_throughput < gpt_throughput:
        print(f"   ⚠️  Master processed MORE total requests ({master_req:,} vs {gpt_req:,})")
        print(f"       but took LONGER ({master_dur/60:.2f} min vs {gpt_dur/60:.2f} min)")
        print(f"       resulting in LOWER throughput ({master_throughput:.2f} vs {gpt_throughput:.2f} req/sec)")

    # Percentile comparison table
    print(f"\n📊 Percentile Comparison:")
    print(f"   {'Percentile':<15} {'Master':>12} {'GPT':>12} {'Change':>15}")
    print(f"   {'-'*55}")

    percentiles = ['p50_ms', 'p90_ms', 'p95_ms', 'p99_ms']
    percentile_labels = ['P50 (median)', 'P90', 'P95', 'P99']

    for label, key in zip(percentile_labels, percentiles):
        master_val = master_metrics[key]
        gpt_val = gpt_metrics[key]
        change_pct = percent_change(master_val, gpt_val)
        print(f"   {label:<15} {master_val:>10.2f} ms {gpt_val:>10.2f} ms {change_pct:>+12.2f}%")
        comparison.append([label + ' (ms)', master_val, gpt_val, change_pct])

    # Summary
    print(f"\n{'='*80}")
    print(f"📋 SUMMARY")
    print(f"{'='*80}")

    # Determine winner for key metrics
    def winner(master, gpt, lower_is_better=False):
        if master == gpt:
            return "TIE"
        if lower_is_better:
            return "GPT" if gpt < master else "MASTER"
        else:
            return "GPT" if gpt > master else "MASTER"

    print(f"\n🏆 Performance Winners:")
    print(f"   Throughput:           {winner(master_metrics['throughput_req_sec'], gpt_metrics['throughput_req_sec'])}")
    print(f"   Avg Response Time:    {winner(master_metrics['avg_response_time_ms'], gpt_metrics['avg_response_time_ms'], True)}")
    print(f"   Max Response Time:    {winner(master_metrics['max_response_time_ms'], gpt_metrics['max_response_time_ms'], True)}")
    print(f"   P99 Latency:          {winner(master_metrics['p99_ms'], gpt_metrics['p99_ms'], True)}")
    print(f"   Error Rate:           {winner(master_metrics['failure_rate'], gpt_metrics['failure_rate'], True)}")

    return comparison

def save_comparison_to_csv(comparison, master_metrics, gpt_metrics, output_file='jmeter_comparison.csv'):
    """
    Save comparison results to CSV
    """
    # Create comparison dataframe
    comparison_df = pd.DataFrame(comparison, columns=['Metric', 'Master', 'GPT', 'Change_%'])
    comparison_df = comparison_df.round(4)

    # Save to CSV
    comparison_df.to_csv(output_file, index=False)
    print(f"\n💾 Comparison saved to: {output_file}")

    # Also save detailed metrics
    detailed_output = output_file.replace('.csv', '_detailed.csv')

    # Create detailed metrics dictionary
    all_metrics = {}
    for key in master_metrics.keys():
        if key not in ['throughput_over_time', 'response_time_over_time', 'request_breakdown', 'dataframe']:
            all_metrics[f'master_{key}'] = [master_metrics[key]]
            all_metrics[f'gpt_{key}'] = [gpt_metrics[key]]

    detailed_df = pd.DataFrame(all_metrics)
    detailed_df.to_csv(detailed_output, index=False)
    print(f"💾 Detailed metrics saved to: {detailed_output}")

    # Save throughput over time comparison
    throughput_comparison_file = output_file.replace('.csv', '_throughput_over_time.csv')

    master_tp_df = master_metrics['throughput_over_time'].reset_index()
    master_tp_df.columns = ['time_window_30sec', 'master_requests']
    master_tp_df['master_req_per_sec'] = master_tp_df['master_requests'] / 30.0

    gpt_tp_df = gpt_metrics['throughput_over_time'].reset_index()
    gpt_tp_df.columns = ['time_window_30sec', 'gpt_requests']
    gpt_tp_df['gpt_req_per_sec'] = gpt_tp_df['gpt_requests'] / 30.0

    throughput_over_time_df = pd.merge(master_tp_df, gpt_tp_df, on='time_window_30sec', how='outer').fillna(0)
    throughput_over_time_df['time_minutes'] = throughput_over_time_df['time_window_30sec'] * 0.5
    throughput_over_time_df.to_csv(throughput_comparison_file, index=False)
    print(f"💾 Throughput over time saved to: {throughput_comparison_file}")

def main():
    """
    Main function to analyze and compare JMeter logs
    """
    print("="*80)
    print("🔬 JMeter Log Analyzer & Comparator")
    print("="*80)

    # File paths
    master_file = '/Users/parth/agentic-code-optimization/mylogfile.log.master.5'
    gpt_file = '/Users/parth/agentic-code-optimization/mylogfile.log.gpt.3'

    # Analyze both files
    master_metrics = analyze_log_file(master_file)
    gpt_metrics = analyze_log_file(gpt_file)

    if master_metrics is None or gpt_metrics is None:
        print("❌ Failed to analyze one or both files")
        return 1

    # Print individual metrics
    print_metrics(master_metrics, "MASTER")
    print_metrics(gpt_metrics, "GPT")

    # Compare metrics
    comparison = compare_metrics(master_metrics, gpt_metrics)

    # Save to CSV
    save_comparison_to_csv(comparison, master_metrics, gpt_metrics)

    print(f"\n{'='*80}")
    print("✅ Analysis complete!")
    print(f"{'='*80}\n")

    return 0

if __name__ == '__main__':
    sys.exit(main())
