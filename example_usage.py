"""
Example of using the Dynatrace client programmatically
"""
import csv
from datetime import datetime, timedelta
from dynatrace_client import DynatraceClient


def example_basic_usage():
    """Basic example - fetch deployment metrics"""
    # Initialize client (reads from .env file)
    client = DynatraceClient()

    # Specify your cluster and namespace
    cluster_name = "my-cluster"
    namespace = "production"

    # Get all deployments
    print(f"Fetching deployments in {cluster_name}/{namespace}...")
    deployments = client.get_deployments(cluster_name, namespace)

    print(f"Found {len(deployments)} deployments\n")

    # Set time range (last 24 hours)
    time_to = datetime.now()
    time_from = time_to - timedelta(hours=24)

    # Fetch metrics for each deployment
    for deployment in deployments:
        name = deployment.get('displayName', 'Unknown')
        entity_id = deployment.get('entityId', '')

        print(f"\nDeployment: {name}")
        print(f"Entity ID: {entity_id}")

        # Get metrics
        cpu_metrics, memory_metrics, pod_count = client.get_workload_metrics(
            deployment_entity_id=entity_id,
            time_from=time_from.strftime('%Y-%m-%dT%H:%M:%S'),
            time_to=time_to.strftime('%Y-%m-%dT%H:%M:%S')
        )

        # Display results
        print(f"  Pod Count: {pod_count}")
        print(f"  CPU:")
        print(f"    Min: {cpu_metrics['min']:.2f} millicores")
        print(f"    Max: {cpu_metrics['max']:.2f} millicores")
        print(f"  Memory:")
        print(f"    Min: {memory_metrics['min'] / (1024**2):.2f} MB")
        print(f"    Max: {memory_metrics['max'] / (1024**2):.2f} MB")


def example_custom_credentials():
    """Example with custom credentials (not using .env)"""
    client = DynatraceClient(
        base_url="https://your-env.live.dynatrace.com",
        api_token="your-api-token"
    )

    deployments = client.get_deployments("my-cluster", "default")
    print(f"Found {len(deployments)} deployments")


def example_process_data():
    """Example showing how to process and aggregate data"""
    client = DynatraceClient()

    cluster_name = "my-cluster"
    namespace = "production"

    deployments = client.get_deployments(cluster_name, namespace)

    time_to = datetime.now()
    time_from = time_to - timedelta(hours=168)  # Last 7 days

    total_cpu_max = 0
    total_memory_max = 0
    total_pods = 0

    for deployment in deployments:
        entity_id = deployment.get('entityId', '')
        cpu_metrics, memory_metrics, pod_count = client.get_workload_metrics(
            deployment_entity_id=entity_id,
            time_from=time_from.strftime('%Y-%m-%dT%H:%M:%S'),
            time_to=time_to.strftime('%Y-%m-%dT%H:%M:%S')
        )

        total_cpu_max += cpu_metrics['max']
        total_memory_max += memory_metrics['max']
        total_pods += pod_count

    print(f"\nCluster: {cluster_name}, Namespace: {namespace}")
    print(f"Total Deployments: {len(deployments)}")
    print(f"Total Pods: {total_pods}")
    print(f"Total Max CPU: {total_cpu_max / 1000:.2f} cores")
    print(f"Total Max Memory: {total_memory_max / (1024**3):.2f} GB")


def example_export_to_csv():
    """Example showing how to export data to CSV programmatically"""
    client = DynatraceClient()

    cluster_name = "my-cluster"
    namespace = "production"

    deployments = client.get_deployments(cluster_name, namespace)

    time_to = datetime.now()
    time_from = time_to - timedelta(hours=24)

    # Prepare data for CSV
    csv_data = []

    for deployment in deployments:
        name = deployment.get('displayName', 'Unknown')
        entity_id = deployment.get('entityId', '')

        cpu_metrics, memory_metrics, pod_count = client.get_workload_metrics(
            deployment_entity_id=entity_id,
            time_from=time_from.strftime('%Y-%m-%dT%H:%M:%S'),
            time_to=time_to.strftime('%Y-%m-%dT%H:%M:%S')
        )

        csv_data.append({
            'cluster': cluster_name,
            'deployment': name,
            'cpu_usage_min': cpu_metrics['min'],
            'cpu_usage_max': cpu_metrics['max'],
            'memory_usage_min': memory_metrics['min'],
            'memory_usage_max': memory_metrics['max'],
            'number_of_pods': pod_count
        })

    # Write to CSV
    output_file = f'deployment_metrics_{cluster_name}_{namespace}.csv'
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'cluster',
            'deployment',
            'cpu_usage_min',
            'cpu_usage_max',
            'memory_usage_min',
            'memory_usage_max',
            'number_of_pods'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"CSV exported to: {output_file}")


if __name__ == '__main__':
    print("Example 1: Basic Usage")
    print("=" * 50)
    example_basic_usage()

    # Uncomment to run other examples
    # print("\n\nExample 2: Custom Credentials")
    # print("=" * 50)
    # example_custom_credentials()

    # print("\n\nExample 3: Process and Aggregate Data")
    # print("=" * 50)
    # example_process_data()

    # print("\n\nExample 4: Export to CSV")
    # print("=" * 50)
    # example_export_to_csv()
