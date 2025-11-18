"""
Main script to fetch and display Kubernetes deployment metrics from Dynatrace
"""
import argparse
import csv
import json
from datetime import datetime, timedelta
from dynatrace_client import DynatraceClient


def format_memory(memory_bytes: float) -> str:
    """
    Format memory in bytes to human-readable format

    Args:
        memory_bytes: Memory in bytes

    Returns:
        Formatted string (e.g., "512.5 MB")
    """
    if memory_bytes >= 1024 ** 3:
        return f"{memory_bytes / (1024 ** 3):.2f} GB"
    elif memory_bytes >= 1024 ** 2:
        return f"{memory_bytes / (1024 ** 2):.2f} MB"
    elif memory_bytes >= 1024:
        return f"{memory_bytes / 1024:.2f} KB"
    else:
        return f"{memory_bytes:.2f} B"


def format_cpu(cpu_millicores: float) -> str:
    """
    Format CPU in millicores to human-readable format

    Args:
        cpu_millicores: CPU in millicores

    Returns:
        Formatted string (e.g., "1.5 cores")
    """
    if cpu_millicores >= 1000:
        return f"{cpu_millicores / 1000:.2f} cores"
    else:
        return f"{cpu_millicores:.2f} millicores"


def get_deployment_metrics(
    cluster_name: str,
    namespace: str,
    hours_back: int = 24,
    output_format: str = 'table',
    output_file: str = None,
    include_heap: bool = False
):
    """
    Get deployment metrics for a specific cluster and namespace

    Args:
        cluster_name: Kubernetes cluster name
        namespace: Kubernetes namespace
        hours_back: Number of hours to look back for metrics (default: 24)
        output_format: Output format - 'table', 'json', or 'csv'
        output_file: Output file path (required for CSV format)
        include_heap: Include JVM heap memory metrics (default: False)
    """
    client = DynatraceClient()

    print(f"Fetching deployments for cluster '{cluster_name}' in namespace '{namespace}'...")
    deployments = client.get_deployments(cluster_name, namespace)

    if not deployments:
        print(f"No deployments found in cluster '{cluster_name}' namespace '{namespace}'")
        return

    print(f"Found {len(deployments)} deployment(s)\n")

    # Calculate time range
    time_to = datetime.now()
    time_from = time_to - timedelta(hours=hours_back)

    results = []

    for deployment in deployments:
        if 'displayName' in deployment and deployment['displayName'] != 'engine':
            continue
        deployment_name = deployment.get('displayName', 'Unknown')
        entity_id = deployment.get('entityId', '')

        print(f"Fetching metrics for deployment: {deployment_name}...")

        cpu_metrics, memory_metrics, heap_metrics, pod_count = client.get_workload_metrics(
            deployment_entity_id=entity_id,
            time_from=time_from.strftime('%Y-%m-%dT%H:%M:%S'),
            time_to=time_to.strftime('%Y-%m-%dT%H:%M:%S'),
            include_heap=include_heap
        )

        result = {
            'deployment_name': deployment_name,
            'namespace': namespace,
            'cluster': cluster_name,
            'pod_count': pod_count,
            'cpu': {
                'min': cpu_metrics['min'],
                'max': cpu_metrics['max'],
                'min_formatted': format_cpu(cpu_metrics['min']),
                'max_formatted': format_cpu(cpu_metrics['max'])
            },
            'memory': {
                'min': memory_metrics['min'],
                'max': memory_metrics['max'],
                'min_formatted': format_memory(memory_metrics['min']),
                'max_formatted': format_memory(memory_metrics['max'])
            }
        }

        if include_heap and heap_metrics:
            result['heap'] = {
                'min': heap_metrics['min'],
                'max': heap_metrics['max'],
                'min_formatted': format_memory(heap_metrics['min']),
                'max_formatted': format_memory(heap_metrics['max'])
            }

        results.append(result)

    # Output results
    if output_format == 'csv':
        if not output_file:
            output_file = f"deployment_metrics_{cluster_name}_{namespace}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = [
                'cluster',
                'deployment',
                'cpu_usage_min',
                'cpu_usage_max',
                'memory_usage_min',
                'memory_usage_max',
            ]

            if include_heap:
                fieldnames.extend([
                    'heap_usage_min',
                    'heap_usage_max'
                ])

            fieldnames.append('number_of_pods')

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = {
                    'cluster': result['cluster'],
                    'deployment': result['deployment_name'],
                    'cpu_usage_min': result['cpu']['min'],
                    'cpu_usage_max': result['cpu']['max'],
                    'memory_usage_min': result['memory']['min'],
                    'memory_usage_max': result['memory']['max'],
                    'number_of_pods': result['pod_count']
                }

                if include_heap and 'heap' in result:
                    row['heap_usage_min'] = result['heap']['min']
                    row['heap_usage_max'] = result['heap']['max']

                writer.writerow(row)

        print(f"\nCSV file saved to: {output_file}")

    elif output_format == 'json':
        print("\n" + json.dumps(results, indent=2))
    else:
        # Table output
        if include_heap:
            sep_line = "=" * 152
            header = (f"{'Deployment':<30} | {'Pods':<6} | {'CPU Min':<15} | {'CPU Max':<15} | "
                     f"{'Memory Min':<15} | {'Memory Max':<15} | {'Heap Min':<15} | {'Heap Max':<15}")
        else:
            sep_line = "=" * 120
            header = f"{'Deployment':<30} | {'Pods':<6} | {'CPU Min':<15} | {'CPU Max':<15} | {'Memory Min':<15} | {'Memory Max':<15}"

        print("\n" + sep_line)
        print(header)
        print(sep_line)

        for result in results:
            line = (
                f"{result['deployment_name']:<30} | "
                f"{result['pod_count']:<6} | "
                f"{result['cpu']['min_formatted']:<15} | "
                f"{result['cpu']['max_formatted']:<15} | "
                f"{result['memory']['min_formatted']:<15} | "
                f"{result['memory']['max_formatted']:<15}"
            )

            if include_heap and 'heap' in result:
                line += (
                    f" | {result['heap']['min_formatted']:<15} | "
                    f"{result['heap']['max_formatted']:<15}"
                )

            print(line)

        print(sep_line)

    print(f"\nMetrics collected from: {time_from.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"                    to: {time_to.strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Fetch Kubernetes deployment metrics from Dynatrace'
    )
    parser.add_argument(
        '--cluster',
        required=False,
        help='Kubernetes cluster name',
        default='aks-playground'
    )
    parser.add_argument(
        '--namespace',
        required=False,
        help='Kubernetes namespace',
        default='astroshop'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to look back for metrics (default: 24)'
    )
    parser.add_argument(
        '--format',
        choices=['table', 'json', 'csv'],
        default='table',
        help='Output format (default: table)'
    )
    parser.add_argument(
        '--output',
        '-o',
        help='Output file path (for CSV format). If not specified, auto-generates filename.'
    )
    parser.add_argument(
        '--include-heap',
        action='store_true',
        help='Include JVM heap memory metrics (for Spring Boot microservices)'
    )

    args = parser.parse_args()

    try:
        get_deployment_metrics(
            cluster_name=args.cluster,
            namespace=args.namespace,
            hours_back=args.hours,
            output_format=args.format,
            output_file=args.output,
            include_heap=args.include_heap
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
